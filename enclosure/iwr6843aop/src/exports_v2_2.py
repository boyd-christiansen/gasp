"""Standing v2.2 exports; historical v2/v2.1 print files remain untouched."""
from pathlib import Path
from cadgen import export
import enclosure_v2_2 as n
import enclosure_v2 as v

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    out = ROOT / 'exports_v2_2'
    out.mkdir(exist_ok=True)
    items = {
        '01_rear_10mm_cable_TP20': n.rear_v22,
        '02_front_clip_capture': n.front_print_v22,
        '04_key_3p20_single_PRINT_TWO': n.key_320_print,
        '04_key_3p35_single_optional_PRINT_TWO': n.key_335_print,
        '05_fitted_mount_integral_socket': n.heel_print_v22,
        '06_preload_clip': n.clip_print_v22,
    }
    for name, fn in items.items():
        export(fn(), out / (name + '.stl'), out / (name + '.step'))
    export(n.print_first_v22(), out / 'PRINT_FIRST_mount_and_keys.3mf',
           out / 'PRINT_FIRST_mount_and_keys.stl')
    export(n.case_pair_v22(), out / 'REPRINT_case_pair.3mf', out / 'REPRINT_case_pair.stl')
    export(n.assembly_v22(), out / 'assembly_with_references.step')
    export(n.desktop_v22(), out / 'assembly_on_existing_stand.glb')
    export(n.mechanism_detail_v22(), out / 'mount_assembly_detail.glb')
    export(n.mount_installation_v22(), out / 'mount_installation.glb')
    reuse = out / 'REUSE_existing_parts'
    reuse.mkdir(exist_ok=True)
    export(v.shroud_print(), reuse / '03_aperture_shroud_unchanged.stl')
    export(v.keeper_print(), reuse / '07_T_keeper_unchanged.stl')
