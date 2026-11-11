from pathlib import Path
from importlib import metadata
import shutil, sys
R=Path(__file__).resolve().parent
O=R/'licenses';O.mkdir(exist_ok=True)
for d in metadata.distributions():
    name=d.metadata['Name'];out=O/name
    for f in d.files or []:
        if any(x in f.name.lower() for x in ['license','copying','notice','copyright']):
            p=Path(d.locate_file(f))
            if p.is_file():
                out.mkdir(exist_ok=True);shutil.copy2(p,out/(str(f).replace('/','_').replace('\\','_')))
shutil.copy2(R/'vendor/Real-ESRGAN-LICENSE.txt',O/'Real-ESRGAN-LICENSE.txt')
python_license=Path(sys.base_prefix)/'LICENSE.txt'
if python_license.exists():shutil.copy2(python_license,O/'CPython-LICENSE.txt')
