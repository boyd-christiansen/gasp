"""Actual solid fit, insertion, cable and stand-footprint checks for the dock."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build123d as bd
from cadgen.geometry import closest_points, overlap_volume, is_sound, boundary_edges
from check_fit import world_parts
import enclosure as e
import enclosure_v1_2 as v
import desktop_dock as d

ROOT = Path(__file__).resolve().parents[1]


def overlap(a, b):
    return sum(overlap_volume(sa, sb) for sa in a.solids() for sb in b.solids())


def main():
    stand = d.desktop_dock().shape
    report = {'parts': {}, 'interferences_mm3': {}, 'insertion_overlap_mm3': {}, 'measurements_mm': {},
              'limits': ['Gravity retained; the pin is smooth and does not screw into the metal nut.',
                         'Actual print/fit, friction, cable bend, tip resistance and durability remain untested.']}
    for part in [stand, d.dock_fit_test().shape]:
        report['parts'][part.label] = {'valid': part.is_valid, 'sound': is_sound(part),
            'solids': len(part.solids()), 'bounds_mm': list(part.bounding_box().size),
            'free_edges': sum(len(boundary_edges(s)) for s in part.shells()), 'volume_mm3': part.volume}
        assert part.is_valid and is_sound(part) and len(part.solids()) == 1 and part.volume > 0
        assert report['parts'][part.label]['free_edges'] == 0

    refs = list(world_parts(v.assembly_v1_2().shape))
    # Account for actual retainer screw heads, absent in the old display model.
    for x in [-9, 9]:
        head = e.cylinder(x, e.NUT_Y, e.HEEL_BACK - 2.4 - 2.5, 2.25, 2.5)
        head.label = f'retainer_head_gauge_{x}'
        refs.append(head)
    # Replace the original schematic 5.2 mm nut bore with a minimum 2B bore
    # envelope: 0.196 in = 4.9784 mm. The locating pin clears its entire length.
    minor_diameter = .196 * 25.4
    sleeve = e.along_y(bd.Cylinder(2.6, 5.55625, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)),
                       0, e.NUT_Y + 2.778125, e.NUT_Z)
    bore = e.along_y(bd.Cylinder(minor_diameter / 2, 6, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)),
                     0, e.NUT_Y + 3, e.NUT_Z)
    minimum_nut = e.quarter_inch_nut().shape + (sleeve - bore)
    minimum_nut.label = 'minimum_2B_minor_diameter_nut_gauge'
    refs.append(minimum_nut)

    for ref in refs:
        part = d.case_pose(ref)
        volume = overlap(stand, part)
        report['interferences_mm3'][ref.label] = volume
        assert volume < 1e-5, (ref.label, volume)
    # Verify the optional open front on the same stand as well.
    assert overlap(stand, d.case_pose(e.front_open_aperture().shape)) < 1e-5
    rear = d.case_pose(v.rear_standard_ties().shape)
    report['measurements_mm']['heel_seat_contact'] = closest_points(stand, rear).distance
    assert report['measurements_mm']['heel_seat_contact'] < 1e-5

    # Check insertion along the case's mounting axis, including pin and guides.
    # These contain every external feature near the dock; the boards remain enclosed.
    lower = [v.rear_standard_ties().shape, e.front_radome().shape, e.nut_retainer().shape,
             minimum_nut, e.cable_reference().shape, *refs[-3:-1]]
    for lift in [1, 3, 5, 8, 12, 20]:
        volume = sum(overlap(stand, d.case_pose(bd.Pos(0, lift, 0) * part)) for part in lower)
        report['insertion_overlap_mm3'][str(lift)] = volume
        assert volume < 1e-5, ('insertion', lift, volume)

    cable = d.case_pose(e.cable_reference().shape)
    report['measurements_mm']['USB_reference_to_stand'] = closest_points(cable, stand).distance
    report['measurements_mm']['USB_reference_lowest_above_desk'] = cable.bounding_box().min.Z
    assert report['measurements_mm']['USB_reference_to_stand'] > 2
    report['measurements_mm']['pin_to_minimum_nut_thread_crest'] = closest_points(d.dock_pose(d.smooth_pin()), d.case_pose(minimum_nut)).distance
    assert report['measurements_mm']['pin_to_minimum_nut_thread_crest'] > .2

    # Probe actual pin sections for maximum diameter and insertion height.
    pin = d.smooth_pin()
    hits = pin.intersect(e.box(0, 0, 2.1, 10, 10, 4.5))
    assert hits
    section = bd.Compound(children=hits)
    assert abs(section.bounding_box().size.X - d.PIN_DIAMETER) < 1e-5
    assert abs(pin.bounding_box().max.Z - d.PIN_LENGTH) < 1e-5

    # A 5-mm-inset footprint prism contains all modeled rigid enclosure parts.
    # This checks static gravity projection without inventing board mass data.
    inset = e.rounded_box(0, d.FOOT_Y, 0, d.FOOT_WIDTH - 10, d.FOOT_DEPTH - 10, 260, 20)
    all_case = d.case_pose(v.assembly_v1_2().shape)
    for part in world_parts(all_case):
        if part.label.startswith('ref_straight_USB'):
            continue
        outside = part.cut(*inset.solids())
        assert abs(outside.volume) < 1e-5, ('outside inset footprint', part.label, outside.volume)
    report['rigid_enclosure_projection_inside_5mm_inset_footprint'] = True
    chip = next(ref for ref in refs if ref.label == 'ref_U2')
    centre = d.case_pose(chip).center(bd.CenterOf.MASS)
    report['measurements_mm']['radar_height'] = centre.Z
    report['measurements_mm']['aim_height_at_1p8ft'] = centre.Z + 548.64 * math.tan(math.radians(d.PITCH))
    report['status'] = 'PASS'
    (ROOT / 'checks/dock_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
