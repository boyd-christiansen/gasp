import sys,json,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import capture_enclosure as c
from cadgen.geometry import overlap_volume
ROOT=Path(__file__).resolve().parents[1]
def overlap(a,b):return sum(overlap_volume(sa,sb) for sa in a.solids() for sb in b.solids())
def box_overlap(lo1,hi1,lo2,hi2):return math.prod(max(0,min(hi1[i],hi2[i])-max(lo1[i],lo2[i])) for i in range(3))
def main():
 env=c.reference_envelopes();ics=[e for e in env if e[0].startswith('IC_')];dcas=[e for e in env if e[0].startswith('DCA_')]
 report={'interboard_box_conflicts':[],'heatsink_box_conflicts':[],'tie_under_floor_conflicts':[],'plug_gauges_mm3':{},'assumptions':['Boot gauges are deliberately generic; confirm the actual cables.','The factory Samtec cable is not modeled: nominal endpoint displacement is a reach check, not a bend/termination verification.','External flexible cable bends and slack must be set by hand with the actual cables; tie heads stay outside.']}
 for a,al,ah in ics:
  for b,bl,bh in dcas:
   v=box_overlap(al,ah,bl,bh)
   if v>1e-4:report['interboard_box_conflicts'].append([a,b,v])
 cx,cy=c.chip_xy();hl=[cx-10.5,cy-10.5,c.AOP_BACK-4.5];hh=[cx+10.5,cy+10.5,c.AOP_BACK]
 for a,al,ah in ics:
  v=box_overlap(al,ah,hl,hh)
  if v>1e-4:report['heatsink_box_conflicts'].append([a,v])
 for x,y in c.CABLE_TIES:
  lo=[x-7.5,y-1.25,3];hi=[x+7.5,y+1.25,4.2]
  for name,el,eh in env:
   v=box_overlap(lo,hi,el,eh)
   if v>1e-4:report['tie_under_floor_conflicts'].append([x,y,name,v])
 rear=c.rear_shell().shape;front=c.front_bezel().shape;cover=c.ripple_cover().shape
 gauges=[('DCA_Ethernet_boot_18x34x17',c.box(46.707,-58.3,8,18,34,17)),('DCA_Ethernet_cable_exit',c.box(46.707,-88,13,7,28,7)),('ICBOOST_USB_1_boot',c.box(15.99,-48,44.5,12,23,8)),('ICBOOST_USB_2_boot',c.box(33.13,-48,44.5,12,23,8)),('carrier_power_boot',c.box(-55.45,-53.5,51.4,13,24,12)),('carrier_power_cable',c.box(-55.45,-83,54.5,6,35,6)),('DCA_power_top_exit',c.box(46.7,83,10,14,34,16)),('AOP_optional_USB_top_exit',c.box(43.48,83,51.3,12,34,8))]
 gauges.extend([('ICBOOST_USB_1_edge_boot',c.box(15.99,-90,44.5,12,14,8)),('ICBOOST_USB_2_edge_boot',c.box(33.13,-90,44.5,12,14,8))])
 for name,g in gauges:
  v=overlap(g,rear)+overlap(g,front)+overlap(g,cover);report['plug_gauges_mm3'][name]=v
 # Nominal centres of the source connector body envelopes.
 ic=next(e for e in ics if e[0].endswith('_J10'));dc=next(e for e in dcas if e[0]=='DCA_NAUO463')
 ip=[(ic[1][i]+ic[2][i])/2 for i in range(3)];dp=[(dc[1][i]+dc[2][i])/2 for i in range(3)]
 report['lvds_connector_body_centre_separation_mm']=math.dist(ip,dp)
 report['nominal_factory_cable_length_mm']=50.8
 report['status']='PASS' if not report['interboard_box_conflicts'] and not report['heatsink_box_conflicts'] and not report['tie_under_floor_conflicts'] and max(report['plug_gauges_mm3'].values())<1e-5 else 'FAIL'
 (ROOT/'checks/stack_and_cables_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
 assert report['status']=='PASS'
if __name__=='__main__':main()
