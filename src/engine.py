"""Bounded-memory GeoTIFF AI enhancement. No CUDA dependency."""
from pathlib import Path
import gc, math, os, shutil, tempfile, threading, uuid, warnings
from dataclasses import dataclass
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.enums import ColorInterp, Resampling
from rasterio.vrt import WarpedVRT
from rasterio.warp import transform_bounds
from rasterio.transform import from_origin
from affine import Affine
from pyproj import CRS
import onnxruntime as ort
from overviews import build_external

class Cancelled(Exception): pass

@dataclass
class Config:
    source: str
    output: str
    resolution: float = .2
    cpu: bool = False
    tile: int = 256
    batch: int = 64
    minimum_tile: int = 64

def resource(name):
    import sys
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / name

class Runner:
    def __init__(self, cfg, notify=lambda *args: None, cancel=None, factory=None):
        self.cfg, self.notify = cfg, notify
        self.cancel = cancel or threading.Event()
        self.factory = factory
        self.tile, self.batch = cfg.tile, 1 if cfg.cpu else cfg.batch
        self.device = 'CPU' if cfg.cpu else 'DirectML'
        self.suggested_batch = self.batch
        self.session = None
        self.completed = 0

    def event(self, stage, percent, message):
        self.notify(stage, min(100, percent), self.device, message)

    def check(self):
        if self.cancel.is_set(): raise Cancelled('任务已取消')

    def session_init(self):
        self.session = None
        gc.collect()
        if self.factory:
            self.session = self.factory(self.device)
            return
        opts = ort.SessionOptions()
        opts.enable_mem_pattern = False
        opts.enable_cpu_mem_arena = False
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.intra_op_num_threads = min(4, os.cpu_count() or 1)
        providers = ['CPUExecutionProvider'] if self.device == 'CPU' else ['DmlExecutionProvider', 'CPUExecutionProvider']
        if self.device == 'DirectML' and 'DmlExecutionProvider' not in ort.get_available_providers():
            raise RuntimeError('DirectML 不可用')
        self.session = ort.InferenceSession(str(resource('models/general-x4v3.onnx')), opts, providers=providers)
        if self.device == 'DirectML' and self.session.get_providers()[0] != 'DmlExecutionProvider':
            raise RuntimeError('DirectML 初始化未成功')

    def fallback(self, error):
        self.check()
        if self.batch > 1:
            self.batch = max(1, self.batch // 2)
            reason = f'batch 降为 {self.batch}'
        elif self.tile > self.cfg.minimum_tile:
            self.tile = max(self.cfg.minimum_tile, self.tile // 2)
            reason = f'tile 降为 {self.tile}'
        elif self.device != 'CPU':
            self.device = 'CPU'
            self.batch = 1
            reason = '自动切换 CPU，保留已完成分块'
        else:
            raise RuntimeError(f'CPU 最小分块仍失败：{error}') from error
        self.event('AI增强', self.ai_percent(), f'推理失败：{str(error)[:400]}；{reason}')
        self.suggested_batch = self.batch
        try:
            self.session_init()
        except Exception as exc:
            if self.device == 'CPU': raise
            self.device = 'CPU'
            self.batch = 1
            self.event('AI增强', self.ai_percent(), f'GPU 重建失败，自动 CPU：{exc}')
            self.session_init()

    def ai_percent(self): return 5 + 65 * self.completed / self.total

    def memory_batch_limit(self, size):
        import ctypes as C
        class Memory(C.Structure):
            _fields_=[('length',C.c_uint32),('load',C.c_uint32)]+[(n,C.c_uint64) for n in ('total','available','page_total','page_available','virtual_total','virtual_available','extended')]
        mem=Memory();mem.length=C.sizeof(mem)
        try:
            ok=C.windll.kernel32.GlobalMemoryStatusEx(C.byref(mem))
            budget=max(1,mem.available//3) if ok else 512*1024**2
        except AttributeError:budget=512*1024**2
        # Two input buffers + x4 output + mask/scratch allowance; independent of image area.
        per_item=size*size*(3*4*18+8)
        return max(1,int(budget//per_item))

    def infer_regions(self, src, dst, regions):
        """Small pending queue only; successful regions are never reprocessed."""
        pending = list(regions)
        while pending:
            self.check()
            # Repartition only unfinished rectangles after a tile reduction.
            if any(w>self.tile or h>self.tile for x,y,w,h in pending):
                pending=[(xx,yy,min(self.tile,x+w-xx),min(self.tile,y+h-yy))
                         for x,y,w,h in pending for yy in range(y,y+h,self.tile) for xx in range(x,x+w,self.tile)]
            # Fixed square context makes all items in a batch stackable.
            pad = 40  # receptive radius 34, plus interpolation margin
            size = self.tile + 2*pad
            memory_limit=self.memory_batch_limit(size)
            if self.batch>memory_limit:self.suggested_batch=min(self.suggested_batch,memory_limit)
            limit=min(len(pending),memory_limit)
            if self.batch>limit:
                self.batch=limit
                self.event('AI增强',self.ai_percent(),f'按剩余分块数 / 可用系统内存设置实际 batch={self.batch}')
            group = pending[:self.batch]
            arrays, masks = [], []
            result=None
            try:
                for x,y,w,h in group:
                    win = Window(x-pad,y-pad,size,size)
                    a = src.read(self.channels, window=win, boundless=True, fill_value=0)
                    m = np.min(src.read_masks(self.channels,window=win,boundless=True),axis=0)>0
                    if len(self.channels)==1: a=np.repeat(a,3,axis=0)
                    a=a.astype(np.float32)/self.scale
                    a[:,~m]=0
                    arrays.append(a)
                    masks.append(m[pad:pad+h,pad:pad+w])
                result = self.session.run(None, {'input':np.ascontiguousarray(np.stack(arrays))})[0]
                if result.shape != (len(group),3,size*4,size*4):
                    raise RuntimeError(f'模型输出形状错误 {result.shape}')
            except Exception as exc:
                result=None;arrays.clear();masks.clear()
                self.fallback(exc)
                continue
            self.check()
            for i,(x,y,w,h) in enumerate(group):
                rgb=np.rint(np.clip(result[i,:,pad*4:(pad+h)*4,pad*4:(pad+w)*4],0,1)*255).astype('uint8')
                alpha=np.repeat(np.repeat(masks[i],4,0),4,1).astype('uint8')*255
                rgb[:,alpha==0]=0
                dst.write(np.concatenate((rgb,alpha[None])),window=Window(x*4,y*4,w*4,h*4))
                self.completed += w*h
            del result, arrays
            pending = pending[len(group):]
            self.event('AI增强',self.ai_percent(),f'已处理 {self.completed:,}/{self.total:,} 原图像元；batch={len(group)}，tile={self.tile}')

    def target_grid(self, src):
        crs=CRS(src.crs)
        bounds=transform_bounds(src.crs,'EPSG:4326',*src.bounds,densify_pts=21)
        west,south,east,north=bounds
        if crs.is_projected and all(abs(a.unit_conversion_factor-1)<1e-9 for a in crs.axis_info[:2]):
            target=src.crs
        else:
            if not (-80 <= south <= north <= 84) or east-west>6 or east<=west:
                raise ValueError('自动 UTM 仅支持纬度 -80° 至 84°、经度跨度不超过 6°且不跨日期变更线的区域；请先重投影到当地米制投影。')
            zone=max(1,min(60,int(((west+east)/2+180)//6)+1))
            target=rasterio.crs.CRS.from_epsg((32600 if (south+north)/2>=0 else 32700)+zone)
            self.event('准备',2,f'经纬度或非米制投影转换到 {target}；UTM 中心分区，跨带边缘存在投影变形')
        left,bottom,right,top=transform_bounds(src.crs,target,*src.bounds,densify_pts=41)
        r=self.cfg.resolution
        left=math.floor(left/r)*r; top=math.ceil(top/r)*r
        width=math.ceil((right-left)/r);height=math.ceil((top-bottom)/r)
        if min(width,height)<1 or max(width,height)>2147483647: raise ValueError('目标网格超出支持范围')
        return target,from_origin(left,top,r,r),width,height

    def run(self):
        c=self.cfg
        if not math.isfinite(c.resolution) or c.resolution<=0: raise ValueError('目标像元必须为正数（米）')
        if not (32<=c.minimum_tile<=c.tile<=512 and 1<=c.batch<=128): raise ValueError('分块参数超出安全范围（batch 1–128）')
        source=Path(c.source).resolve();out=Path(c.output).resolve()
        if source.suffix.lower() not in ('.tif','.tiff'): raise ValueError('仅支持 GeoTIFF')
        out.mkdir(parents=True,exist_ok=True)
        work=None
        try:
            self.check()
            self.event('准备',0,'读取影像信息；人工增强不代表新增真实测量精度')
            with rasterio.Env(GDAL_CACHEMAX=128*1024*1024,GDAL_NUM_THREADS='2'):
                with rasterio.open(source) as src:
                    if not src.crs: raise ValueError('输入缺少坐标系')
                    if src.count not in (1,3,4) or src.dtypes[0] not in ('uint8','uint16'):
                        raise ValueError('支持 uint8/uint16 单波段灰度、RGB 或 RGBA GeoTIFF；多光谱/浮点数据需先转换为显示影像')
                    if ColorInterp.palette in src.colorinterp:
                        raise ValueError('调色板 GeoTIFF 需先转换为 RGB')
                    if src.count==4 and src.colorinterp[3]!=ColorInterp.alpha:
                        raise ValueError('4 波段必须带明确的 Alpha 标记；不自动把近红外当透明度')
                    self.channels=[1] if src.count==1 else [1,2,3]
                    self.scale=255 if src.dtypes[0]=='uint8' else 65535
                    if self.scale==65535:self.event('准备',1,'16位输入按 0–65535 归一化，输出为8位显示影像；不进行辐射定量保持')
                    crs,tr,width,height=self.target_grid(src)
                    self.total=src.width*src.height
                    estimate=self.total*16*4+width*height*4*1.4
                    self.event('准备',3,f'目标 {width:,}×{height:,}，{c.resolution} 米；未压缩暂存上限估计 {estimate/1024**3:.2f} GiB')
                    if shutil.disk_usage(out).free < estimate*1.05+64*1024**2:
                        raise ValueError('输出磁盘可用空间不足以容纳保守估计的临时影像和最终影像')
                    work=Path(tempfile.mkdtemp(prefix='.geosr-task-',dir=out))
                    try:self.session_init()
                    except Exception as exc:
                        self.device='CPU';self.batch=1;self.event('准备',4,f'GPU 初始化失败，使用 CPU：{exc}');self.session_init()
                    self.event('AI增强',5,f'设备 {self.device}；初始 batch={self.batch}，tile={self.tile}；执行一次4倍增强')
                    profile=dict(driver='GTiff',count=4,dtype='uint8',crs=src.crs,
                        transform=src.transform*Affine.scale(.25,.25),width=src.width*4,height=src.height*4,
                        tiled=True,blockxsize=256,blockysize=256,compress='deflate',BIGTIFF='YES',SPARSE_OK=True)
                    stage=work/'ai.tif'
                    with rasterio.open(stage,'w',**profile) as dst:
                        dst.colorinterp=(ColorInterp.red,ColorInterp.green,ColorInterp.blue,ColorInterp.alpha)
                        # At most batch macro-tiles in memory, independent of image dimensions.
                        group=[]
                        for y in range(0,src.height,c.tile):
                            for x in range(0,src.width,c.tile):
                                group.append((x,y,min(c.tile,src.width-x),min(c.tile,src.height-y)))
                                if len(group)>=self.batch:
                                    self.infer_regions(src,dst,group);group=[]
                        if group:self.infer_regions(src,dst,group)
                self.session=None;gc.collect()
                partial=work/'result.tif'
                profile.update(crs=crs,transform=tr,width=width,height=height)
                with rasterio.open(stage) as ai, WarpedVRT(ai,crs=crs,transform=tr,width=width,height=height,
                        resampling=Resampling.cubic,warp_mem_limit=128) as vrt, rasterio.open(partial,'w',**profile) as dst:
                    dst.colorinterp=ai.colorinterp
                    n=math.ceil(width/256)*math.ceil(height/256)
                    for i,(_,win) in enumerate(dst.block_windows(1),1):
                        self.check();dst.write(vrt.read(window=win),window=win)
                        self.event('米制网格',70+18*i/n,f'重投影 / 重采样 {i:,}/{n:,}')
                    dst.update_tags(MODEL='Real-ESRGAN realesr-general-x4v3',AI_ENHANCEMENT='Artificial detail, not measured spatial accuracy',
                                    TARGET_PIXEL_METRES=str(c.resolution),SOURCE=source.name,MODEL_PASSES='1',VALIDITY='Alpha band')
                levels=[2]
                while max(width,height)/levels[-1]>256:levels.append(levels[-1]*2)
                self.event('建立金字塔',88,f'生成外部 .tif.ovr，缩小倍数 {levels}')
                last_progress=[-1]
                def overview_progress(fraction):
                    self.check()
                    value=int(fraction*100)
                    if value!=last_progress[0]:
                        last_progress[0]=value
                        self.event('建立金字塔',88+8*fraction,f'金字塔构建 {value}%')
                    return True
                sidecar=build_external(partial,levels,overview_progress)
                self.check()
                with rasterio.open(partial) as final:
                    if final.crs!=crs or final.width!=width or final.height!=height or not np.allclose(final.res,(c.resolution,)*2,rtol=0,atol=1e-10):
                        raise RuntimeError('输出地理参考校验失败')
                    for i,(_,win) in enumerate(final.block_windows(1),1):
                        self.check();final.read(window=win)
                        self.event('校验',96+3*i/n,f'影像与金字塔可读性校验 {i:,}/{n:,}')
                    for band in range(1,5):
                        if len(final.overviews(band))!=len(levels):raise RuntimeError('外部金字塔层数校验失败')
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore',rasterio.errors.NotGeoreferencedWarning)
                        with rasterio.open(sidecar) as ovr:
                            if ovr.count!=4 or (ovr.width,ovr.height)!=(math.ceil(width/2),math.ceil(height/2)):
                                raise RuntimeError('外部金字塔尺寸校验失败')
                            for _,win in ovr.block_windows(1):self.check();ovr.read(window=win)
                self.check()
                name=f'{source.stem}_AI_{c.resolution:g}m_{uuid.uuid4().hex[:8]}.tif'
                target=out/name
                target_ovr=Path(str(target)+'.ovr')
                os.rename(sidecar,target_ovr)
                try:
                    self.check()
                    os.rename(partial,target)  # Publish TIFF only when its overview is ready.
                except BaseException:
                    target_ovr.unlink() # Only this invocation's newly published sidecar.
                    raise
            shutil.rmtree(work)
            work=None
            self.event('完成',100,str(target))
            return target
        finally:
            self.session=None
            # Only the directory created by this invocation is ever removed.
            if work is not None: shutil.rmtree(work)
