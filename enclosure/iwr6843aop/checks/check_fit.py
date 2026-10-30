"""Measure the actual built solids, component envelopes and mating features."""
from pathlib import Path
import sys
import json
import math
from itertools import combinations

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import build123d as bd
from cadgen.geometry import closest_points, overlap_volume, is_sound, boundary_edges
from enclosure import assembly, data, PCB_BACK, PCB_THICK, AIR_GAP, FRONT_INNER, FRONT_OUTER, CLOSURE_XY, cylinder, along_y, box, USB_X, USB_Z, NUT_Y, NUT_Z, HEEL_BACK


def world_parts(node, parent=None):
    here = (bd.Location() if parent is None else parent) * node.location
    if node.children:
        for child in node.children:
            yield from world_parts(child, here)
    else:
        yield node.located(here)


def find_part(tree, label):
    matches = [part for part in world_parts(tree) if part.label == label]
    if len(matches) != 1:
        raise ValueError(f"Expected one {label}, found {len(matches)}")
    return matches[0]


def intersection(a, b):
    return sum(overlap_volume(sa, sb) for sa in a.solids() for sb in b.solids())


def main():
    kit = assembly().shape
    parts = list(world_parts(kit))
    rear, front, retainer = [find_part(kit, n) for n in ["rear_shell", "front_radome", "nut_retainer"]]
    pcb = find_part(kit, "pcb_PROC091G")
    antenna = find_part(kit, "ref_U2")
    nut = find_part(kit, "hardware_1_4_20_nut_threads_schematic")
    cable = find_part(kit, "ref_straight_USB_boot_11x20x6_cable_4p4")
    result = {"parts": {}, "interferences_mm3": {}, "measurements_mm": {}}
    for p in [rear, front, retainer]:
        result["parts"][p.label] = {"solids": len(p.solids()), "valid": p.is_valid,
            "sound": is_sound(p), "free_edges": sum(len(boundary_edges(s)) for s in p.shells()),
            "volume_mm3": p.volume, "bounds_mm": tuple(p.bounding_box().size)}
        assert p.is_valid and is_sound(p) and len(p.solids()) == 1 and p.volume > 0
        assert sum(len(boundary_edges(s)) for s in p.shells()) == 0
    for a, b in combinations([rear, front, retainer, nut], 2):
        v = intersection(a, b)
        result["interferences_mm3"][a.label + "/" + b.label] = v
        assert v < 1e-5, (a.label, b.label, v)
    for dz in [-2, -4, -6, -8, -12]:
        assert intersection(bd.Pos(0, 0, dz) * nut, rear) < 1e-5, ("nut insertion", dz)
    for x in [USB_X - 3.6, USB_X + 3.6]:
        tie_gauge = box(x, -74, HEEL_BACK - 1, 2.0, 2.6, 7 - HEEL_BACK)
        assert intersection(tie_gauge, rear) < 1e-6, "Cable-tie slot must pass through heel"
    for ref in [p for p in parts if p.label.startswith(("ref_", "pcb_"))]:
        for shell in [rear, front, retainer]:
            v = intersection(ref, shell)
            result["interferences_mm3"][ref.label + "/" + shell.label] = v
            assert v < 1e-5, (ref.label, shell.label, v)
    gap = closest_points(antenna, front).distance
    result["measurements_mm"]["antenna_to_radome"] = gap
    assert abs(gap - AIR_GAP) < 1e-4, gap
    probe = cylinder(0.2, -20.11, FRONT_INNER - 0.5, 0.5, 3.0)
    thickness = intersection(probe, front) / (math.pi * 0.5**2)
    result["measurements_mm"]["radome_centre_thickness"] = thickness
    assert abs(thickness - 1.6) < 1e-4
    result["measurements_mm"]["pcb_support_contact"] = closest_points(pcb, rear).distance
    assert closest_points(pcb, rear).distance < 1e-5
    assert closest_points(front, rear).distance < 1e-5
    for hole in data()["mounting_holes"]:
        x, y = hole["xy"]
        gauge = cylinder(x, y, PCB_BACK - 3.8, 1.0, 3.8 + PCB_THICK)
        assert intersection(gauge, rear) < 1e-6
        assert intersection(gauge, pcb) < 1e-6
    a, b = data()["mounting_holes"]
    result["measurements_mm"]["pcb_hole_pitch"] = math.dist(a["xy"], b["xy"])
    for x, y in CLOSURE_XY:
        gauge = cylinder(x, y, 1.5, 1.25, 16)
        assert intersection(gauge, rear) < 1e-6
        assert intersection(gauge, front) < 1e-6
    # 1/4 inch major diameter clears the external access hole up to the nut.
    nut_entry = nut.bounding_box().min.Y
    entry_depth = nut_entry - (-89)
    result["measurements_mm"]["mount_face_to_nut_entry"] = entry_depth
    result["measurements_mm"]["thread_engagement_with_7p5mm_stud"] = min(7.5 - entry_depth, 5.55625)
    assert entry_depth < 2.1
    gauge = along_y(bd.Cylinder(6.35/2, entry_depth + 0.1, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)), 0, nut_entry, NUT_Z)
    assert intersection(gauge, rear) < 1e-6
    shoulder = along_y(bd.Cylinder(12.5, 8, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)), 0, -89, NUT_Z)
    assert intersection(shoulder, cable) < 1e-6
    assert intersection(shoulder, rear) < 1e-6
    result["measurements_mm"]["25mm_arm_shoulder_to_cable"] = closest_points(shoulder, cable).distance
    result["measurements_mm"]["cable_to_rear_minimum"] = closest_points(cable, rear).distance
    result["measurements_mm"]["heatsink_to_rear_minimum"] = closest_points(find_part(kit, "ref_heatsink_envelope"), rear).distance
    result["status"] = "PASS"
    out = Path(__file__).resolve().parents[1] / "checks/fit_report.json"
    out.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
