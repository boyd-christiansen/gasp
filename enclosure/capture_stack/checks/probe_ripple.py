import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import build123d as bd
import capture_enclosure as c
s=c.ripple_cover_print().shape;cx,cy=c.chip_xy()
print('BOUNDS',s.bounding_box())
for r in [40,45,60,65,70,75,90,95,100,110,115,130]:
 x=cx-r;y=cy;e=bd.Edge.make_line((x,y,-1),(x,y,20))
 hits=e.intersect(s) or []
 zs=[v.center().Z for h in hits for v in h.vertices()]
 print(r,'expected',c.ripple_height(x,y),'actual',zs)
