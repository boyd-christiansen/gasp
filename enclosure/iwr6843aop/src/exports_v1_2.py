from pathlib import Path
from cadgen import export
from enclosure import front_radome, front_open_aperture, nut_retainer
from enclosure_v1_2 import rear_standard_ties, pcb_washer, washer_print_pair, assembly_v1_2, assembly_open_v1_2

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    for name, model in [("rear_shell", rear_standard_ties), ("front_radome", front_radome),
                        ("front_open_aperture", front_open_aperture), ("nut_retainer", nut_retainer),
                        ("pcb_washer", pcb_washer), ("washer_print_pair", washer_print_pair)]:
        export(model(), ROOT / "exports_v1_2" / (name + ".step"), ROOT / "exports_v1_2" / (name + ".stl"))
    export(assembly_v1_2(), ROOT / "exports_v1_2/assembly_with_references.step")
    export(assembly_open_v1_2(), ROOT / "exports_v1_2/assembly_open_aperture_with_references.step")
