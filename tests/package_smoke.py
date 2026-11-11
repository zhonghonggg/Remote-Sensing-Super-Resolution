"""Exercise the frozen program with a directory, Unicode paths, and external OVRs."""
from pathlib import Path
import tempfile,subprocess,json,os
import numpy as np,rasterio
from rasterio.transform import from_origin
R=Path(__file__).resolve().parents[1]
(R/'QA').mkdir(exist_ok=True)
T=Path(tempfile.mkdtemp(prefix='packaged-',dir=R/'QA'));inputs=T/'中文原图';inputs.mkdir()
template=inputs/'a.TIF';a=np.full((3,32,32),120,dtype='uint8');a[:,:8,:8]=0
with rasterio.open(template,'w',driver='GTiff',width=32,height=32,count=3,dtype='uint8',crs='EPSG:32650',transform=from_origin(500000,2800000,1,1),nodata=0) as d:d.write(a)
import shutil
shutil.copy2(template,inputs/'b.tiff');(inputs/'nested').mkdir();shutil.copy2(template,inputs/'nested/ignored.tif')
report=T/'结果.json';env=os.environ.copy()
for key in ['PYTHONPATH','PYTHONHOME','GDAL_DATA','PROJ_DATA','PROJ_LIB']:env.pop(key,None)
env['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
p=subprocess.run([str(R/'dist/GeoSR/GeoSR.exe'),'--input',str(inputs),'--output',str(T/'成果'),'--resolution','0.5','--cpu','--report',str(report)],env=env,timeout=180)
assert p.returncode==0,p.returncode
data=json.loads(report.read_text(encoding='utf-8'))
assert data['success'] and data['total']==2 and len(data['outputs'])==2,data
for output in data['outputs']:
    assert Path(output+'.ovr').is_file()
    with rasterio.open(output) as d:
        assert d.res==(.5,.5) and d.crs.to_epsg()==32650 and d.overviews(1)==[2]
        assert d.read(4,out_shape=(64,64))[0,0]==0
assert len(list((T/'成果').iterdir()))==4
print('Packaged directory CPU / external OVR / Unicode / isolated environment passed:',report)
