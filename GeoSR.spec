from PyInstaller.utils.hooks import collect_all, collect_submodules
datas=[('models/general-x4v3.onnx','models'),('assets/geosr.ico','assets'),('README.md','.'),('THIRD_PARTY_NOTICES.txt','.'),('licenses','licenses')]
binaries=[];hidden=[]
for package in ['rasterio','pyproj','onnxruntime']:
    d,b,h=collect_all(package);datas+=d;binaries+=b;hidden+=h
hidden+=collect_submodules('rasterio')
a=Analysis(['src/app.py'],pathex=['src'],binaries=binaries,datas=datas,hiddenimports=hidden,excludes=['onnx','torch','pytest','matplotlib'],noarchive=False)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='GeoSR',console=False,icon='assets/geosr.ico')
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='GeoSR')
