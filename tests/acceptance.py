from pathlib import Path
import sys, threading, json, time
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'src'))
from engine import *
T=R/'QA';T.mkdir(exist_ok=True)
results=[]
def test(name,fn):
    start=time.time();fn();results.append({'test':name,'pass':True,'seconds':round(time.time()-start,2)});print(results[-1],flush=True)
def make(name,crs='EPSG:32650',tr=None,size=48):
    path=T/name
    a=np.random.default_rng(8).integers(10,240,(3,size,size),dtype='uint8');a[:,:8,:8]=0
    with rasterio.open(path,'w',driver='GTiff',count=3,dtype='uint8',width=size,height=size,crs=crs,
                       transform=tr or from_origin(500000,2800000,1,1),nodata=0) as dst:dst.write(a)
    return path
sample=make('中文小样.tif')
def actual(cpu):
    events=[];cfg=Config(str(sample),str(T/('CPU' if cpu else 'GPU')),.2,cpu,64,2)
    p=Runner(cfg,lambda *e:events.append(e)).run()
    with rasterio.open(p) as d:
        assert d.res==(.2,.2) and d.crs.to_epsg()==32650 and d.width==240 and d.height==240
        assert d.read(4)[2,2]==0 and d.read(4)[100,100]>0 and d.count==4
    if not cpu:assert any(e[2]=='DirectML' and e[0]=='AI增强' for e in events)
    assert events[-1][1]==100
    (T/('cpu-events.json' if cpu else 'gpu-events.json')).write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
    assert not list(p.parent.glob('.geosr-task-*'))
test('实际 DirectML 推理与地理参考/Alpha',lambda:actual(False))
test('实际 CPU 推理与地理参考/Alpha',lambda:actual(True))
class Fake:
    def __init__(self,device,state,mode):self.device=device;self.state=state;self.mode=mode
    def run(self,_,inputs):
        a=inputs['input'];self.state.append((self.device,tuple(a.shape)))
        if self.mode=='oom' and self.device=='DirectML':raise RuntimeError('injected GPU out of memory')
        if self.mode=='error':raise RuntimeError('injected terminal error')
        return [np.repeat(np.repeat(a,4,2),4,3)]
def faults():
    a=make('回退.tif',size=160);calls=[];events=[]
    p=Runner(Config(str(a),str(T/'回退'),.5,False,128,4,32),lambda *e:events.append(e),factory=lambda d:Fake(d,calls,'oom')).run()
    assert [x[1][0] for x in calls[:3]]==[4,2,1],calls
    assert any(x[1][2]==144 for x in calls) and any(x[1][2]==112 for x in calls)
    assert calls[-1][0]=='CPU'
    assert len(calls)<50
    (T/'fault-events.json').write_text(json.dumps(dict(events=events,calls=calls),ensure_ascii=False,indent=2),encoding='utf-8')
    # Cancellation and terminal failure clean only their own temporary directory.
    for mode in ['cancel','error']:
        dest=T/mode;dest.mkdir(exist_ok=True);keep=dest/'用户文件.txt';keep.write_text('keep')
        ev=threading.Event()
        def note(*e):
            if mode=='cancel' and e[0]=='AI增强':ev.set()
        try:Runner(Config(str(a),str(dest),.5,True,32,1,32),note,ev,lambda d:Fake(d,[],mode)).run()
        except (Cancelled,RuntimeError):pass
        else:raise AssertionError('expected failure')
        assert keep.read_text()=='keep' and len(list(dest.iterdir()))==1
test('注入 OOM：真实 batch 改变、tile 下降、CPU 回退及安全清理',faults)
def grids():
    a=make('经纬度.tif','EPSG:4326',from_origin(119,25,.00001,.00001),16)
    p=Runner(Config(str(a),str(T/'UTM'),.2,True,32,1,32),factory=lambda d:Fake(d,[],'ok')).run()
    with rasterio.open(p) as d:assert d.crs.to_epsg()==32650 and d.res==(.2,.2)
    a=make('英尺.tif','EPSG:2263',from_origin(980000,190000,3,3),16)
    p=Runner(Config(str(a),str(T/'feet'),.5,True,32,1,32),factory=lambda d:Fake(d,[],'ok')).run()
    with rasterio.open(p) as d:assert d.crs.to_epsg()==32618 and d.res==(.5,.5)
    a=make('极区.tif','EPSG:4326',from_origin(119,89,.00001,.00001),16)
    try:Runner(Config(str(a),str(T/'polar'),.2),factory=lambda d:Fake(d,[],'ok')).run()
    except ValueError as e:assert 'UTM' in str(e)
    else:raise AssertionError('polar must reject')
test('经纬度/英尺投影转换及 UTM 边界拒绝',grids)
def dynamic():
    import onnx
    m=onnx.load(str(R/'models/general-x4v3.onnx'));onnx.checker.check_model(m)
    assert m.graph.input[0].type.tensor_type.shape.dim[0].dim_param=='batch'
    opts=ort.SessionOptions();opts.enable_mem_pattern=False
    s=ort.InferenceSession(str(R/'models/general-x4v3.onnx'),opts,providers=['CPUExecutionProvider'])
    a=np.random.default_rng(5).random((2,3,8,8),dtype=np.float32)
    b=s.run(None,{'input':a})[0]
    assert b.shape==(2,3,32,32)
    for i in range(2):np.testing.assert_allclose(b[i:i+1],s.run(None,{'input':a[i:i+1]})[0],atol=2e-5)
test('动态 batch=2 数值等效逐张推理',dynamic)
(T/'acceptance.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
