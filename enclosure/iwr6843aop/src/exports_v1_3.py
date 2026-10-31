from pathlib import Path
from cadgen import export
from enclosure_v1_3 import rear_reinforced, rear_reinforced_print, assembly_v1_3

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    out = ROOT / 'exports_v1_3'
    out.mkdir(exist_ok=True)
    export(rear_reinforced_print(), out / 'rear_shell_reinforced.stl', out / 'rear_shell_reinforced.step')
    export(rear_reinforced(), out / 'rear_shell_assembly_coordinates.step')
    export(assembly_v1_3(), out / 'assembly_with_references.step', out / 'assembly_with_references.glb')
