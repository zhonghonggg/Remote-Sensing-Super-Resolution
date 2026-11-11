param([string]$ISCC = "$PSScriptRoot\vendor\inno\ISCC.exe")
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (!(Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE) { throw 'Python 3.10 x64 required' }
}
$py = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
& $py -m pip install --no-index --find-links wheelhouse -r requirements-lock.txt
if ($LASTEXITCODE) { throw 'Dependencies failed' }
& $py collect_licenses.py
& $py tests\acceptance.py
if ($LASTEXITCODE) { throw 'Tests failed' }
& $py -m PyInstaller --noconfirm GeoSR.spec
if ($LASTEXITCODE) { throw 'PyInstaller failed' }
if (!(Test-Path -LiteralPath $ISCC)) { throw 'Provide installed Inno Setup 6 ISCC.exe using -ISCC path' }
& $ISCC installer.iss
if ($LASTEXITCODE) { throw 'Installer compilation failed' }
Get-FileHash -Algorithm SHA256 release\*.exe | ForEach-Object { "$($_.Hash)  $([IO.Path]::GetFileName($_.Path))" } | Set-Content -Encoding utf8 release\SHA256SUMS.txt
