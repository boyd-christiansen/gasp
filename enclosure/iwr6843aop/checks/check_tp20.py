"""Regression check for the TP20 rear-shell relief, including actual old export."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build123d as bd
from OCP.BRepAlgoAPI import BRepAlgoAPI_Cut
from cadgen.geometry import closest_points
import enclosure_v2 as v
import enclosure as e
from check_fit import world_parts, intersection

ROOT = Path(__file__).resolve().parents[1]


def comparison_cut(a, b):
    # STEP round-trip surfaces differ at floating-point tolerance. Use a
    # one-micron fuzzy Boolean for the cross-format regression comparison.
    operation = BRepAlgoAPI_Cut(a.wrapped, b.wrapped)
    operation.SetFuzzyValue(.001)
    operation.Build()
    assert operation.IsDone()
    return bd.Compound(operation.Shape())


def main():
    old = bd.import_step(ROOT / 'history/v2_before_tp20/01_rear_flat.step').solids()[0]
    new = bd.import_step(ROOT / 'exports_v2_1/01_rear_TP20_clearance.step').solids()[0]
    refs = list(world_parts(e.board_reference().shape))
    tp20 = next(p for p in refs if p.label == 'ref_TP20')
    tail = next(p for p in refs if p.label == 'ref_TP20_tail')
    removed = comparison_cut(old, new)
    added = comparison_cut(new, old)
    outside_relief = comparison_cut(removed, v.tp20_relief())
    vol = lambda s: sum(abs(x.volume) for x in s.solids())
    report = {
        'status': 'PENDING',
        'center_xy_mm': v.tp20_center(),
        'relief_diameter_mm': v.TP20_RELIEF_DIAMETER,
        'STEP_comparison_tolerance_mm': .001,
        'previous_volume_mm3': old.volume,
        'updated_volume_mm3': new.volume,
        'previous_bounds_mm': tuple(old.bounding_box().size),
        'previous_shell_overlap_with_TP20_mm3': intersection(old, tp20),
        'updated_shell_overlap_with_TP20_mm3': intersection(new, tp20),
        'updated_shell_minimum_clearance_to_TP20_envelope_mm': closest_points(new, tp20).distance,
        'removed_volume_mm3': vol(removed),
        'added_volume_mm3': vol(added),
        'removed_outside_local_relief_mm3': vol(outside_relief),
        'board_support_height_mm': e.PCB_BACK,
        'new_bounds_mm': tuple(new.bounding_box().size),
        'board_insertion_overlaps_mm3': {},
        'actual_physical_fit_verified': False,
    }
    for lift in (0, .25, .5, 1, 2, 4, 8, 16):
        report['board_insertion_overlaps_mm3'][str(lift)] = intersection(
            new, bd.Pos(0, 0, lift) * bd.Compound(children=[tp20, tail]))
    print(json.dumps(report, indent=2))
    assert report['previous_shell_overlap_with_TP20_mm3'] > .1
    assert report['updated_shell_overlap_with_TP20_mm3'] < 1e-5
    assert report['updated_shell_minimum_clearance_to_TP20_envelope_mm'] > .8
    assert report['added_volume_mm3'] < 1e-5
    assert report['removed_outside_local_relief_mm3'] < 1e-5
    assert all(x < 1e-5 for x in report['board_insertion_overlaps_mm3'].values())
    assert abs(e.PCB_BACK - 10.4) < 1e-9
    assert new.is_valid and len(new.solids()) == 1
    report['status'] = 'PASS'
    (ROOT / 'checks/tp20_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: TP20 clearance and local-change regression')


if __name__ == '__main__':
    main()
