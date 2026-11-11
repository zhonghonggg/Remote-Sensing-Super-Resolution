from pathlib import Path
import sys,tempfile,shutil,threading,json
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'src'))
from engine import *
from batch import discover_inputs,run_inputs
T=Path(tempfile.mkdtemp(prefix='directory-',dir=R/'QA'))
root=T/'中文原图';root.mkdir();nested=root/'子文件夹';nested.mkdir()
template=R/'QA/中文小样.tif'
for name in ['a.TIF','b.tiff']:shutil.copy2(template,root/name)
(root/'c_bad.tif').write_text('invalid')
shutil.copy2(template,nested/'不处理.tif');(root/'目录.tif').mkdir()
assert [p.name for p in discover_inputs(root)]==['a.TIF','b.tiff','c_bad.tif']
class Fake:
    def run(self,_,d):return [np.repeat(np.repeat(d['input'],4,2),4,3)]
seen=[]
class TestRunner(Runner):
    def run(self):seen.append(Path(self.cfg.source).name);return super().run()
    def session_init(self):self.session=Fake()
events=[]
result=run_inputs(Config(str(root),str(root),.5,True,32,64,32),lambda *e:events.append(e),runner_cls=TestRunner)
assert result.total==3 and len(result.outputs)==2 and len(result.failures)==1 and not result.cancelled
assert seen==['a.TIF','b.tiff','c_bad.tif'] # Newly produced TIFFs never enter this snapshot.
for output in result.outputs:assert Path(output).is_file() and Path(output+'.ovr').is_file()
assert not list(root.glob('.geosr-task-*')) and not list(nested.glob('*_AI_*'))
assert events[-1][1]==100 and '失败' in events[-1][0]
cancel_root=T/'取消';cancel_root.mkdir()
for name in ['first.tif','second.tif']:shutil.copy2(template,cancel_root/name)
ev=threading.Event()
def note(*e):
    if '文件完成' in e[0]:ev.set()
result_cancel=run_inputs(Config(str(cancel_root),str(T/'取消成果'),.5,True,32,64,32),note,ev,TestRunner)
assert result_cancel.cancelled and len(result_cancel.outputs)==1 and result_cancel.total==2
assert len(list((T/'取消成果').iterdir()))==2
empty=T/'空目录';empty.mkdir();(empty/'嵌套').mkdir();shutil.copy2(template,empty/'嵌套/ignored.tif')
try:discover_inputs(empty)
except ValueError:pass
else:raise AssertionError('Nested TIFF must not be discovered')
(R/'QA/批量验收.json').write_text(json.dumps(dict(top_level_only=True,case_insensitive_extensions=True,no_new_output_requeue=True,continue_after_failure=True,cancel_keeps_completed=True,test_directory=str(T)),ensure_ascii=False,indent=2),encoding='utf-8')
print('Nonrecursive directory queue, mixed TIFF extensions, failure continuation, cancellation and output snapshot passed')
