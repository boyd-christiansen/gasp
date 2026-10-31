"""Verify changed solids, actual tie clearances and assembled washers."""
import json
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import build123d as bd
from cadgen.geometry import closest_points, overlap_volume, is_sound, boundary_edges
from check_fit import world_parts, intersection
from enclosure import data, box, cylinder, PCB_BACK, PCB_THICK, USB_X, HEEL_BACK, CLOSURE_XY
from enclosure_v1_2 import assembly_v1_2, rear_standard_ties, pcb_washer, assembled_washers

def main():
    rear = rear_standard_ties().shape
    washer = pcb_washer().shape
    parts = list(world_parts(assembly_v1_2().shape))
    for s in [rear, washer]:
        assert s.is_valid and is_sound(s) and len(s.solids()) == 1
        assert sum(len(boundary_edges(sh)) for sh in s.shells()) == 0
    for p in parts:
        if p.label != rear.label:
            assert intersection(rear, p) < 1e-5, (rear.label, p.label)
    for x in [USB_X-3.6, USB_X+3.6]:
        assert intersection(rear, box(x, -74, HEEL_BACK-1, 2.8, 3.4, 7-HEEL_BACK)) < 1e-6
    washers = assembled_washers()
    pcb = next(p for p in parts if p.label == "pcb_PROC091G")
    for w in washers:
        assert closest_points(w, pcb).distance < 1e-6
        for p in parts:
            if p.label != washer.label:
                assert intersection(w, p) < 1e-5, ("washer", p.label)
    for h, w in zip(data()["mounting_holes"], washers):
        # Probe actual M2 shaft clearance and the 6 mm screw reach.
        seat = w.bounding_box().max.Z
        gauge = cylinder(*h["xy"], seat - 6, 1.0, 6)
        assert intersection(gauge, w) < 1e-6
        assert intersection(gauge, pcb) < 1e-6
        assert intersection(gauge, rear) < 1e-6
        engagement = PCB_BACK - (seat - 6)
        assert 3.5 < engagement < 4.0
    result = {"status":"PASS", "tie_gauge_mm":[2.8,3.4], "washer_bounds_mm":list(washer.bounding_box().size),
              "washer_volume_mm3":washer.volume, "pcb_screw_engagement_mm":engagement,
              "rear_volume_mm3":rear.volume, "checked":"Rear against every assembly component; washers contact PCB and clear other modeled components; M2 shafts clear rear, PCB and washers."}
    (Path(__file__).parent / "v1_2_report.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__ == "__main__":
    main()
