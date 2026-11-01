"""Hardware-free pill enclosure, v2 prototype, with a removable aperture shroud.

Case coordinates follow enclosure.py. The front drops on 6 mm toward -Y,
slides +Y to close, then the shroud inserts along -Z. Two lateral printed
keys retain its locating legs. This is cosmetic trim, not an RF horn antenna.
"""
import math
import build123d as bd
from cadgen import model
import enclosure as e
from enclosure_v1_3 import reinforced_saddle, SADDLES
import desktop_dock as dock

WIDTH = 60.0
HEIGHT = 174.0
SLIDE = 6.0
SEAM = 14.0
FRONT_BASE = 14.15
PCB_CAPTURE_GAP = .15
HORN_BOTTOM = 13.3
HORN_SEAT = 20.95
HORN_TOP = 22.15
THROAT = 20.0
FLARE = 1.7  # radial growth per mm height, in each principal plane
HORN_WALL = 1.6  # XY section thickness (normal thickness is lower on slope)
HORN_FLANGE = 55.8
CX, CY = e.radar_window_centre()
LOCK_X = 26.0
KEY_Z = 11.5
HEEL_SLIDE = 7.0
KEEPER_Y = -76.5
SOCKET_LENGTH = 10.6
TP20_RELIEF_DIAMETER = 6.0


def tp20_center():
    point = next(c for c in e.data()['components'] if c['name'] == 'TP20')
    return ((point['xmin'] + point['xmax']) / 2,
            (point['ymin'] + point['ymax']) / 2)


def tp20_relief():
    # Open through the flat back: no thin residual floor or printing support.
    # The existing neighboring vent naturally joins this clearance opening.
    return e.cylinder(*tp20_center(), -.1, TP20_RELIEF_DIAMETER / 2, e.FLOOR + .2)


def rr(x, y, z, w, h, r):
    return bd.Pos(x, y, z) * bd.RectangleRounded(w, h, r)


def horn_size(z):
    return THROAT + 2 * FLARE * (z - HORN_BOTTOM)


def horn_inner(z0=None, z1=None, extra=0):
    z0 = HORN_BOTTOM - .1 if z0 is None else z0
    z1 = HORN_TOP + .1 if z1 is None else z1
    return bd.loft([rr(CX, CY, z, horn_size(z) + 2 * extra,
                        horn_size(z) + 2 * extra,
                        1 + (z - HORN_BOTTOM) / (HORN_TOP - HORN_BOTTOM))
                    for z in (z0, z1)])


def horn_outer(z0, z1, clearance=0):
    return bd.loft([rr(CX, CY, z,
                        horn_size(z) + 2 * (HORN_WALL + clearance),
                        horn_size(z) + 2 * (HORN_WALL + clearance),
                        2.6 + (z - HORN_BOTTOM) / (HORN_TOP - HORN_BOTTOM))
                    for z in (z0, z1)])


def rf_keepout(zmax=HORN_TOP + 3, half_angle=60):
    antenna_z = e.PCB_BACK + e.PCB_THICK + e.ANTENNA_HEIGHT
    a = next(c for c in e.data()['components'] if c['name'] == 'U2')
    w, h = a['xmax'] - a['xmin'], a['ymax'] - a['ymin']
    growth = 2 * (zmax - antenna_z) * math.tan(math.radians(half_angle))
    return bd.loft([bd.Pos(CX, CY, antenna_z) * bd.Rectangle(w, h),
                    bd.Pos(CX, CY, zmax) * bd.Rectangle(w + growth, h + growth)])


def key_slot(side):
    return e.box(side * 26.0, CY, KEY_Z - .9, 10, 3.4, 1.8)


def cable_bore():
    return e.along_y(bd.Cylinder(2.75, 24,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)), e.USB_X, -68, e.USB_Z)


def heel_stud(x):
    s = e.box(x, -68, -.1, 4, 3, 3.0)
    s += e.rounded_box(x, -68, 2.8, 8, 7, 1.6, .6)
    return s


def heel_keyway(x):
    return (e.rounded_box(x, -68 - HEEL_SLIDE, -.1, 8.6, 7.6, 2.7, .7)
            + e.box(x, -68 - HEEL_SLIDE / 2, -.1, 4.6, HEEL_SLIDE + 3.6, 2.7))


@model
def rear_v2():
    s = e.capsule(WIDTH, HEIGHT, 0, SEAM)
    s -= e.capsule(WIDTH - 4.8, HEIGHT - 4.8, e.FLOOR, SEAM + 1)
    for h in e.data()['mounting_holes']:
        x, y = h['xy']
        s += e.cylinder(x, y, 2.3, 2.65, e.PCB_BACK - 2.3)
        s += e.cylinder(x, y, e.PCB_BACK - .1, 1.05, 2.5)
        s += bd.Pos(x, y, e.PCB_BACK + 2.3) * bd.Cone(1.05, .8, .35,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    for x, y in SADDLES:
        s += reinforced_saddle(x, y)
    # Four ledges for the lid's drop-and-slide hooks, clear of the electronics.
    for side in (-1, 1):
        for y in (-50, 50):
            s += e.box(side * 25.0, y, 12.7, 6.0, 4, 1.3)
            # Stops locate the final slide position; wall braces support ledges.
            s += e.box(side * 24.8, y + 3.1, 2.3, 6.4, 1.6, 11.7)
        # Shroud-leg receivers also stiffen the side wall.
        s += e.rounded_box(side * LOCK_X, CY, 2.3, 6.2, 11, 11.7, 1)
        s -= e.rounded_box(side * LOCK_X, CY, 8.2, 3.5, 7.5, 6, .35)
        s -= key_slot(side)
    for y in (-29, -24, -19, -14, 8, 13, 18, 23, 28, 33, 38):
        s -= e.rounded_box(0, y, -.1, 15 if y < 0 else 13, 2, 2.6, .9)
    s -= e.rounded_box(4.2, -11.95, -.1, 8, 5, 2.6, 1)
    s -= e.usb_exit()
    # Lower half of a boot stop; a 5.5 mm cable passage is completed by the lid.
    s += e.box(e.USB_X, -80, 2.3, 13, 2, e.USB_Z - 2.3)
    s -= cable_bore()
    for x in (-8, 8):
        s -= heel_keyway(x)
    s -= e.box(0, KEEPER_Y, -.1, 3.5, 3.5, 2.7)
    s -= tp20_relief()
    return e.check_part(s, 'v2_rear_flat_back', '#39434C')


def lid_hook(side, y):
    # L section under the rear ledge; neck remains inboard of that ledge.
    s = e.box(side * 20.6, y, 11.0, 1.8, 4, e.FRONT_INNER - 11 + .1)
    s += e.box(side * 22.0, y, 11.0, 4.6, 4, 1.4)
    return s


@model
def front_v2():
    outer = e.capsule(WIDTH, HEIGHT, FRONT_BASE, e.FRONT_OUTER - FRONT_BASE)
    edges = [x for x in outer.edges() if abs(x.bounding_box().min.Z - e.FRONT_OUTER) < 1e-5]
    outer = bd.fillet(edges, 1.2)
    s = outer - e.capsule(WIDTH - 3.2, HEIGHT - 3.2, FRONT_BASE - .1,
                          e.FRONT_INNER - FRONT_BASE + .1)
    for side in (-1, 1):
        for y in (-50, 50):
            s += lid_hook(side, y)
    # Upper pads capture the board with clearance, never use PCB as closure stop.
    z = e.PCB_BACK + e.PCB_THICK + PCB_CAPTURE_GAP
    for h in e.data()['mounting_holes']:
        x, y = h['xy']
        pad = e.cylinder(x, y, z, 2.65, e.FRONT_INNER - z + .1)
        pad -= e.rounded_box(x, y + SLIDE / 2, z - .1, 2.7, SLIDE + 2.7, 1.5, .6)
        s += pad
    for x, y in [(-11.7, 14), (-7.15, -42), (7.4, -42)]:
        outward = -1 if x < 0 else 1
        inner = x - outward * .6
        s += e.rounded_box(inner + outward * 1.4, y, z, 2.8, 6,
                           e.FRONT_INNER - z + .1, .6)
    # Thick local seat around the aperture, with a recessed flange ledge.
    s += e.rounded_box(CX, CY, 18.0, HORN_FLANGE + 1.4, HORN_FLANGE + 1.4,
                       e.FRONT_INNER - 18 + .1, 4)
    s -= horn_outer(12.9, HORN_TOP + 1, .3)
    s -= e.rounded_box(CX, CY, HORN_SEAT, HORN_FLANGE + .5,
                       HORN_FLANGE + .5, 4, 3.5)
    # These vertical bores index the shroud through the cover into the rear.
    for side in (-1, 1):
        s -= e.rounded_box(side * LOCK_X, CY, 10, 3.5, 7.5, 14, .35)
    s -= e.usb_exit()
    upper = e.box(e.USB_X, -80, e.USB_Z + .15, 13, 2,
                  e.FRONT_INNER - e.USB_Z - .05)
    upper -= cable_bore()
    s += upper
    # Stop the internal heel keeper lifting once the cover has closed.
    for x in (-9, 9):
        s += e.box(x, KEEPER_Y + 1.4, 4.55, 3, 1.8, e.FRONT_INNER - 4.45)
    return e.check_part(s, 'v2_sliding_open_front', '#B8C2C7')


@model
def aperture_shroud():
    s = horn_outer(HORN_BOTTOM, HORN_SEAT + .1)
    s += e.rounded_box(CX, CY, HORN_SEAT, HORN_FLANGE, HORN_FLANGE,
                       HORN_TOP - HORN_SEAT, 3.3)
    s -= horn_inner()
    for side in (-1, 1):
        # Broad rigid legs, retained by separate sliding keys rather than snaps.
        leg = e.rounded_box(side * LOCK_X, CY, 8.5, 3, 7, HORN_SEAT - 8.4, .3)
        leg -= key_slot(side)
        s += leg
    return e.check_part(s, 'v2_removable_flared_aperture_shroud', '#D79C5B')


def locking_key_body(width=3.20):
    # Canonical key for +X side. Taper is for entry, not a specified press fit.
    outline = bd.Polygon((23.3, CY - 1.35), (30.3, CY - width / 2),
                         (30.3, CY + width / 2), (23.3, CY + 1.35), align=None)
    s = bd.Pos(0, 0, KEY_Z - .75) * bd.extrude(outline, amount=1.5)
    s += e.rounded_box(31.3, CY, KEY_Z - .75, 2.2, 7, 2.6, .6)
    return s


@model
def locking_key():
    return e.check_part(locking_key_body(), 'v2_shroud_locking_key', '#D79C5B')


def socket_pose(shape):
    return bd.Pos(0, -89, -8) * bd.Rot(-90, 0, 0) * shape


def socket_body(bore=4.5):
    s = e.cylinder(0, 0, 0, 4, 9.1)
    s += e.cylinder(0, 0, 9, 5.4, 1.6)
    s -= e.cylinder(0, 0, -.1, bore / 2, 11)
    # Existing dock has a broad pin root: leave space before the grip section.
    s -= bd.Pos(0, 0, -.1) * bd.Cone(3.4, bore / 2, 2.1,
            align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    for angle in (0, 120, 240):
        s -= bd.Rot(0, 0, angle) * e.box(3.0, 0, -.1, 6.2, .8, 8.3)
    return s


@model
def socket_nominal():
    return e.check_part(socket_body(4.5), 'v2_socket_4p50_nominal', '#D79C5B')


@model
def socket_snug():
    return e.check_part(socket_body(4.35), 'v2_socket_4p35_snug_trial', '#D79C5B')


@model
def socket_loose():
    return e.check_part(socket_body(4.65), 'v2_socket_4p65_loose_trial', '#D79C5B')


@model
def heel_v2():
    s = e.rounded_box(0, -74.5, -16, 26, 29, 16, 3)
    # Sleeve loads axially from the heel's upper end before the keeper is fitted.
    s -= socket_pose(e.cylinder(0, 0, -.1, 4.2, 9.2))
    s -= socket_pose(e.cylinder(0, 0, 9, 5.7, 21))
    for x in (-8, 8):
        s += heel_stud(x)
    s -= e.box(0, KEEPER_Y, -13.2, 3.5, 3.5, 14)
    return e.check_part(s, 'v2_detachable_stand_heel', '#39434C')


@model
def heel_keeper():
    s = e.box(0, KEEPER_Y, -13, 3, 3, 15.5)
    s += e.rounded_box(0, KEEPER_Y, 2.4, 22, 5, 2, .7)
    return e.check_part(s, 'v2_internal_heel_and_socket_keeper', '#D79C5B')


def print_flip(shape, top_z):
    return bd.Pos(0, 0, top_z) * bd.Rot(180, 0, 0) * shape


@model
def front_v2_print():
    return e.check_part(print_flip(front_v2().shape, e.FRONT_OUTER),
                        'v2_front_print_face_down', '#B8C2C7')


@model
def shroud_print():
    return e.check_part(print_flip(aperture_shroud().shape, HORN_TOP),
                        'v2_shroud_print_mouth_down', '#D79C5B')


@model
def heel_v2_print():
    # Socket axis vertical; load mouth at bed. Only small stud shoulders overhang.
    s = bd.Pos(0, 8, 89) * bd.Rot(90, 0, 0) * heel_v2().shape
    return e.check_part(s, 'v2_heel_print_socket_axis_up', '#39434C')


@model
def keeper_print():
    return e.check_part(print_flip(heel_keeper().shape, 4.4), 'v2_keeper_print_head_down', '#D79C5B')


@model
def keys_print():
    s = bd.Pos(-28, -CY, -(KEY_Z - .75)) * locking_key().shape
    return bd.Compound(children=[s, bd.Pos(15, 0, 0) * s], label='v2_two_locking_keys_print')


@model
def key_print():
    return e.check_part(bd.Pos(-28, -CY, -(KEY_Z - .75)) * locking_key().shape,
                        'v2_single_locking_key_print', '#D79C5B')


@model
def key_snug_print():
    return e.check_part(bd.Pos(-28, -CY, -(KEY_Z - .75)) * locking_key_body(3.35),
                        'v2_locking_key_3p35_snug_trial', '#D79C5B')


@model
def key_loose_print():
    return e.check_part(bd.Pos(-28, -CY, -(KEY_Z - .75)) * locking_key_body(3.05),
                        'v2_locking_key_3p05_loose_trial', '#D79C5B')


@model
def socket_nominal_print():
    return e.check_part(print_flip(socket_nominal().shape, SOCKET_LENGTH),
                        'v2_socket_4p50_print', '#D79C5B')


@model
def socket_snug_print():
    return e.check_part(print_flip(socket_snug().shape, SOCKET_LENGTH),
                        'v2_socket_4p35_print', '#D79C5B')


@model
def socket_loose_print():
    return e.check_part(print_flip(socket_loose().shape, SOCKET_LENGTH),
                        'v2_socket_4p65_print', '#D79C5B')


def clipped_part(shape, crop, label):
    s = bd.Compound(children=shape.solids()[0].intersect(crop))
    return e.check_part(s, label, shape.color)


@model
def slider_rear_coupon():
    s = clipped_part(rear_v2().shape, e.box(24, 48, -.1, 14, 17, 15),
                     'v2_slider_rear_fit_coupon')
    return bd.Pos(-24, -48, 0) * s


@model
def slider_front_coupon():
    s = clipped_part(front_v2().shape, e.box(24, 48, 10, 14, 17, 14),
                     'v2_slider_front_fit_coupon')
    return bd.Pos(-24, 48, 0) * print_flip(s, e.FRONT_OUTER)


@model
def shroud_receiver_coupon():
    s = clipped_part(rear_v2().shape, e.box(26, CY, -.1, 8, 13, 15),
                     'v2_shroud_receiver_fit_coupon')
    return bd.Pos(-26, -CY, 0) * s


@model
def shroud_leg_coupon():
    s = clipped_part(aperture_shroud().shape, e.box(26, CY, 8, 4, 9, 15),
                     'v2_shroud_leg_fit_coupon')
    return bd.Pos(-26, CY, 0) * print_flip(s, HORN_TOP)


@model
def fit_coupons():
    return bd.Compound(children=[bd.Pos(-20, 25, 0) * slider_rear_coupon().shape,
        bd.Pos(0, 25, 0) * slider_front_coupon().shape,
        bd.Pos(20, 25, 0) * shroud_receiver_coupon().shape,
        bd.Pos(32, 25, 0) * shroud_leg_coupon().shape,
        bd.Pos(25, -9, 0) * key_loose_print().shape,
        bd.Pos(25, 0, 0) * key_print().shape,
        bd.Pos(25, 9, 0) * key_snug_print().shape,
        bd.Pos(-25, 0, 0) * socket_snug_print().shape,
        bd.Pos(-10, 0, 0) * socket_nominal_print().shape,
        bd.Pos(5, 0, 0) * socket_loose_print().shape], label='v2_print_first_fit_checks')


@model
def sockets_print():
    return bd.Compound(children=[bd.Pos(x, 0, 0) * print_flip(fun().shape, SOCKET_LENGTH)
        for x, fun in [(-15, socket_snug), (0, socket_nominal), (15, socket_loose)]],
        label='v2_socket_fit_trials_left_4p35_middle_4p50_right_4p65')


def hardwareless_parts():
    right = locking_key().shape
    left = bd.mirror(right, about=bd.Plane.YZ)
    left.label = 'v2_shroud_locking_key_left'
    left.color = right.color
    sleeve = socket_pose(socket_nominal().shape)
    return [rear_v2().shape, front_v2().shape, aperture_shroud().shape,
            right, left, heel_v2().shape, heel_keeper().shape, sleeve]


@model
def assembly_v2():
    return bd.Compound(children=[*hardwareless_parts(), e.board_reference().shape,
                                 e.cable_reference().shape], label='hardware_free_pill_v2_prototype')


@model
def desktop_v2():
    return bd.Compound(children=[dock.desktop_dock().shape, dock.case_pose(assembly_v2().shape)],
                        label='hardware_free_pill_v2_on_existing_dock')


@model
def exploded_v2():
    p = hardwareless_parts()
    placements = [bd.Pos(), bd.Pos(0, -SLIDE, 35), bd.Pos(0, 0, 65),
                  bd.Pos(14, 0, 65), bd.Pos(-14, 0, 65),
                  bd.Pos(0, -HEEL_SLIDE, -25), bd.Pos(0, 0, 14), bd.Pos(0, 20, -25)]
    return bd.Compound(children=[pose * part for pose, part in zip(placements, p)]
                        + [bd.Pos(0, 0, 14) * e.board_reference().shape], label='v2_assembly_order_exploded')


@model
def insert_installation():
    p = hardwareless_parts()
    p[2] = bd.Pos(0, 0, 24) * p[2]
    p[3] = bd.Pos(12, 0, 24) * p[3]
    p[4] = bd.Pos(-12, 0, 24) * p[4]
    return bd.Compound(children=[*p, e.board_reference().shape, e.cable_reference().shape],
                        label='v2_cover_closed_then_insert_shroud_and_keys')


@model
def shroud_section():
    crop = e.box(CX + 50, CY, -20, 100, 200, 80)
    children = []
    for part in [rear_v2().shape, front_v2().shape, aperture_shroud().shape]:
        cut = part - crop
        cut.label = part.label + '_section'; cut.color = part.color
        children.append(cut)
    children.append(e.board_reference().shape)
    return bd.Compound(children=children, label='v2_aperture_section')


if __name__ == '__main__':
    assembly_v2()
    desktop_v2()
    exploded_v2()
    shroud_section()
