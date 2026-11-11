exec((__import__('pathlib').Path(__file__).parent/'acceptance.py').read_text(encoding='utf-8').split("if '--cpu-only' not in sys.argv:")[0])
def edge():
    # NoData is optional: a valid black pixel must remain opaque.
    a=make('有效黑像元.tif',size=32)
    with rasterio.open(a,'r+') as s:s.nodata=None
    p=Runner(Config(str(a),str(T/'black'),.5,True,32,1,32),factory=lambda d:Fake2()).run()
    with rasterio.open(p) as d:assert d.read(4).min()==255
    assert p.read_bytes()[2:4]==b'+\x00' # little-endian BigTIFF version 43
    # Fail after one successful batch: completed area must remain untouched.
    a=make('保留已完成.tif',size=96);seen=[];events=[]
    class Intermittent:
        def __init__(self,dev):self.dev=dev
        def run(self,_,inputs):
            x=inputs['input']
            if self.dev=='DirectML' and seen:raise RuntimeError('injected later GPU failure')
            seen.append(self.dev)
            return [np.repeat(np.repeat(x,4,2),4,3)]
    r=Runner(Config(str(a),str(T/'preserved'),.5,False,32,1,32),lambda *e:events.append(e),factory=Intermittent)
    r.run();assert len(seen)==9 and seen[0]=='DirectML' and seen[1:] == ['CPU']*8
    assert r.completed==96*96
    perc=[e[1] for e in events];assert perc==sorted(perc)
    # Cancellation during final validation cannot publish a formal result.
    ev=threading.Event();dest=T/'latecancel'
    def cb(*e):
        if e[0]=='校验':ev.set()
    try:Runner(Config(str(a),str(dest),.5,True,32,1,32),cb,ev,lambda d:Fake2()).run()
    except Cancelled:pass
    else:raise AssertionError('late cancel')
    assert not list(dest.iterdir())
class Fake2:
    def run(self,_,d):return [np.repeat(np.repeat(d['input'],4,2),4,3)]
test('有效黑像元/BigTIFF/已完成块沿用/校验时取消',edge)
(T/'edge-cases.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
