"""Per-user, per-version update notes; no network or administrator access."""
from pathlib import Path
import json,os,tempfile

VERSION='1.1.0'
UPDATE_NOTES=(
    'V1.1 更新内容\n\n'
    '• 文件夹批量超分：只扫描所选文件夹本层的 TIF/TIFF，不扫描子目录。\n\n'
    '• 自动建立金字塔：每幅成果配套生成同名 .tif.ovr，提高影像浏览效率。\n\n'
    '• 更大的 GPU 批量：初始 batch 默认 64，可设置为 1–128；显存不足自动降低 batch、缩小分块，最终回退 CPU。\n\n'
    '• 批量进度与结果汇总：显示当前文件，支持取消；已完成的成果保留。'
)

def show_updates_once(show,log=lambda message:None,data_dir=None,version=VERSION):
    directory=Path(data_dir) if data_dir is not None else Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'GeoSR'
    state=directory/'seen_updates.json'
    seen=[]
    try:
        data=json.loads(state.read_text(encoding='utf-8'))
        if isinstance(data,dict) and isinstance(data.get('versions'),list):
            seen=[x for x in data['versions'] if isinstance(x,str)][-100:]
    except (OSError,ValueError):pass
    if version in seen:return False
    # Only remember after the user dismisses the dialog.
    show('更新日志 · V1.1',UPDATE_NOTES)
    temp=None
    try:
        directory.mkdir(parents=True,exist_ok=True)
        fd,name=tempfile.mkstemp(prefix='seen_updates-',suffix='.tmp',dir=directory)
        temp=Path(name)
        with os.fdopen(fd,'w',encoding='utf-8') as f:json.dump({'versions':seen+[version]},f,ensure_ascii=False)
        os.replace(temp,state);temp=None
    except OSError as exc:
        log(f'无法保存更新日志已读状态，下次启动可能再次提示：{exc}')
    finally:
        if temp is not None:
            try:temp.unlink()
            except OSError:pass
    return True
