"""Tabletop raw-ADC capture enclosure. All dimensions mm; angles degrees.

Cassette frame: +X right, +Y toward upper edge, +Z out through radar face.
World: +Z up, user is in -Y. Pitch is antenna boresight above horizontal.
Board references are vendor-derived envelopes, not complete PCB component CAD.
"""
import json, math
from pathlib import Path
import build123d as bd
from cadgen import model, memo
from water_profile import water_height_mm, _smootherstep
ROOT=Path(__file__).resolve().parents[1]
W=180.0; H=180.0; WALL=2.4; FLOOR=3.0
SEAM=62.5; FRONT=65.5
IC_BACK=50.0; IC_T=69.71*.0254; MATE=5.0
AOP_BACK=IC_BACK+IC_T+MATE; AOP_T=1.6256
DCA_BACK=21.5; DCA_T=1.5937484
# Match QSH J2 to QTH J4 using pad-pattern centre, rotation preserved.
IC_CX=35.0; IC_CY=67.31001016
AOP_DX=43.0905393; AOP_DY=-17.70356396
DCA_DX=-4.72800912; DCA_DY=60.89472145
PIVOT_Y=-5.0; PIVOT_Z=32.0; PIVOT_H=120.0; LOCK_R=36.0
ANGLES=(0,10,20,30,40)
CLOSURES=[(-80,-80),(80,-80),(-80,80),(80,80)]
M3_CLEAR=3.4; M3_NUT_AF=5.8; M3_NUT_H=2.8
M2_BORE=3.0
CORNER_R=14.0
BODY_COLOR='#343D46'; FACE_COLOR='#E7E3D8'
GUIDE_Y=65.0
CABLE_TIES=[(-55,-76),(25,-76),(46,-61),(46,77),(65,56),(65,-36)]
RIPPLE_XY_SCALE=1.35
RIPPLE_Z_SCALE=.55
RIPPLE_BACK=1.2
RIPPLE_PAD=3.2
RIPPLE_GRID=91

def data(name):return json.loads((ROOT/'vendor'/f'{name}_geometry.json').read_text())
def icxy(p):return (p[1]-IC_CY,IC_CX-p[0])
def dcaxy(p):return (p[1]+DCA_DX,DCA_DY-p[0])
def aopxy(p):return (-p[0]+AOP_DX,-p[1]+AOP_DY)
def ic_holes():return [icxy(h['xy']) for h in data('icboost')['holes'] if abs(h['diameter']-4.318)<.001]
def dca_holes():return [dcaxy(c[:2]) for c in data('dca')['circles'] if c[2]==0 and abs(c[3]-2.159)<.001]
def aop_holes():return [aopxy(h['xy']) for h in data('aop')['mounting_holes']]
def chip_xy():
 c=next(c for c in data('aop')['components'] if c['name']=='U2')
 return aopxy(((c['xmin']+c['xmax'])/2,(c['ymin']+c['ymax'])/2))
def box(x,y,z,dx,dy,dz):return bd.Pos(x,y,z)*bd.Box(dx,dy,dz,align=(bd.Align.CENTER,bd.Align.CENTER,bd.Align.MIN))
def cyl(x,y,z,r,h):return bd.Pos(x,y,z)*bd.Cylinder(r,h,align=(bd.Align.CENTER,bd.Align.CENTER,bd.Align.MIN))
def rr(x,y,z,w,h,t,r=3):return bd.Pos(x,y,z)*bd.extrude(bd.RectangleRounded(w,h,r),amount=t)
def hexcut(x,y,z,af,h,rotation=0):return bd.Pos(x,y,z)*bd.extrude(bd.RegularPolygon(af/math.sqrt(3),6,rotation=rotation),amount=h)
def xshape(s,x,y,z):return bd.Pos(x,y,z)*bd.Rot(0,90,0)*s
def xcyl(x,y,z,r,h):return xshape(cyl(0,0,0,r,h),x,y,z)
def xhex(x,y,z,af,h):return xshape(hexcut(0,0,0,af,h),x,y,z)
def yport(x,y,z,w,h,r=3):
 # Rounded port through a horizontal cassette edge (profile in XZ).
 return bd.Pos(x,y+6,z)*bd.Rot(90,0,0)*rr(0,0,0,w,h,12,r)
def arc_slot(cx,cy,z,r,start,end,width=4.5,depth=3.2):
 # A planar annular sector with semicircular ends, extruded through the face.
 pts=[(cx+r*math.cos(math.radians(a)),cy+r*math.sin(math.radians(a))) for a in (start,end)]
 outer=bd.CenterArc((cx,cy),r+width/2,start,end-start)
 inner=bd.CenterArc((cx,cy),r-width/2,end,start-end)
 e1=bd.Line(outer@1,inner@0);e2=bd.Line(inner@1,outer@0)
 face=bd.make_face(bd.Wire([outer,e1,inner,e2]))
 s=bd.Pos(0,0,z)*bd.extrude(face,amount=depth)
 for x,y in pts:s+=cyl(x,y,z,width/2,depth)
 return s
def finish(s,name,color):
 assert s.is_valid and len(s.solids())==1 and s.volume>0,(name,len(s.solids()))
 s.label=name;s.color=color;return s

def pose(s,angle):return bd.Pos(0,0,PIVOT_H)*bd.Rot(90-angle,0,0)*bd.Pos(0,-PIVOT_Y,-PIVOT_Z)*s

def ripple_height(x,y):
 cx,cy=chip_xy();r=math.hypot(x-cx,y-cy)
 # Original solid water-impact profile; soften only the transition to the
 # enclosure's perimeter. The central jet is removed by the radar opening.
 edge=min(90-abs(x),90-abs(y))
 fade=_smootherstep((edge-3)/13)
 h=RIPPLE_BACK+RIPPLE_Z_SCALE*water_height_mm(max(r,20)/RIPPLE_XY_SCALE)*fade
 # Flat seating lands let the original corner fasteners clamp both layers.
 for px,py in CLOSURES:
  d=math.hypot(x-px,y-py)
  blend=1-_smootherstep((d-6)/6)
  h=h*(1-blend)+(RIPPLE_PAD+.2)*blend
 return h

@memo
def ripple_blank():
 points=[]
 for j in range(RIPPLE_GRID):
  y=-90+j*180/(RIPPLE_GRID-1)
  points.append([(x,y,ripple_height(x,y)) for x in [-90+i*180/(RIPPLE_GRID-1) for i in range(RIPPLE_GRID)]])
 top=bd.Face.make_surface_from_array_of_points(points,tol=.03,min_deg=3,max_deg=3)
 solid=bd.extrude(top,amount=-25,dir=(0,0,1))
 assert solid.is_valid and len(solid.solids())==1,('ripple extrude',solid.is_valid,len(solid.solids()))
 # Flatten the back and trim the sculpture to the existing rounded perimeter.
 solid=solid&rr(0,0,0,W,H,20,CORNER_R)
 assert solid.is_valid and len(solid.solids())==1,('ripple trim',solid.is_valid,len(solid.solids()))
 return solid

def ripple_vent_tools(z,depth):
 cx,cy=chip_xy();tools=[]
 for radius,ranges in [
  (54,[(70,141),(164,195),(218,290)]),
  (82.35,[(70,290)]),
  (105.3,[(132,190),(224,232)]),
  (122,[(145,200)])]:
  for start,end in ranges:tools.append(arc_slot(cx,cy,z,radius,start,end,4.5,depth))
 return tools

@model
def ripple_cover():
 s=bd.Pos(0,0,FRONT)*ripple_blank()
 cx,cy=chip_xy()
 # Flare above the structural face; preserve the full antenna view through
 # the extra relief depth instead of leaving a deep straight-sided window.
 aperture=bd.loft([
  bd.Pos(cx,cy,FRONT-.1)*bd.RectangleRounded(42,44,3),
  bd.Pos(cx,cy,FRONT+20)*bd.RectangleRounded(42+40*math.tan(math.radians(60)),44+40*math.tan(math.radians(60)),3)])
 s=s.cut(aperture,*ripple_vent_tools(FRONT-.1,21))
 assert s.is_valid and len(s.solids())==1,('ripple openings',s.is_valid,len(s.solids()))
 s-=rr(-55,-47.5,FRONT-.1,21,45,21,3)
 s-=rr(AOP_DX,-84,FRONT-.1,18,20,21,3)
 assert s.is_valid and len(s.solids())==1,('ripple ports',s.is_valid,len(s.solids()))
 for x,y in CLOSURES:
  s-=cyl(x,y,FRONT+RIPPLE_PAD,4.1,21)
  assert s.is_valid and len(s.solids())==1,('ripple pad seat',x,y,s.is_valid,len(s.solids()))
  s-=cyl(x,y,FRONT-.1,1.7,21)
 return finish(s,'sculpted_water_ripple_cover',FACE_COLOR)

@model
def ripple_cover_print():
 s=bd.Pos(0,0,-FRONT)*ripple_cover().shape
 s.label='ripple_cover_print_flat_back_down';return s

@model
def rear_shell():
 outer=rr(0,0,0,W,H,SEAM,CORNER_R)
 outer=bd.fillet(outer.faces().sort_by(bd.Axis.Z)[0].edges(),radius=1.5)
 s=outer-rr(0,0,FLOOR,W-2*WALL,H-2*WALL,SEAM,CORNER_R-WALL)
 # Dedicated rounded ports retain the top/bottom walls between the cables.
 s-=yport(46.7,-90,17.5,24,23) # Ethernet boot / lead
 s-=yport(24.56,-90,48.5,35,14) # paired carrier USB
 s-=yport(-55.45,-90,58,16,13) # carrier power, open at seam
 s-=yport(46.7,90,18,20,22) # DCA power
 s-=yport(43.48,90,55.3,18,13) # optional radar USB
 s-=xshape(rr(0,0,0,17,34,10,3),85,-14,23.5)
 # Side vents stay outside the pivot and indexed locking bosses.
 for side in [-1,1]:
  for y,length in [(14,24),(25,31),(36,36),(47,31),(58,24)]:
   s-=xshape(rr(0,0,0,length,4.5,10,2),84 if side>0 else -94,y,31)
 # Rear vents avoid standoff roots and nut pockets.
 for x in [-70,-56,-42,-28,-14,0,14,28,42,56,70]:
  if any(abs(x-hx)<11 and abs(hy)<31 for hx,hy in dca_holes()):continue
  s-=rr(x,0,-.1,5,48,3.2,2)
 # DCA supports: screws M3x25 through 1.8-mm printed washers.
 for x,y in dca_holes():
  s+=cyl(x,y,2.8,5,18.7)
  s-=cyl(x,y,-.1,1.7,22)
  s-=hexcut(x,y,-.1,M3_NUT_AF,2.9)
 # Lid columns join the rear floor and corner walls.
 for x,y in CLOSURES:
  s+=cyl(x,y,2.8,6,SEAM-2.8)
  s+=box(x+(3 if x>0 else -3),y,2.8,12,7,SEAM-2.8)&outer
  s-=cyl(x,y,53,1.7,11)
  s-=hexcut(x,y,57.8,M3_NUT_AF,2.8,rotation=30)
  # Side entry toward the centre; nut is installed before boards.
  s-=box(x,y-(3 if y>0 else -3),57.8,6.0,12,2.8)
 # Trunnions and locking points, with captive nuts on the inside.
 for side in [-1,1]:
  for y in [PIVOT_Y,PIVOT_Y-LOCK_R]:
   start=87.2 if side>0 else -96.0
   s+=xcyl(start,y,PIVOT_Z,9,8.8)
   s-=xcyl(-97,y,PIVOT_Z,1.7,194)
   if side>0:s-=xhex(87.2,y,PIVOT_Z,M3_NUT_AF,3.1)
   else:s-=xhex(-90.3,y,PIVOT_Z,M3_NUT_AF,3.1)
 # Purchased 2.5-mm ties; paired pass-through slots.
 for cx,cy in CABLE_TIES:
  for dx in [-6,6]:s-=box(cx+dx,cy,-.1,3.0,3.8,3.2)
 return finish(s,'rear_shell',BODY_COLOR)

@model
def front_bezel():
 s=rr(0,0,SEAM,W,H,3,CORNER_R)
 s=bd.fillet(s.faces().sort_by(bd.Axis.Z)[-1].edges(),radius=1.2)
 cx,cy=chip_xy();s-=rr(cx,cy,SEAM-.1,42,44,3.2,3)
 # Vent paths match the sculpted cover exactly through both front layers.
 s=s.cut(*ripple_vent_tools(SEAM-.1,3.2))
 # Power jack and AOP USB access are open through the lower edge.
 s-=rr(-55,-47.5,SEAM-.1,21,45,3.2,3)
 s-=rr(AOP_DX,-84,SEAM-.1,18,20,3.2,3)
 # ICBOOST hangs from the front on four accurately located standoffs.
 # M3x12 enters from PCB back; side-loaded nuts are hidden behind the face.
 for x,y in ic_holes():
  s+=cyl(x,y,IC_BACK+IC_T,3.4,4.1)
  s+=cyl(x,y,IC_BACK+IC_T+4,4,FRONT-IC_BACK-IC_T-4)
  s-=cyl(x,y,IC_BACK+IC_T-.1,1.7,10)
  s-=hexcut(x,y,58.5,M3_NUT_AF,2.8,rotation=30)
  s-=box(x,y-4,58.5,6,8,2.8)
 # AOP screws enter from behind the radar PCB before ICBOOST is mated.
 for x,y in aop_holes():
  s+=cyl(x,y,AOP_BACK+AOP_T,2.5,.8)
  s+=cyl(x,y,AOP_BACK+AOP_T+.8,3.0,FRONT-(AOP_BACK+AOP_T+.8))
  s-=cyl(x,y,AOP_BACK+AOP_T-.1,M2_BORE/2,4.3)
  s-=cyl(x,y,AOP_BACK+AOP_T-.1,1.15,6.2)
 for x,y in CLOSURES:
  s-=cyl(x,y,SEAM-.1,1.7,3.2)
  s-=cyl(x,y,FRONT-.8,3.8,.9)
 return finish(s,'front_bezel_open_radar',FACE_COLOR)

@model
def table_base():
 s=rr(0,-7.5,0,214,195,6,20)
 s=bd.fillet(s.faces().sort_by(bd.Axis.Z)[-1].edges(),radius=2)
 # Cheeks printed upright with base, side holes parallel to X.
 def crown_tangent(y,sign):
  z=5-PIVOT_H;r=18;d2=y*y+z*z;k=r*math.sqrt(d2-r*r)/d2
  return (r*r*y/d2+sign*k*(-z),PIVOT_H+r*r*z/d2+sign*k*y)
 right=crown_tangent(44,1);left=crown_tangent(-50,-1)
 profile=bd.make_face(bd.Wire([
  bd.Line((-50,5),(44,5)),
  bd.Line((44,5),right),
  bd.ThreePointArc(right,(0,138),left),
  bd.Line(left,(-50,5))]))
 # Make local XY sketch (Y,Z of world), extrude into world X.
 for side in [-1,1]:
  p=bd.extrude(profile,amount=6)
  p=bd.fillet(p.faces().filter_by(bd.Axis.Z).edges(),radius=1)
  p=bd.Pos(96.5 if side>0 else -102.5,0,0)*bd.Rot(0,0,90)*bd.Rot(90,0,0)*p
  s+=p
  # A continuous tapered heel replaces the exposed triangular fins.
  heel=bd.extrude(bd.Polygon((102.3,4),(106.8,4),(102.3,70),align=None),amount=88)
  heel=bd.Pos(0,43,0)*bd.Rot(90,0,0)*heel
  clip=bd.Pos(101.8,0,0)*bd.Rot(0,0,90)*bd.Rot(90,0,0)*bd.extrude(profile,amount=6)
  heel=heel&clip
  if side<0:heel=bd.mirror(heel,about=bd.Plane.YZ)
  s+=heel
  s-=bd.Pos(-108,-4,40)*bd.Rot(0,0,90)*bd.Rot(90,0,0)*rr(0,0,0,48,38,216,16)
  s-=xcyl(-104,0,PIVOT_H,1.7,208)
  for a in ANGLES:
   y=-LOCK_R*math.sin(math.radians(a));z=PIVOT_H-LOCK_R*math.cos(math.radians(a))
   s-=xcyl(-104,y,z,1.7,208)
 # Recessed angle markings on the outside of the right cheek.
 for a in ANGLES:
  y=-LOCK_R*math.sin(math.radians(a));z=PIVOT_H-LOCK_R*math.cos(math.radians(a))
  # Recessed numbers stay below the arc, clear of screw heads.
  ly=6-46*math.sin(math.radians(a));lz=PIVOT_H-46*math.cos(math.radians(a))
  segments={'0':'abcedf','1':'bc','2':'abged','3':'abgcd','4':'fgbc'}
  bars={'a':(0,1.5,1.6,.35),'g':(0,0,1.6,.35),'d':(0,-1.5,1.6,.35),'f':(-.8,.75,.35,1.15),'b':(.8,.75,.35,1.15),'e':(-.8,-.75,.35,1.15),'c':(.8,-.75,.35,1.15)}
  digits=str(a)
  for di,digit in enumerate(digits):
   for key in segments[digit]:
    u,v,w,h=bars[key]
    cut=box(102.3,ly+u+(di-(len(digits)-1)/2)*2.5,lz+v-h/2,.6,w,h)
    assert abs((s&cut).volume-.5*w*h)<1e-5,('angle marking clipped',a,digit,key)
    s-=cut
 # Rear cable-guide pads and captive nuts. Guide is removable around plugs.
 for x in [-37,37]:
  s+=rr(x,GUIDE_Y,5.9,16,18,3.1,3)
  s-=cyl(x,GUIDE_Y,-.1,1.7,9.2)
  s-=hexcut(x,GUIDE_Y,-.1,M3_NUT_AF,5.7)
 return finish(s,'table_base_0_10_20_30_40_degrees',BODY_COLOR)

@model
def cable_guide():
 # A 52 x 12-mm clear pass-through above the foot; screws land on base pads.
 s=rr(0,GUIDE_Y,18,64,18,3,4)
 for side in [-1,1]:
  s+=rr(side*29,GUIDE_Y,9,6,18,10,2)
  s+=rr(side*37,GUIDE_Y,9,16,18,3,3)
  s-=cyl(side*37,GUIDE_Y,8.9,1.7,3.2)
 return finish(s,'removable_rear_cable_guide',BODY_COLOR)

@model
def cable_guide_print():
 s=bd.Pos(0,21,9-GUIDE_Y)*bd.Rot(90,0,0)*cable_guide().shape
 s.label='cable_guide_print_rear_edge_down';return s

def washer(od,id,h,name):return finish(cyl(0,0,0,od/2,h)-cyl(0,0,-.1,id/2,h+.2),name,'#E4C375')
@model
def dca_washer():return washer(7,3.4,1.8,'DCA_washer_1p8')
@model
def carrier_washer():return washer(7,3.4,.8,'ICBOOST_washer_0p8')
@model
def radar_washer():return washer(4.4,2.3,.6,'AOP_washer_0p6')
@model
def fit_coupon():
 s=rr(0,0,0,52,25,6,3)
 for x,d in [(-17,2.9),(-8,3.0),(1,3.1)]:s-=cyl(x,0,1.8,d/2,4.3)
 s-=hexcut(16,0,3.2,5.8,2.9);s-=cyl(16,0,-.1,1.7,6.2)
 return finish(s,'fit_coupon_M2_2p9_3p0_3p1_M3_nut','#E4C375')

# Lightweight reference geometry. Mounts and PCB holes are exact source values;
# component boxes are mechanical keep-outs, not a claim about RF/thermal performance.
def component_box(name,lo,hi,color):
 s=box((lo[0]+hi[0])/2,(lo[1]+hi[1])/2,lo[2],hi[0]-lo[0],hi[1]-lo[1],hi[2]-lo[2])
 s.label=name;s.color=color;return s

def reference_envelopes():
 out=[]
 # ICBOOST in rotated board coordinates.
 d=data('icboost')
 for i,c in enumerate(d['components']):
  if c['height']<=.2:continue
  corners=[icxy(c['min']),icxy(c['max'])];lo=[min(p[k] for p in corners) for k in [0,1]];hi=[max(p[k] for p in corners) for k in [0,1]]
  z=IC_BACK+IC_T if c['layer']=='TOP' else IC_BACK-c['height']
  out.append((f"IC_{i}_{c['name']}",lo+[z],hi+[z+c['height']]))
 d=data('dca')
 for c in d['components'][1:]:
  corners=[dcaxy(c['min'][:2]),dcaxy(c['max'][:2])]
  lo=[min(p[k] for p in corners) for k in [0,1]]+[DCA_BACK+c['min'][2]]
  hi=[max(p[k] for p in corners) for k in [0,1]]+[DCA_BACK+c['max'][2]]
  out.append((f"DCA_{c['name']}",lo,hi))
 d=data('aop')
 for i,c in enumerate(d['components']):
  corners=[aopxy((c['xmin'],c['ymin'])),aopxy((c['xmax'],c['ymax']))]
  lo=[min(p[k] for p in corners) for k in [0,1]];hi=[max(p[k] for p in corners) for k in [0,1]]
  z=AOP_BACK+AOP_T if c['layer']=='TOP' else AOP_BACK-c['height']
  out.append((f"AOP_{i}_{c['name']}",lo+[z],hi+[z+c['height']]))
 return out

@model
def board_references():
 parts=[]
 s=box(0,0,IC_BACK,134.62002032,70,IC_T)
 for h in data('icboost')['holes']:
  x,y=icxy(h['xy']);s-=cyl(x,y,IC_BACK-.1,h['diameter']/2,IC_T+.2)
 s.label='PCB_ICBOOST_PROC074B';s.color='#A63737';parts.append(s)
 s=box(45+DCA_DX,DCA_DY-51,DCA_BACK,90,102,DCA_T)
 for c in data('dca')['circles']:
  if c[2]!=0:continue
  x,y=dcaxy(c[:2]);s-=cyl(x,y,DCA_BACK-.1,c[3],DCA_T+.2)
 s.label='PCB_DCA1000_PROC048A';s.color='#197C69';parts.append(s)
 s=bd.Pos(0,0,AOP_BACK)*bd.extrude(bd.Polygon(*[aopxy(p) for p in data('aop')['outline']],align=None),amount=AOP_T)
 for h in data('aop')['mounting_holes']:
  x,y=aopxy(h['xy']);s-=cyl(x,y,AOP_BACK-.1,h['diameter']/2,AOP_T+.2)
 s.label='PCB_AOP_PROC091G';s.color='#BC4940';parts.append(s)
 for n,lo,hi in reference_envelopes():
  size=[hi[k]-lo[k] for k in range(3)]
  if max(size[:2])<7 and size[2]<3:continue
  parts.append(component_box(n,lo,hi,'#3A3E40' if not n.endswith('U2') else '#C2BFA4'))
 # Factory thermal solution reserved behind the antenna; verify installed revision.
 cx,cy=chip_xy();parts.append(component_box('AOP_heatsink_envelope',[cx-10.5,cy-10.5,AOP_BACK-4.5],[cx+10.5,cy+10.5,AOP_BACK],'#303537'))
 return bd.Compound(children=parts,label='electronics_vendor_references')

def metal(s,name):s.label=name;s.color='#A9AFB2';return s
def nut_z(x,y,z,rotation=0):return metal(hexcut(x,y,z,5.5,2.4,rotation)-cyl(x,y,z-.1,1.5,2.6),'M3_nut_schematic')
def screw_z(x,y,seat,length,reverse=False):
 # Shaft below head seat by default. Smooth nominal shank, threads schematic.
 s=cyl(0,0,-length,1.5,length)+cyl(0,0,0,2.75,3)
 if reverse:s=bd.Rot(180,0,0)*s
 return metal(bd.Pos(x,y,seat)*s,f'M3x{length}_screw')

def cassette_parts(include_hardware=True):
 ps=[rear_shell().shape,front_bezel().shape,ripple_cover().shape,board_references().shape]
 for x,y in dca_holes():
  w=bd.Pos(x,y,DCA_BACK+DCA_T)*dca_washer().shape;ps.append(w)
  if include_hardware:ps.extend([nut_z(x,y,0),screw_z(x,y,DCA_BACK+DCA_T+1.8,25)])
 for x,y in ic_holes():
  w=bd.Pos(x,y,IC_BACK-.8)*carrier_washer().shape;ps.append(w)
  if include_hardware:ps.extend([nut_z(x,y,58.5,rotation=30),screw_z(x,y,IC_BACK-.8,12,True)])
 for x,y in aop_holes():
  ps.append(bd.Pos(x,y,AOP_BACK-.6)*radar_washer().shape)
  if include_hardware:
   ins=cyl(x,y,AOP_BACK+AOP_T,1.6,4)-cyl(x,y,AOP_BACK+AOP_T-.1,1,4.2)
   ps.append(metal(ins,'M2_heat_insert_nominal_interference_fit'))
   m2=cyl(0,0,0,1,6)+cyl(0,0,-1.4,1.9,1.4)
   ps.append(metal(bd.Pos(x,y,AOP_BACK-.6)*m2,'M2x6_screw'))
 if include_hardware:
  for x,y in CLOSURES:
   ps.append(nut_z(x,y,57.8,rotation=30));ps.append(screw_z(x,y,FRONT+RIPPLE_PAD+.5,16))
   ps.append(metal(cyl(x,y,FRONT+RIPPLE_PAD,3.5,.5)-cyl(x,y,FRONT+RIPPLE_PAD-.1,1.6,.7),'M3_flat_washer'))
 return ps

def assembly_body(angle):
 ps=[table_base().shape,cable_guide().shape,pose(bd.Compound(children=cassette_parts(),label='tilting_capture_cassette'),angle)]
 for x in [-37,37]:
  ps.extend([nut_z(x,GUIDE_Y,3.2),screw_z(x,GUIDE_Y,12.5,12)])
  ps.append(metal(cyl(x,GUIDE_Y,12,3.5,.5)-cyl(x,GUIDE_Y,11.9,1.6,.7),'M3_cable_guide_washer'))
 for ylocal in [PIVOT_Y,PIVOT_Y-LOCK_R]:
  for side in [-1,1]:
   # Nuts load from inside of shell; screws from outside stand cheeks.
   n=nut_z(0,0,0);n=bd.Rot(0,90,0)*n
   n=bd.Pos(87.2 if side>0 else -89.6,ylocal,PIVOT_Z)*n
   ps.append(pose(n,angle))
   yz=pose(cyl(0,ylocal,PIVOT_Z,.01,.01),angle).bounding_box().center()
   screw=screw_z(0,0,0,16)
   screw=bd.Rot(0,90*side,0)*screw
   screw=bd.Pos(side*103,yz.Y,yz.Z)*screw;ps.append(screw)
   w=xcyl(102.5 if side>0 else -103,yz.Y,yz.Z,3.5,.5)-xcyl(102.4 if side>0 else -103.1,yz.Y,yz.Z,1.6,.7)
   ps.append(metal(w,'M3_pivot_lock_washer'))
 return bd.Compound(children=ps,label=f'capture_enclosure_aim_{angle}_degrees')
@model
def assembly_20():return assembly_body(20)
@model
def assembly_0():return assembly_body(0)
@model
def assembly_40():return assembly_body(40)
@model
def front_print():
 s=bd.Pos(0,0,FRONT)*bd.Rot(180,0,0)*front_bezel().shape
 s.label='front_bezel_print_outer_face_down';return s

@model
def service_view():
 refs=board_references().shape
 rear_parts=[rear_shell().shape]
 front_parts=[front_bezel().shape,bd.Pos(0,0,25)*ripple_cover().shape]
 for part in refs.children:
  if part.label.startswith(('PCB_DCA','DCA_')):rear_parts.append(part)
  else:front_parts.append(part)
 back=bd.Compound(children=rear_parts,label='rear_shell_and_DCA')
 front=bd.Pos(0,0,95)*bd.Compound(children=front_parts,label='front_AOP_ICBOOST_exploded_offset_95mm')
 return bd.Compound(children=[back,front],label='exploded_assembly_illustration_do_not_print')

@model
def print_parts():
 parts=[rear_shell().shape,bd.Pos(200,0,FRONT)*bd.Rot(180,0,0)*front_bezel().shape,bd.Pos(0,220,0)*table_base().shape]
 for i in range(4):parts.append(bd.Pos(120+i*10,120,0)*dca_washer().shape)
 for i in range(4):parts.append(bd.Pos(120+i*10,135,0)*carrier_washer().shape)
 for i in range(2):parts.append(bd.Pos(120+i*10,150,0)*radar_washer().shape)
 parts.append(bd.Pos(150,180,0)*fit_coupon().shape)
 parts.append(bd.Pos(200,240,0)*cable_guide_print().shape)
 parts.append(bd.Pos(400,0,0)*ripple_cover_print().shape)
 return bd.Compound(children=parts,label='all_printed_parts_separate_plates_required')
if __name__=='__main__':
 assembly_20();print_parts();front_print();service_view();cable_guide_print();ripple_cover_print()
