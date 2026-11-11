from pathlib import Path
import sys,tempfile,json
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'src'))
from updates import show_updates_once,VERSION,UPDATE_NOTES
T=Path(tempfile.mkdtemp(prefix='updates-',dir=R/'QA'));calls=[]
def show(title,text):
    assert not (T/'seen_updates.json').exists()
    calls.append((title,text))
assert show_updates_once(show,data_dir=T)
assert not show_updates_once(lambda *args:calls.append(args),data_dir=T)
assert len(calls)==1 and VERSION in json.loads((T/'seen_updates.json').read_text())['versions']
assert all(word in UPDATE_NOTES for word in ['本层','.tif.ovr','64','CPU'])
# A future version is shown once, preserving the already-seen release.
assert show_updates_once(lambda *args:calls.append(args),data_dir=T,version='1.2.0')
assert not show_updates_once(lambda *args:calls.append(args),data_dir=T)
assert len(calls)==2
# Read-only preferences do not block the application, and do not mark notes as read.
errors=[]
with patch('updates.os.replace',side_effect=OSError('injected read-only profile')):
    assert show_updates_once(lambda *args:None,errors.append,T/'readonly')
assert errors and not (T/'readonly/seen_updates.json').exists() and not list((T/'readonly').glob('*.tmp'))
print('First-open V1.1 notes, per-version persistence, and read-only profile handling passed')
