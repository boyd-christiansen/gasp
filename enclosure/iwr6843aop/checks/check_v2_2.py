"""Measure the v2.2 parts, mating paths and deliberate compliant-fit regions."""
from pathlib import Path
import sys
import json
from itertools import combinations
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build123d as bd
from cadgen.geometry import closest_points, is_sound, boundary_edges
import enclosure_v2_2 as n
import enclosure_v2 as v
import enclosure as e
import desktop_dock as dock
from check_fit import world_parts, intersection

ROOT = Path(__file__).resolve().parents[1]


def main():
    parts = n.hardwareless_parts()
    rear, front, horn, kr, kl, heel, clip, keeper = parts
    refs = list(world_parts(e.board_reference().shape)) + [n.cable_reference_v22().shape]
    report = {'parts': {}, 'overlaps_mm3': {}, 'measurements_mm': {},
              'intentional_elastic_overlaps_mm3': {}, 'retention_mm3': {}, 'failures': [],
              'physical_fit_verified': False}

    def zero(name, a, b):
        vol = intersection(a, b)
        report['overlaps_mm3'][name] = vol
        if vol > 1e-5:
            report['failures'].append([name, vol])
        return vol

    def retained(name, a, b):
        vol = intersection(a, b)
        report['retention_mm3'][name] = vol
        if vol < 1e-4:
            report['failures'].append(['missing retention ' + name, vol])

    for p in parts + [n.key_335().shape]:
        print('Checking solid:', p.label, flush=True)
        report['parts'][p.label] = {'valid': p.is_valid, 'sound': is_sound(p),
            'solids': len(p.solids()), 'volume_mm3': p.volume,
            'free_edges': sum(len(boundary_edges(s)) for s in p.shells())}
        assert p.is_valid and is_sound(p) and len(p.solids()) == 1
        assert report['parts'][p.label]['free_edges'] == 0
    pads = bd.Compound(children=[n.contact_ramp(x + a) for x in (-8, 8) for a in (-3.1, 3.1)])
    for a, b in combinations(parts, 2):
        if a is heel and b is clip:
            report['intentional_elastic_overlaps_mm3']['clip_head_preload'] = intersection(a, b)
            zero('clip_head_outside_raised_pads', a, b - pads)
        else:
            zero(a.label + '/' + b.label, a, b)
    for p in parts + [n.key_335().shape]:
        for r in refs:
            zero(p.label + '/' + r.label, p, r)
        zero('RF_60deg/' + p.label, p, v.rf_keepout())
    for name, a, b in [('horn_RF_gap', horn, v.rf_keepout()),
                        ('heel_to_rear_contact', heel, rear), ('clip_handle_floor_contact', clip, rear)]:
        report['measurements_mm'][name] = closest_points(a, b).distance
    pcb = next(p for p in refs if p.label.startswith('pcb_'))
    report['measurements_mm']['rear_PCB_contact'] = closest_points(pcb, rear).distance
    report['measurements_mm']['PCB_upper_pad_clearance'] = closest_points(pcb, front).distance

    fixed = bd.Compound(children=[rear, heel, clip, keeper, *refs])
    for dy in (-6, -5, -4, -3, -2, -1, 0):
        zero('front_slide_' + str(dy), bd.Pos(0, dy, 0) * front, fixed)
    for dz in (.5, 1, 2, 4, 8, 16, 30):
        zero('front_drop_' + str(dz), bd.Pos(0, -6, dz) * front, fixed)
    for dy in (-7, -6, -4, -2, 0):
        zero('heel_slide_' + str(dy), bd.Pos(0, dy, 0) * heel, rear)
    for dz in (0, -1, -3, -6, -12):
        zero('heel_drop_' + str(dz), bd.Pos(0, -7, dz) * heel, rear)
    for dy in [n.CLIP_INSERT_OFFSET] + [k / 4 for k in range(29, -1, -1)]:
        c = bd.Pos(0, dy, 0) * clip
        moving_pads = bd.Pos(0, dy, 0) * pads
        zero('clip_insert_rear_' + str(dy), c, rear)
        zero('clip_insert_heel_nonelastic_' + str(dy), c - moving_pads, heel)
        zero('clip_insert_cable_' + str(dy), c, n.cable_reference_v22().shape)
    for dz in (0, 1, 3, 6, 10, 20):
        zero('clip_drop_' + str(dz), bd.Pos(0, n.CLIP_INSERT_OFFSET, dz) * clip,
             bd.Compound(children=[rear, heel]))
    for dz in (0, 2, 5, 10, 16, 25):
        zero('keeper_insert_' + str(dz), bd.Pos(0, 0, dz) * keeper,
             bd.Compound(children=[rear, heel, clip]))
    fixed = bd.Compound(children=[rear, front, heel, clip, keeper, *refs])
    for dz in (0, .5, 1, 2, 4, 8, 14, 24):
        zero('horn_insert_' + str(dz), bd.Pos(0, 0, dz) * horn, fixed)
    for key in (kr, n.key_335().shape):
        for dx in (0, 1, 2, 4, 8, 12):
            zero(key.label + '_insert_' + str(dx), bd.Pos(dx, 0, 0) * key,
                 bd.Compound(children=[rear, front, horn]))
    retained('horn_lift_1mm', bd.Pos(0, 0, 1) * horn, bd.Compound(children=[kr, kl]))
    retained('front_slide_open_1mm', bd.Pos(0, -1, 0) * front, horn)
    retained('front_lift_1mm', bd.Pos(0, 0, 1) * front, rear)
    retained('heel_withdraw_1mm', bd.Pos(0, -1, 0) * heel, keeper)
    retained('clip_withdraw_1mm_with_keeper', bd.Pos(0, 1, 0) * clip, keeper)
    retained('clip_lift_0p4_closed_lid', bd.Pos(0, 0, .4) * clip, front)

    # The old stand's peg intentionally expands the tested 4.35 mm split socket.
    # All material outside that peg must clear throughout insertion.
    local = bd.Rot(90, 0, 0) * bd.Pos(0, 89, 8) * bd.Compound(children=parts)
    cradle_no_pin = dock.cradle() - dock.smooth_pin()
    for lift in (0, .5, 1, 2, 3, 5, 8, 12, 20):
        p = bd.Pos(0, 0, lift) * local
        zero('stand_insertion_no_pin_' + str(lift), p, cradle_no_pin)
        report['intentional_elastic_overlaps_mm3']['stand_pin_lift_' + str(lift)] = intersection(p, dock.smooth_pin())
    retained('shoe_blocks_twist_2deg', bd.Rot(0, 0, 2) * local, cradle_no_pin)
    retained('shoe_blocks_side_shift_0p5', bd.Pos(.5, 0, 0) * local, cradle_no_pin)
    retained('shoe_blocks_rear_shift_0p5', bd.Pos(0, .5, 0) * local, cradle_no_pin)
    # Full pedestal/base check catches anything below the clipped cradle.
    stand_no_pin = dock.desktop_dock().shape - dock.dock_pose(dock.smooth_pin())
    zero('full_stand_excluding_pin', dock.dock_pose(local), stand_no_pin)

    # Actual geometric pass/fail gauges, rather than echoing the chosen constant.
    def cable_gauge(diameter):
        return e.along_y(bd.Cylinder(diameter / 2, 4,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)), e.USB_X, -78, e.USB_Z)
    shells = bd.Compound(children=[rear, front])
    zero('cable_10mm_pass_gauge', cable_gauge(10), shells)
    retained('cable_10p02mm_no_go_gauge', cable_gauge(10.02), shells)
    report['measurements_mm']['cable_passage_gauge_bracket'] = [10, 10.02]
    local_heel = bd.Rot(90, 0, 0) * bd.Pos(0, 89, 8) * heel
    for z in (1.2, 5, 9.9):
        section = bd.Compound(children=local_heel.intersect(e.box(0, 0, z, 50, 50, .001)))
        bounds = section.bounding_box()
        width = 26.8 + (z + .2) / 10.4
        back = 10.8 + .5 * (z + .2) / 10.4
        report['measurements_mm']['shoe_side_gap_z_' + str(z)] = (width - bounds.size.X) / 2
        report['measurements_mm']['shoe_rear_gap_z_' + str(z)] = back - bounds.max.Y
    report['notes'] = [
        'The two listed elastic overlaps are intentional; no FEA, print, force or fatigue validation has been performed.',
        'The shoe is gravity/friction retained in the existing stand; no positive lift latch is claimed.',
        'USB molded strain relief is an assumed 9 mm diameter by 12 mm envelope, not a user measurement.',
        'Board seating height, shroud and PCB capture gap are inherited from v2.1; TP20 relief remains open.'
    ]
    report['status'] = 'FAIL' if report['failures'] else 'PASS'
    (ROOT / 'checks/v2_2_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'failures', 'measurements_mm',
        'intentional_elastic_overlaps_mm3', 'retention_mm3')}, indent=2))
    assert not report['failures']


if __name__ == '__main__':
    main()
