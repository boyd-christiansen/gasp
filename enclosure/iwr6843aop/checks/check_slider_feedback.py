"""Focused rigid-geometry checks following the first physical slider test."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build123d as bd
import enclosure_v2 as v
from check_fit import intersection


def main():
    rear = v.rear_v2().shape
    front = v.front_v2().shape
    hook = bd.Compound(children=front.intersect(v.e.box(23.1, 50, 10.9, 2.2, 4, 1.6)))
    ledge = bd.Compound(children=rear.intersect(v.e.box(23, 50, 12.5, 2, 4, 1.6)))
    result = {
        'scope': 'Rigid CAD only; no printed flex, friction, wear or arbitrary motion-path proof.',
        'hook_top_z_mm': hook.bounding_box().max.Z,
        'ledge_underside_z_mm': ledge.bounding_box().min.Z,
        'nominal_lift_clearance_mm': ledge.bounding_box().min.Z - hook.bounding_box().max.Z,
        'full_cover_lateral_motion_overlap_mm3': {},
        'full_cover_lift_overlap_mm3': {},
    }
    for dx in (-.6, -.4, .4, .6):
        result['full_cover_lateral_motion_overlap_mm3'][str(dx)] = intersection(
            bd.Pos(dx, 0, 0) * front, rear)
    for dz in (.2, .4, 1):
        result['full_cover_lift_overlap_mm3'][str(dz)] = intersection(
            bd.Pos(0, 0, dz) * front, rear)
    for dx in (-2.4, 0):
        coupon_front = v.print_flip(v.slider_front_coupon().shape, v.e.FRONT_OUTER)
        result['single_coupon_lift_1mm_at_x_' + str(dx)] = intersection(
            bd.Pos(dx, 0, 1) * coupon_front, v.slider_rear_coupon().shape)
    out = Path(__file__).with_name('slider_feedback_report.json')
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
