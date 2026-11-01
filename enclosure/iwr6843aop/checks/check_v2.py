"""Native-solid clearance, assembly motion and fit checks for v2 prototype."""
from pathlib import Path
import sys
import json
from itertools import combinations
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build123d as bd
from cadgen.geometry import closest_points, is_sound, boundary_edges
import enclosure_v2 as v
import enclosure as e
import desktop_dock as dock
from check_fit import world_parts, intersection

ROOT = Path(__file__).resolve().parents[1]


def main():
    parts = v.hardwareless_parts()
    rear, front, horn, keyr, keyl, heel, keeper, sleeve = parts
    refs = list(world_parts(e.board_reference().shape)) + [e.cable_reference().shape]
    pcb = next(p for p in refs if p.label.startswith('pcb_'))
    ant = next(p for p in refs if p.label == 'ref_U2')
    report = {'parts': {}, 'overlaps_mm3': {}, 'motion_overlaps_mm3': {}, 'measurements_mm': {}, 'failures': []}

    def zero(name, a, b, motion=False):
        vol = intersection(a, b)
        report['motion_overlaps_mm3' if motion else 'overlaps_mm3'][name] = vol
        if vol > 1e-5:
            report['failures'].append([name, vol])
        return vol

    for p in parts:
        report['parts'][p.label] = {'valid': p.is_valid, 'solids': len(p.solids()),
            'sound': is_sound(p), 'volume_mm3': p.volume, 'bounds_mm': tuple(p.bounding_box().size),
            'free_edges': sum(len(boundary_edges(s)) for s in p.shells())}
        assert p.is_valid and is_sound(p) and len(p.solids()) == 1
        assert report['parts'][p.label]['free_edges'] == 0
    for a, b in combinations(parts, 2):
        zero(a.label + '/' + b.label, a, b)
    for p in parts:
        for ref in refs:
            zero(p.label + '/' + ref.label, p, ref)
    cone = v.rf_keepout()
    for p in parts:
        zero('60deg_package_envelope/' + p.label, cone, p)
    report['measurements_mm']['horn_to_RF_envelope'] = closest_points(cone, horn).distance
    report['measurements_mm']['horn_to_chip'] = closest_points(ant, horn).distance
    report['measurements_mm']['horn_to_PCB'] = closest_points(pcb, horn).distance
    report['measurements_mm']['rear_to_PCB_contact'] = closest_points(pcb, rear).distance
    report['measurements_mm']['PCB_to_upper_pads'] = closest_points(pcb, front).distance
    report['measurements_mm']['horn_seat_contact'] = closest_points(horn, front).distance
    report['measurements_mm']['heel_to_rear_contact'] = closest_points(heel, rear).distance

    # Cover drops at -6Y, then slides +6Y. Shroud and lateral keys are absent.
    stationary = bd.Compound(children=[rear, heel, keeper, sleeve, *refs])
    for dy in (-6, -5, -4, -3, -2, -1, 0):
        zero('front_slide_y_' + str(dy), bd.Pos(0, dy, 0) * front, stationary, True)
    for dz in (.5, 1, 2, 4, 8, 16, 30):
        zero('front_drop_z_' + str(dz), bd.Pos(0, -6, dz) * front, stationary, True)
    # Horn inserts only after the cover has slid closed, with keys withdrawn.
    fixed = bd.Compound(children=[rear, front, heel, keeper, sleeve, *refs])
    for dz in (0, .5, 1, 2, 4, 8, 14, 24):
        zero('horn_drop_z_' + str(dz), bd.Pos(0, 0, dz) * horn, fixed, True)
    for dx in (0, 1, 2, 4, 8, 12):
        zero('right_key_insert_' + str(dx), bd.Pos(dx, 0, 0) * keyr,
             bd.Compound(children=[rear, front, horn]), True)
    # Heel slides under empty rear, with keeper absent.
    for dy in (-v.HEEL_SLIDE, -6, -4, -2, 0):
        zero('heel_slide_' + str(dy), bd.Pos(0, dy, 0) * heel, rear, True)
    for dz in (0, -1, -3, -6, -12):
        zero('heel_drop_' + str(dz), bd.Pos(0, -v.HEEL_SLIDE, dz) * heel, rear, True)
    for dz in (0, 2, 5, 10, 16, 25):
        zero('keeper_insert_' + str(dz), bd.Pos(0, 0, dz) * keeper,
             bd.Compound(children=[rear, heel, sleeve]), True)
    for dy in (0, 2, 5, 10, 20, 30):
        zero('socket_insert_' + str(dy), bd.Pos(0, dy, 0) * sleeve, heel, True)
    # Positive retention checks: keys prevent horn lift, horn prevents lid sliding.
    report['retention_overlap_mm3'] = {
        'horn_lift_1mm_with_keys': intersection(bd.Pos(0, 0, 1) * horn, bd.Compound(children=[keyr, keyl])),
        'front_open_1mm_with_horn': intersection(bd.Pos(0, -1, 0) * front, horn),
        'heel_withdraw_1mm_with_keeper': intersection(bd.Pos(0, -1, 0) * heel, keeper),
        'socket_withdraw_2mm_with_keeper': intersection(bd.Pos(0, 2, 0) * sleeve, keeper),
        'front_lift_1mm_with_rails': intersection(bd.Pos(0, 0, 1) * front, rear),
    }
    for name, value in report['retention_overlap_mm3'].items():
        if value <= 1e-4:
            report['failures'].append(['missing retention: ' + name, value])
    stand = dock.desktop_dock().shape
    for lift in (0, 1, 3, 5, 8, 12, 20):
        posed = dock.dock_pose(bd.Pos(0, 0, lift) * bd.Rot(90, 0, 0)
                              * bd.Pos(0, 89, 8) * bd.Compound(children=parts))
        zero('stand_insertion_' + str(lift), posed, stand, True)
    report['status'] = 'FAIL' if report['failures'] else 'PASS'
    (ROOT / 'checks/v2_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'failures': report['failures'],
                      'measurements_mm': report['measurements_mm'],
                      'retention': report['retention_overlap_mm3']}, indent=2))
    assert not report['failures']


if __name__ == '__main__':
    main()
