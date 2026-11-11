from pathlib import Path
import hashlib,zipfile,json,shutil,sys
R=Path(__file__).resolve().parent
files=[]
for folder in ['src','tests','assets','models','licenses','wheelhouse','.github']:
    files.extend(p for p in (R/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
files.extend(p for p in (R/'vendor').glob('*') if p.is_file())
if '--public' not in sys.argv:
    files.extend(p for p in (R/'QA').glob('*') if p.is_file() and p.suffix in ('.json','.log'))
files.extend(p for p in R.iterdir() if p.is_file() and p.suffix in ('.py','.md','.txt','.ps1','.spec','.iss'))
if (R/'.gitignore').exists():files.append(R/'.gitignore')
archive=R/'release/GeoSR-1.1.0-Full-Source.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(files)):z.write(p,Path('GeoSR-Source')/p.relative_to(R))
    manifest={str(p.relative_to(R)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    z.writestr('GeoSR-Source/SOURCE-MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
outputs=[R/'release/GeoSR-1.1.0-Windows-x64-Setup.exe',archive]
(R/'release/SHA256SUMS.txt').write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in outputs),encoding='utf-8')
for p in outputs:print(p.name,p.stat().st_size)
