from pathlib import Path
import os,subprocess,json
import rasterio
R=Path(__file__).resolve().parents[1];T=R/'QA'
app=T/'中文安装目录/GeoSR.exe'
env=os.environ.copy()
for k in ['PYTHONPATH','PYTHONHOME','GDAL_DATA','PROJ_LIB','PROJ_DATA']:
    env.pop(k,None)
env['PATH']=str(Path(os.environ['SystemRoot'])/'System32')
for cpu in [False,True]:
    report=T/('installed-cpu.json' if cpu else 'installed-gpu.json')
    args=[str(app),'--input',str(T/'莆田实际裁块.tif'),'--output',str(T/'安装后成果'),
          '--resolution','0.2','--report',str(report)]
    if cpu:args.append('--cpu')
    result=subprocess.run(args,env=env,timeout=180)
    assert result.returncode==0,result.returncode
    data=json.loads(report.read_text(encoding='utf-8'));assert data['success'],data
    with rasterio.open(data['output']) as d:
        assert d.res==(.2,.2) and d.crs.to_epsg()==32650 and d.count==4
        assert d.overviews(1) and Path(data['output']+'.ovr').is_file()
        for _,w in d.block_windows(1):d.read(window=w)
    if not cpu:assert any(e[0].endswith('AI增强') and e[2]=='DirectML' for e in data['events'])
print('Installed EXE CPU / GPU passed with Python and geospatial environment paths removed')
