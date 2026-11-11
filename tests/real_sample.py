from pathlib import Path
import sys,json
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'src'))
from engine import *
T=R/'QA';p=T/'莆田实际裁块.tif'
with rasterio.open(R.parent/'最终成果/Putian_区域原始裁剪.tif') as src:
    win=Window(3000,1500,384,256);a=src.read(window=win)
    profile=src.profile.copy();profile.update(width=384,height=256,transform=src.window_transform(win))
    with rasterio.open(p,'w',**profile) as d:d.write(a)
reports=[]
for cpu in [False,True]:
    e=[];out=Runner(Config(str(p),str(T/('实际CPU' if cpu else '实际GPU')),.2,cpu,128,4),lambda *x:e.append(x)).run()
    with rasterio.open(out) as d:
        assert d.res==(.2,.2) and d.crs.to_epsg()==32650
        reports.append(dict(cpu=cpu,output=str(out),crs=str(d.crs),shape=[d.width,d.height],res=d.res,bounds=list(d.bounds),events=e))
(T/'real-sample.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
print('real image CPU + DirectML complete')
