from pathlib import Path
import json
import build123d as bd
from cadgen import model,read_step
ROOT=Path(__file__).resolve().parents[1]
@model
def dca_vendor():
 s=read_step(ROOT/'vendor/dca1000/sprr350/PROC048A_STEP.STEP')
 print('ROOT',s.label,s.bounding_box())
 def walk(s,parent=None):
  here=(bd.Location() if parent is None else parent)*s.location
  if s.children:
   for c in s.children:yield from walk(c,here)
  else:yield s.located(here)
 out=[]
 for p in walk(s):
  b=p.bounding_box(); out.append({'name':p.label,'min':list(b.min),'max':list(b.max),'vol':p.volume})
 print(json.dumps(out))
 s.label='DCA1000_vendor_reference'
 return s
if __name__=='__main__':dca_vendor()
