"""Validate reinforced board saddles, the mount roof and existing mating parts."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build123d as bd
from cadgen.geometry import closest_points, overlap_volume, is_sound, boundary_edges
from check_fit import world_parts, find_part, intersection
import enclosure as e
import enclosure_v1_2 as v2
import enclosure_v1_3 as v3
import desktop_dock as d

ROOT = Path(__file__).resolve().parents[1]


def main():
    rear = v3.rear_reinforced().shape
    old = v2.rear_standard_ties().shape
    kit = v3.assembly_v1_3().shape
    pcb = find_part(kit, 'pcb_PROC091G')
    result = {'part': {}, 'saddles': [], 'interferences_mm3': {}, 'measurements_mm': {},
              'limits': ['User reported a fragile v1.2 PLA edge saddle and difficult automatic tree-support removal.',
                         'This revised geometry has not yet been physically printed, load tested or sliced for a specific printer.',
                         'Board and component references remain conservative envelopes from the earlier design.']}
    for p in [rear, v3.rear_reinforced_print().shape]:
        assert p.is_valid and is_sound(p) and len(p.solids()) == 1 and p.volume > 0
        assert sum(len(boundary_edges(sh)) for sh in p.shells()) == 0
    result['part'] = {'valid': True, 'sound': True, 'solids': 1, 'free_edges': 0,
                      'bounds_mm': list(rear.bounding_box().size), 'volume_mm3': rear.volume}
    for part in world_parts(kit):
        if part.label == rear.label:
            continue
        volume = intersection(rear, part)
        result['interferences_mm3'][part.label] = volume
        assert volume < 1e-5, (part.label, volume)
    assert intersection(rear, e.front_open_aperture().shape) < 1e-5
    assert closest_points(rear, e.front_radome().shape).distance < 1e-5
    for x, y in v3.SADDLES:
        saddle = v3.reinforced_saddle(x, y)
        assert abs(saddle.cut(*rear.solids()).volume) < 1e-5
        contact = closest_points(saddle, pcb).distance
        assert contact < 1e-5
        section = bd.Compound(children=saddle.intersect(e.box(x, y, e.PCB_BACK - .8, 25, 25, .5)))
        bounds = section.bounding_box().size
        assert abs(bounds.X - 2.8) < 1e-5 and abs(bounds.Y - 6) < 1e-5
        assert abs(saddle.bounding_box().max.Z - e.PCB_BACK) < 1e-6
        result['saddles'].append({'original_xy': [x, y], 'measured_upper_width_mm': bounds.X,
            'measured_upper_length_mm': bounds.Y, 'root_bounds_mm': list(saddle.bounding_box().size),
            'pcb_contact_mm': contact, 'top_height_mm': saddle.bounding_box().max.Z})
    # The only removed geometry is the explicit support-reducing bore roof.
    removed = old.cut(*rear.solids())
    assert abs(removed.cut(*v3.mount_roof_relief().solids()).volume) < 1e-5
    result['removed_only_mount_roof_mm3'] = removed.volume
    # Prove the rest of the new material lies only in the four saddle volumes.
    added = rear.cut(*old.solids())
    assert abs(added.cut(*[v3.reinforced_saddle(x, y) for x, y in v3.SADDLES]).volume) < 1e-5
    result['added_only_saddle_material_mm3'] = added.volume
    for x in [e.USB_X - 3.6, e.USB_X + 3.6]:
        assert intersection(rear, e.box(x, -74, e.HEEL_BACK - 1, 2.8, 3.4, 7 - e.HEEL_BACK)) < 1e-6
    # Full nominal 1/4-inch stud still clears the mount entrance and nut axis.
    gauge = e.along_y(bd.Cylinder(6.35 / 2, 23, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)), 0, -66, e.NUT_Z)
    assert intersection(rear, gauge) < 1e-6
    nut = e.quarter_inch_nut().shape
    for dz in [-2, -4, -8, -12]:
        assert intersection(rear, bd.Pos(0, 0, dz) * nut) < 1e-6
    # Enlarging the bore roof must not let the hex nut pull through either wall.
    for dy in [-1, 1]:
        assert intersection(rear, bd.Pos(0, dy, 0) * nut) > 1
    roof = v3.mount_roof_relief()
    result['measurements_mm']['roof_apex_z'] = roof.bounding_box().max.Z
    assert abs(roof.bounding_box().max.Z - (e.NUT_Z + 3.4 * math.sqrt(2))) < 1e-5
    result['mount_roof_angle_degrees'] = 45
    # Existing drop-in stand, seat contact and insertion travel remain compatible.
    dock = d.desktop_dock().shape
    result['measurements_mm']['dock_seat_contact'] = closest_points(dock, d.case_pose(rear)).distance
    assert result['measurements_mm']['dock_seat_contact'] < 1e-5
    for lift in [0, 1, 3, 5, 8, 12, 20]:
        assert intersection(dock, d.case_pose(bd.Pos(0, lift, 0) * rear)) < 1e-5
    # Original fastener bores and PCB contact heights are retained.
    for x, y in e.CLOSURE_XY:
        assert intersection(rear, e.cylinder(x, y, 1.5, 1.25, 16)) < 1e-6
    for hole in e.data()['mounting_holes']:
        assert intersection(rear, e.cylinder(*hole['xy'], e.PCB_BACK - 3.8, 1, 3.8 + e.PCB_THICK)) < 1e-6
    result['status'] = 'PASS'
    (ROOT / 'checks/v1_3_report.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
