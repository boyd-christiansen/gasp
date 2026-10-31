from pathlib import Path
from cadgen import export
import build123d as bd
from capture_enclosure import rear_shell,front_print,ripple_cover_print,table_base,cable_guide_print,dca_washer,carrier_washer,radar_washer,fit_coupon,assembly_20
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
 for name,func in [('rear_shell',rear_shell),('front_bezel',front_print),('ripple_cover',ripple_cover_print),('table_base',table_base),('cable_guide',cable_guide_print),('dca_washer_1p8',dca_washer),('carrier_washer_0p8',carrier_washer),('radar_washer_0p6',radar_washer),('fit_coupon',fit_coupon)]:
  doc=func()
  if name=='ripple_cover':
   # The viewer's fixed ~0.3-mm display tessellation is too coarse for this
   # shallow water surface. Export its actual B-rep at 0.02 mm for printing.
   export(doc,ROOT/'exports'/f'{name}.step')
   assert bd.export_stl(doc.shape,ROOT/'exports'/f'{name}.stl',tolerance=.02,angular_tolerance=.08)
   assert bd.export_gltf(doc.shape,ROOT/'exports/ripple_cover.glb',binary=True,linear_deflection=.02,angular_deflection=.08)
  else:export(doc,ROOT/'exports'/f'{name}.step',ROOT/'exports'/f'{name}.stl')
 doc=assembly_20()
 export(doc,ROOT/'exports/assembly_20_degrees.step')
 assert bd.export_gltf(doc.shape,ROOT/'exports/assembly_20_degrees.glb',binary=True,linear_deflection=.02,angular_deflection=.08)
