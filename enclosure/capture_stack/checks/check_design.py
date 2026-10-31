"""Measure built B-reps, compare full vendor component envelopes, and aim poses."""
import sys,json,math
from pathlib import Path
from itertools import combinations
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import build123d as bd
from cadgen.geometry import closest_points,overlap_volume,is_sound,boundary_edges
import capture_enclosure as c
ROOT=Path(__file__).resolve().parents[1]
def world_parts(node,parent=None):
 here=(bd.Location() if parent is None else parent)*node.location
 if node.children:
  for child in node.children:yield from world_parts(child,here)
 else:yield node.located(here)
def find_part(tree,label):
 matches=[p for p in world_parts(tree) if p.label==label]
 if len(matches)!=1:raise ValueError((label,len(matches)))
 return matches[0]
def overlap(a,b):return sum(overlap_volume(sa,sb) for sa in a.solids() for sb in b.solids())
def bbox_may_overlap(a,b):
 aa=a.bounding_box();bb=b.bounding_box()
 return all(tuple(aa.min)[k]<tuple(bb.max)[k]-1e-6 and tuple(bb.min)[k]<tuple(aa.max)[k]-1e-6 for k in range(3))
def broadphase_regions(body,front=False):
 # Conservative feature prisms reduce empty-cavity Boolean work. Prove they
 # cover the ENTIRE actual B-rep first, so a later CAD edit cannot silently
 # add material outside this collision broadphase.
 if front:
  regions=[c.box(0,0,c.SEAM,180,180,3)]
  regions += [c.box(x,y,c.IC_BACK+c.IC_T,8,8,c.FRONT-c.IC_BACK-c.IC_T) for x,y in c.ic_holes()]
  regions += [c.box(x,y,c.AOP_BACK+c.AOP_T,6,6,c.FRONT-c.AOP_BACK-c.AOP_T) for x,y in c.aop_holes()]
 else:
  regions=[c.box(0,0,0,180,180,3)]
  for side in [-1,1]:
   regions.extend([c.box(side*83,0,0,14,180,c.SEAM),c.box(0,side*83,0,180,14,c.SEAM)])
   for y in [c.PIVOT_Y,c.PIVOT_Y-c.LOCK_R]:regions.append(c.box(side*91.6,y,23,8.8,18,18))
  regions += [c.box(x,y,2.8,10,10,c.DCA_BACK-2.8) for x,y in c.dca_holes()]
  regions += [c.box(x,y,2.8,12,12,c.SEAM-2.8) for x,y in c.CLOSURES]
 missing=body.cut(*regions)
 assert abs(missing.volume)<1e-5,('broadphase does not cover body',body.label,missing.volume)
 return regions
def main():
 rear=c.rear_shell().shape;front=c.front_bezel().shape;cover=c.ripple_cover().shape;base=c.table_base().shape
 guide=c.cable_guide().shape
 parts=[rear,front,cover,base,guide,c.dca_washer().shape,c.carrier_washer().shape,c.radar_washer().shape,c.fit_coupon().shape]
 report={'parts':{},'collisions':[],'checks':{},'poses':[],'limits':['Vendor component bodies use bounding envelopes; complete solder/connector detail is not modelled.','Physical printer fit, connector seating, stock ribbon bend/length, heat, RF and load performance remain untested.']}
 for p in parts:
  print('VALIDATING',p.label,flush=True)
  report['parts'][p.label]={'valid':p.is_valid,'sound':is_sound(p),'solids':len(p.solids()),'free_edges':sum(len(boundary_edges(s)) for s in p.shells()),'volume_mm3':p.volume,'bounds_mm':list(p.bounding_box().size)}
  assert p.is_valid and is_sound(p) and len(p.solids())==1
  assert not report['parts'][p.label]['free_edges']
 refs=c.board_references().shape
 regions={rear.label:broadphase_regions(rear),front.label:broadphase_regions(front,True),cover.label:[c.box(0,0,c.FRONT,180,180,20)]}
 assert abs(cover.cut(*regions[cover.label]).volume)<1e-5
 # Exact PCB volumes, including mounting holes, compared against enclosure.
 for name in ['PCB_ICBOOST_PROC074B','PCB_DCA1000_PROC048A','PCB_AOP_PROC091G']:
  p=find_part(refs,name)
  for e in [rear,front,cover]:
   v=overlap(p,e)
   if v>1e-5:report['collisions'].append([name,e.label,v])
 # Every source component envelope, not only the large display references.
 for n,lo,hi in c.reference_envelopes():
  if min(hi[i]-lo[i] for i in range(3))<=1e-5:continue
  p=c.component_box(n,lo,hi,'#333333')
  for e in [rear,front,cover]:
   if not any(bbox_may_overlap(p,r) for r in regions[e.label]):continue
   v=overlap(p,e)
   if v>1e-5:report['collisions'].append([n,e.label,v])
 print('VALIDATED all vendor component envelopes',flush=True)
 # Factory heatsink keepout behind chip.
 heat=find_part(refs,'AOP_heatsink_envelope')
 for e in [rear,front,cover]:
  v=overlap(heat,e)
  if v>1e-5:report['collisions'].append(['heatsink',e.label,v])
 report['checks']['shell_seam_overlap_mm3']=overlap(rear,front)
 report['checks']['shell_seam_contact_mm']=closest_points(rear,front).distance
 report['checks']['ripple_cover_contact_mm']=closest_points(cover,front).distance
 report['checks']['ripple_cover_overlap_mm3']=overlap(cover,front)+overlap(cover,rear)
 assert report['checks']['ripple_cover_contact_mm']<1e-5 and report['checks']['ripple_cover_overlap_mm3']<1e-5
 for holes,z,board_label,body in [(c.dca_holes(),c.DCA_BACK,'PCB_DCA1000_PROC048A',rear),(c.ic_holes(),c.IC_BACK+c.IC_T,'PCB_ICBOOST_PROC074B',front),(c.aop_holes(),c.AOP_BACK+c.AOP_T,'PCB_AOP_PROC091G',front)]:
  pcb=find_part(refs,board_label)
  for i,(x,y) in enumerate(holes):
   # Model support lands themselves contact board in their expected plane.
   radius=2.5 if 'AOP' in board_label else (4 if 'ICBOOST' in board_label else 5)
   land=c.cyl(x,y,z-.01,radius,.02)
   assert overlap(land,body)>0 and overlap(land,pcb)>0,(board_label,i,'support land')
 # The entire 15-mm package's +/-60-deg pyramid must clear printed front/rear.
 cx,cy=c.chip_xy();zchip=c.AOP_BACK+c.AOP_T+.964999
 h=30;half0=7.5;half1=half0+h*math.tan(math.radians(60))
 cone=bd.loft([bd.Pos(cx,cy,zchip)*bd.Rectangle(2*half0,2*half0),bd.Pos(cx,cy,zchip+h)*bd.Rectangle(2*half1,2*half1)])
 for e in [rear,front,cover]:
  v=overlap(cone,e);report['checks'][f'60_degree_aperture_{e.label}_mm3']=v
  if v>1e-5:report['collisions'].append(['60deg_aperture',e.label,v])
 # Through-holes permit each nominal fastener shaft; designed insert press-fit excluded.
 for x,y in c.dca_holes():assert overlap(c.cyl(x,y,-.2,1.5,24),rear)<1e-5
 for x,y in c.ic_holes():assert overlap(c.cyl(x,y,c.IC_BACK-.8,1.5,12),front)<1e-5
 for x,y in c.aop_holes():assert overlap(c.cyl(x,y,c.AOP_BACK+c.AOP_T,1,4),front)<1e-5
 # Side-loaded nuts must reach the lid traps without passing through plastic.
 for x,y in c.CLOSURES:
  n=c.nut_z(x,y,57.8,rotation=30)
  for offset in [0,2,5,10,15]:
   shifted=bd.Pos(0,-math.copysign(offset,y),0)*n
   assert overlap(shifted,rear)<1e-5,('nut loading',x,y,offset)
 for x,y in c.ic_holes():
  for offset in [0,2,5,10]:
   assert overlap(c.nut_z(x,y-offset,58.5,rotation=30),front)<1e-5,('hidden carrier nut loading',x,y,offset)
 # Cable guide pads contact, shafts clear both parts, nuts load from underneath.
 assert overlap(guide,base)<1e-5 and closest_points(guide,base).distance<1e-6
 for x in [-37,37]:
  shaft=c.cyl(x,c.GUIDE_Y,.5,1.5,12)
  assert overlap(shaft,guide)<1e-5 and overlap(shaft,base)<1e-5
  for z in [-3,0,3.2]:assert overlap(c.nut_z(x,c.GUIDE_Y,z),base)<1e-5
 # Nominal rear cable bundle passes without touching guide or foot.
 bundle=c.box(0,c.GUIDE_Y,6.5,48,28,11)
 assert overlap(bundle,base)<1e-5 and overlap(bundle,guide)<1e-5
 # Nominal axial stack calculation; solid bore gauges were checked above.
 def engage(a,b):return max(0,min(a[1],b[1])-max(a[0],b[0]))
 report['checks']['engagement_mm']={'DCA_M3x25':engage((c.DCA_BACK+c.DCA_T+1.8-25,c.DCA_BACK+c.DCA_T+1.8),(0,2.4)),'ICBOOST_M3x12':engage((c.IC_BACK-.8,c.IC_BACK-.8+12),(58.5,60.9)),'lid_M3x16':engage((c.FRONT+c.RIPPLE_PAD+.5-16,c.FRONT+c.RIPPLE_PAD+.5),(57.8,60.2)),'pivot_M3x16':engage((103-16,103),(87.2,89.6)),'guide_M3x12':engage((.5,12.5),(3.2,5.6)),'AOP_M2x6':engage((c.AOP_BACK-.6,c.AOP_BACK-.6+6),(c.AOP_BACK+c.AOP_T,c.AOP_BACK+c.AOP_T+4))}
 for k,v in report['checks']['engagement_mm'].items():assert v>= (3.5 if k.startswith('AOP') else 2.39),(k,v)
 # Check assembled plastic across endpoints and every locking position.
 for angle in c.ANGLES:
  r=c.pose(rear,angle);f=c.pose(front,angle);v=c.pose(cover,angle)
  rv,fv=overlap(r,base)+overlap(r,guide),overlap(f,base)+overlap(f,guide)+overlap(v,base)+overlap(v,guide)
  assert v.bounding_box().min.Y>-105 and v.bounding_box().max.Y<90
  b=r.bounding_box();q=c.pose(c.cyl(cx,cy,zchip,.01,.01),angle).bounding_box().center()
  report['poses'].append({'pitch':angle,'base_collision_mm3':rv+fv,'lowest_case_z':b.min.Z,'radar_height':q.Z,'case_y_extent':[b.min.Y,b.max.Y],'height_at_548p64mm_distance':q.Z+548.64*math.tan(math.radians(angle))})
  if rv+fv>1e-5:report['collisions'].append([f'pose_{angle}','base',rv+fv])
  assert b.min.Z>6
  assert b.min.Y>-105 and b.max.Y<90
  # Lock bores and pivot have a clear nominal 3-mm path through cheeks and case.
  for ly in [c.PIVOT_Y,c.PIVOT_Y-c.LOCK_R]:
   g=c.pose(c.xcyl(-104,ly,c.PIVOT_Z,1.5,208),angle)
   assert overlap(g,base)<1e-5 and overlap(g,r)<1e-5,(angle,'lock')
 # All case material stays within desk footprint at requested indexed poses.
 report['checks']['rear_front_contact_mm']=closest_points(rear,front).distance
 for x,y in c.CLOSURES:
  g=c.cyl(x,y,c.FRONT+c.RIPPLE_PAD+.5-16,1.5,16)
  assert all(overlap(g,p)<1e-5 for p in [rear,front,cover])
  w=c.cyl(x,y,c.FRONT+c.RIPPLE_PAD,3.5,.5)-c.cyl(x,y,c.FRONT+c.RIPPLE_PAD-.1,1.6,.7)
  assert overlap(w,cover)<1e-5 and closest_points(w,cover).distance<1e-5
 report['status']='PASS' if not report['collisions'] and report['checks']['shell_seam_overlap_mm3']<1e-5 else 'FAIL'
 (ROOT/'checks/design_report.json').write_text(json.dumps(report,indent=2))
 print(json.dumps(report,indent=2),flush=True)
 assert report['status']=='PASS'
if __name__=='__main__':main()
