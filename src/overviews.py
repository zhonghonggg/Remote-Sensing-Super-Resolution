"""External TIFF overviews using the GDAL runtime already shipped by Rasterio."""
from pathlib import Path
import ctypes as C
import rasterio

def build_external(path, levels, progress):
    # Resolve only Rasterio's own GDAL, including its PyInstaller layout.
    folder=Path(rasterio.__file__).resolve().parent.parent/'rasterio.libs'
    candidates=list(folder.glob('gdal-*.dll'))
    if len(candidates)!=1:raise RuntimeError('无法定位随程序安装的 GDAL 运行库')
    lib=C.CDLL(str(candidates[0]))
    callback_type=C.CFUNCTYPE(C.c_int,C.c_double,C.c_char_p,C.c_void_p)
    lib.GDALAllRegister.argtypes=[];lib.GDALAllRegister.restype=None
    lib.GDALOpenEx.argtypes=[C.c_char_p,C.c_uint,C.c_void_p,C.c_void_p,C.c_void_p];lib.GDALOpenEx.restype=C.c_void_p
    lib.GDALBuildOverviews.argtypes=[C.c_void_p,C.c_char_p,C.c_int,C.POINTER(C.c_int),C.c_int,C.c_void_p,callback_type,C.c_void_p]
    lib.GDALBuildOverviews.restype=C.c_int
    lib.GDALClose.argtypes=[C.c_void_p];lib.GDALClose.restype=C.c_int
    lib.CPLGetLastErrorMsg.argtypes=[];lib.CPLGetLastErrorMsg.restype=C.c_char_p
    lib.GDALAllRegister()
    handle=lib.GDALOpenEx(str(path).encode('utf-8'),2,None,None,None) # raster, read-only => .ovr
    if not handle:raise RuntimeError('无法打开金字塔源影像')
    errors=[]
    def callback(fraction,message,data):
        try:return int(progress(fraction))
        except BaseException as exc:errors.append(exc);return 0
    cb=callback_type(callback)
    factors=(C.c_int*len(levels))(*levels)
    with rasterio.Env(COMPRESS_OVERVIEW='DEFLATE',BIGTIFF_OVERVIEW='YES',GDAL_TIFF_OVR_BLOCKSIZE='256',GDAL_NUM_THREADS='2'):
        try:
            status=lib.GDALBuildOverviews(handle,b'AVERAGE',len(levels),factors,0,None,cb,None)
            message=(lib.CPLGetLastErrorMsg() or b'').decode('utf-8',errors='replace')
        finally:close_status=lib.GDALClose(handle)
    if errors:raise errors[0]
    if status or close_status:raise RuntimeError(f'金字塔生成失败：{message}')
    sidecar=Path(str(path)+'.ovr')
    if not sidecar.is_file():raise RuntimeError('GDAL 未生成外部 .ovr 金字塔')
    return sidecar
