from pathlib import Path
import sys,json
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'src'))
from engine import *
T=R/'QA';data=json.loads((T/'real-sample.json').read_text(encoding='utf-8'))
with rasterio.open(T/'莆田实际裁块.tif') as s:
    assert np.any(s.read()!=0),'actual sample must contain valid imagery'
    bounds=transform_bounds(s.crs,'EPSG:32650',*s.bounds,densify_pts=41)
    source_valid=float((s.dataset_mask()>0).mean())
with rasterio.open(data[0]['output']) as a,rasterio.open(data[1]['output']) as b:
    assert a.bounds.left<=bounds[0] and a.bounds.bottom<=bounds[1] and a.bounds.right>=bounds[2] and a.bounds.top>=bounds[3]
    for x,y in zip([bounds[0]-a.bounds.left,bounds[1]-a.bounds.bottom,a.bounds.right-bounds[2],a.bounds.top-bounds[3]],[.2]*4):assert -1e-8<=x<=y+1e-8
    diff=np.abs(a.read().astype('int16')-b.read().astype('int16'))
    report=dict(source_valid_fraction=source_valid,cpu_gpu_max_difference=int(diff.max()),cpu_gpu_mean_difference=float(diff.mean()),
                grid_contains_source=True,outward_grid_padding_below_one_pixel=True,shape=[a.width,a.height],bounds=list(a.bounds),res=a.res)
    assert report['cpu_gpu_max_difference']<=3,report
(T/'output-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(report)
