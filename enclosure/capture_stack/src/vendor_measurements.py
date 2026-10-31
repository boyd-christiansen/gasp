from pathlib import Path
import json
import build123d as bd
from cadgen import model,read_step
ROOT=Path(__file__).resolve().parents[1]
def world_parts(n,parent=None):
 here=(bd.Location() if parent is None else parent)*n.location
 if n.children:
  for c in n.children:yield from world_parts(c,here)
 else:yield n.located(here)
@model
def dca_pcb_reference():
 s=read_step(ROOT/'vendor/dca1000/sprr350/PROC048A_STEP.STEP')
 ps=list(world_parts(s));pcb=next(p for p in ps if p.label=='NAUO1')
 cs=[]
 for e in pcb.edges():
  if e.geom_type==bd.GeomType.CIRCLE and e.radius>1:
   c=e.arc_center
   v=[round(c.X,5),round(c.Y,5),round(c.Z,5),round(e.radius,5)]
   if v not in cs:cs.append(v)
 out={'source':'TI SPRR350A PROC048A vendor STEP','pcb_thickness':pcb.bounding_box().size.Z,'circles':cs,'components':[]}
 for p in ps:
  b=p.bounding_box();out['components'].append({'name':p.label,'min':list(b.min),'max':list(b.max)})
 print('MEASUREMENTS_JSON='+json.dumps(out))
 pcb.label='DCA1000_PCB'
 return pcb
if __name__=='__main__':dca_pcb_reference()
