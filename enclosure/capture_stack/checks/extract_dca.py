import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from inspect_vendor import dca_vendor
import build123d as bd
s=dca_vendor().shape

def parts(n,parent=None):
 here=(bd.Location() if parent is None else parent)*n.location
 if n.children:
  for c in n.children:yield from parts(c,here)
 else:yield n.located(here)
ps=list(parts(s));pcb=next(p for p in ps if p.label=='NAUO1')
cs=[]
for e in pcb.edges():
 if e.geom_type==bd.GeomType.CIRCLE and e.radius>1:
  c=e.arc_center
  v=[round(c.X,5),round(c.Y,5),round(c.Z,5),round(e.radius,5)]
  if v not in cs:cs.append(v)
print('CIRCLES',cs)
out={'source':'TI SPRR350A PROC048A vendor STEP','pcb_thickness':pcb.bounding_box().size.Z,'circles':cs,'components':[]}
for p in ps:
 b=p.bounding_box();out['components'].append({'name':p.label,'min':list(b.min),'max':list(b.max)})
 if b.size.Z>5 or b.min.Z < -5 or (b.size.Y>15 and b.size.X<25): print(p.label,'box',b)
(Path(__file__).resolve().parents[1]/'vendor/dca_geometry.json').write_text(json.dumps(out,indent=2))
