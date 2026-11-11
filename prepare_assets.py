from pathlib import Path
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parent
im=Image.new('RGBA',(256,256),(0,0,0,0));d=ImageDraw.Draw(im)
d.rounded_rectangle((8,8,248,248),radius=50,fill='#123b36')
d.polygon([(35,63),(91,43),(153,65),(207,45),(207,164),(153,184),(91,163),(35,183)],fill='#e4efe2')
d.line([(91,43),(91,163)],fill='#789d89',width=5);d.line([(153,65),(153,184)],fill='#789d89',width=5)
d.line([(39,143),(77,109),(111,127),(154,87),(196,101)],fill='#3c846c',width=9)
d.ellipse((119,115,204,200),fill='#f4c55c',outline='#123b36',width=9)
d.line((188,186,224,224),fill='#f4c55c',width=19)
d.line((142,157,180,157),fill='#123b36',width=8);d.line((161,138,161,176),fill='#123b36',width=8)
im.save(R/'assets/geosr.png');im.save(R/'assets/geosr.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
