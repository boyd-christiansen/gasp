"""Export v2 prototype print parts and small fit coupons, preserving v1 files."""
from pathlib import Path
from cadgen import export
import enclosure_v2 as v

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    out = ROOT / 'exports_v2'
    out.mkdir(exist_ok=True)
    items = {
        '01_rear_flat': v.rear_v2,
        '02_sliding_front': v.front_v2_print,
        '03_aperture_shroud': v.shroud_print,
        '04_locking_key_single': v.key_print,
        '05_detachable_heel': v.heel_v2_print,
        '06_heel_keeper': v.keeper_print,
        '07_socket_4p50_nominal': v.socket_nominal_print,
        'socket_4p35_snug_trial': v.socket_snug_print,
        'socket_4p65_loose_trial': v.socket_loose_print,
        'key_3p35_snug_trial': v.key_snug_print,
        'key_3p05_loose_trial': v.key_loose_print,
        'coupon_slider_rear': v.slider_rear_coupon,
        'coupon_slider_front': v.slider_front_coupon,
        'coupon_shroud_receiver': v.shroud_receiver_coupon,
        'coupon_shroud_leg': v.shroud_leg_coupon,
    }
    for name, fn in items.items():
        export(fn(), out / (name + '.stl'), out / (name + '.step'))
    export(v.keys_print(), out / 'two_locking_keys.stl')
    export(v.sockets_print(), out / 'three_socket_trials.stl')
    export(v.fit_coupons(), out / 'PRINT_FIRST_fit_coupons.3mf', out / 'PRINT_FIRST_fit_coupons.stl')
    export(v.assembly_v2(), out / 'assembly_with_references.step', out / 'assembly_with_references.glb')
    export(v.desktop_v2(), out / 'assembly_on_existing_stand.glb')
    export(v.exploded_v2(), out / 'assembly_order_exploded.glb')
    export(v.insert_installation(), out / 'shroud_installation.glb')
    correction = ROOT / 'exports_v2_1'
    correction.mkdir(exist_ok=True)
    export(v.rear_v2(), correction / '01_rear_TP20_clearance.stl',
           correction / '01_rear_TP20_clearance.step',
           correction / '01_rear_TP20_clearance.3mf')
