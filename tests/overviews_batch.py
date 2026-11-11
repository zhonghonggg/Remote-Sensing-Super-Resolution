from pathlib import Path
import sys,json,threading
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'src'))
from engine import *
T=R/'QA/v1.1';T.mkdir(exist_ok=True,parents=True)
source=T/'中文测试.tif'
a=np.random.default_rng(2).integers(10,245,(3,256,256),dtype='uint8');a[:,:32,:32]=0
with rasterio.open(source,'w',driver='GTiff',crs='EPSG:32650',transform=from_origin(500000,2800000,1,1),width=256,height=256,count=3,dtype='uint8',nodata=0) as d:d.write(a)
class Fake:
    def __init__(self,device,calls,fail):self.device=device;self.calls=calls;self.fail=fail
    def run(self,_,inputs):
        x=inputs['input'];self.calls.append((self.device,list(x.shape)))
        if self.device=='DirectML' and self.fail:raise RuntimeError('injected GPU out of memory')
        return [np.repeat(np.repeat(x,4,2),4,3)]
calls=[];events=[];previous=set((T/'回退').iterdir()) if (T/'回退').exists() else set()
r=Runner(Config(str(source),str(T/'回退'),.5,False,32,64,32),lambda *e:events.append(e),factory=lambda d:Fake(d,calls,True))
p=r.run()
assert [s[1][0] for s in calls[:7]]==[64,32,16,8,4,2,1],calls[:7]
assert calls[-1][0]=='CPU' and r.completed==256*256
with rasterio.open(p) as d:
    assert d.overviews(1)==[2] and d.read(4,out_shape=(256,256))[0,0]==0
    assert d.res==(.5,.5)
assert Path(str(p)+'.ovr').is_file() and len(set(p.parent.iterdir())-previous)==2
assert [e[1] for e in events]==sorted(e[1] for e in events)
assert events[-1][1]==100
# Cancel from the real GDAL callback, then inject a build failure: neither publishes a partial pair.
for kind in ['cancel','failure']:
    dest=T/kind;dest.mkdir(exist_ok=True);keep=dest/'用户文件.txt';keep.write_text('keep')
    ev=threading.Event()
    def note(*e):
        if kind=='cancel' and e[0]=='建立金字塔' and '构建' in e[3]:ev.set()
    runner=Runner(Config(str(source),str(dest),.5,True,64,64),note,ev,lambda d:Fake(d,[],False))
    try:
        if kind=='failure':
            with patch('engine.build_external',side_effect=RuntimeError('injected overview error')):runner.run()
        else:runner.run()
    except (Cancelled,RuntimeError):pass
    else:raise AssertionError('Expected failure')
    assert len(list(dest.iterdir()))==1 and keep.read_text()=='keep'
# Failure during TIFF publication must roll back its already-renamed sidecar.
dest=T/'rename-failure';dest.mkdir(exist_ok=True)
real_rename=os.rename
def fail_publish(src,dst):
    if str(src).endswith('result.tif'):raise OSError('injected publish error')
    return real_rename(src,dst)
try:
    with patch('engine.os.rename',side_effect=fail_publish):Runner(Config(str(source),str(dest),.5,True,64,64),factory=lambda d:Fake(d,[],False)).run()
except OSError:pass
else:raise AssertionError('Expected publication error')
assert not list(dest.iterdir())
# Real DirectML large-batch inference: use 64 tiles, keeping the sample bounded.
actual=T/'实际64batch.tif'
with rasterio.open(source) as s:
    profile=s.profile.copy();profile.update(width=512,height=512)
    with rasterio.open(actual,'w',**profile) as d:
        for y in [0,256]:
            for x in [0,256]:d.write(a,window=Window(x,y,256,256))
real_calls=[]
class TrackingRunner(Runner):
    def session_init(self):
        super().session_init();inner=self.session
        class Track:
            def run(_,outputs,inputs):
                value=inner.run(outputs,inputs)
                real_calls.append((self.device,list(inputs['input'].shape)))
                return value
        self.session=Track()
events_real=[]
p=TrackingRunner(Config(str(actual),str(T/'实际GPU'),1,False,64,64),lambda *e:events_real.append(e)).run()
assert any(dev=='DirectML' and shape[0]==64 for dev,shape in real_calls),real_calls
with rasterio.open(p) as d:assert d.overviews(1)==[2] and d.count==4
(T/'验收.json').write_text(json.dumps(dict(fallback_calls=calls[:8],gpu_calls=real_calls,gpu_events=events_real,ovr=str(p)+'.ovr',cancel_cleanup=True,publish_rollback=True),ensure_ascii=False,indent=2),encoding='utf-8')
print('OVR, 64->1->CPU, cancel/error cleanup, pair rollback, and real DirectML batch=64 passed')
