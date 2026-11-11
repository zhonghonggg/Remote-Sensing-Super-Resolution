"""Single-image and non-recursive directory jobs, processed sequentially."""
from dataclasses import dataclass,field,replace
from pathlib import Path
import threading
from engine import Runner,Cancelled

def discover_inputs(source):
    path=Path(source).expanduser()
    if path.is_file():
        if path.suffix.lower() not in ('.tif','.tiff'):raise ValueError('请选择 GeoTIFF 文件或文件夹')
        return [path]
    if not path.is_dir():raise ValueError('请选择有效的 GeoTIFF 文件或文件夹')
    # Snapshot only this directory. Outputs created later cannot enter this queue.
    files=sorted((p for p in path.iterdir() if p.is_file() and p.suffix.lower() in ('.tif','.tiff')),key=lambda p:(p.name.casefold(),p.name))
    if not files:raise ValueError('所选文件夹本层没有 .tif/.tiff 文件（不扫描子文件夹）')
    return files

@dataclass
class BatchResult:
    total:int
    outputs:list=field(default_factory=list)
    failures:list=field(default_factory=list)
    cancelled:bool=False

def run_inputs(config,notify=lambda *e:None,cancel=None,runner_cls=Runner):
    cancel=cancel or threading.Event()
    files=discover_inputs(config.source)
    result=BatchResult(len(files));effective=config
    last_percent=[0.0]
    notify('扫描完成',0,'CPU' if config.cpu else 'DirectML',f'队列共 {len(files)} 幅；文件夹仅扫描本层；逐幅处理')
    for index,source in enumerate(files,1):
        if cancel.is_set():result.cancelled=True;break
        def progress(stage,percent,device,message):
            name=source.name if len(source.name)<=48 else source.name[:45]+'…'
            last_percent[0]=max(last_percent[0],100*(index-1+percent/100)/len(files))
            notify(f'[{index}/{len(files)}] {name} · {stage}',last_percent[0],device,message)
        runner=runner_cls(replace(effective,source=str(source)),progress,cancel)
        try:
            output=runner.run()
            result.outputs.append(str(output))
            progress('文件完成',100,runner.device,f'{source.name} → {output}；金字塔：{output}.ovr')
        except Cancelled:
            result.cancelled=True;break
        except Exception as exc:
            result.failures.append({'source':str(source),'error':str(exc)})
            progress('文件失败',100,runner.device,f'{source.name}：{exc}；继续后续文件')
        # Retain OOM / RAM reductions, without carrying a small image's tail batch into the next file.
        effective=replace(effective,cpu=runner.device=='CPU',tile=runner.tile,batch=getattr(runner,'suggested_batch',config.batch))
    done=len(result.outputs)+len(result.failures)
    message=f'共 {result.total} 幅，成功 {len(result.outputs)}，失败 {len(result.failures)}，未处理 {result.total-done}'
    notify('已取消' if result.cancelled else ('批次结束（含失败）' if result.failures else '全部完成'),
           min(99.999,last_percent[0]) if result.cancelled else 100,
           'CPU' if effective.cpu else 'DirectML',message)
    return result
