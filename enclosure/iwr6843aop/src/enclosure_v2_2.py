"""v2.2 physical-fit revision: cable clearance and preloaded hardware-free mount.

Reuses v2.1's board supports, TP20 clearance, shroud and the existing desktop dock.
Dimensions are mm. Fit remains a print trial, including the two compliant fits.
"""
import build123d as bd
from cadgen import model
import enclosure as e
import enclosure_v2 as v
import desktop_dock as dock

CABLE_PASSAGE = 10.0
SOCKET_BORE = 4.35
SHOE_CLEARANCE = .15  # each side and the back, after the entry lead
CLIP_PRELOAD = .10
HEAD_UNDERSIDE = 4.0
CLIP_INSERT_OFFSET = 7.4


def cable_clearance():
    return e.along_y(bd.Cylinder(CABLE_PASSAGE / 2, 30,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)), e.USB_X, -65, e.USB_Z)


@model
def rear_v22():
    s = v.rear_v2().shape
    s -= cable_clearance()
    # 0.2 mm pockets beneath the four springs permit preload while the clip
    # itself has a flat underside for support-free printing.
    for x in (-8, 8):
        for offset in (-3.4, 3.4):
            s -= e.box(x + offset, -68.35, 2.2, 2.4, 7.7, .21)
    # Path for the clip's rear crossbar, below the cable's molded sleeve.
    s -= e.box(0, -79.75, 2.4, 28.6, 1.8, 1.3)
    return e.check_part(s, 'v2_2_rear_10mm_cable_TP20', '#39434C')


@model
def front_v22():
    s = v.front_v2().shape
    # Keep the original T-keeper capture pads. Closing the lid also traps the
    # new preload fork, which inserts from the board end toward the USB end.
    for x in (-13.4, 13.4):
        s += e.box(x, -63.2, 5.2, 2.4, 4, e.FRONT_INNER - 5.1)
    s -= cable_clearance()
    return e.check_part(s, 'v2_2_front_cable_and_clip_capture', '#B8C2C7')


def fitted_shoe():
    sections = []
    for z, lead in ((0, .4), (1.2, 0), (10, 0)):
        pocket_width = 26.8 + (z + .2) / 10.4
        back = 10.8 + .5 * (z + .2) / 10.4 - SHOE_CLEARANCE - lead
        width = pocket_width - 2 * SHOE_CLEARANCE - 2 * lead
        front = -8.0
        sections.append(bd.Pos(0, (front + back) / 2, z)
                        * bd.RectangleRounded(width, back - front, 1.8))
    return v.socket_pose(bd.loft(sections, ruled=True))


def mount_stud(x):
    s = e.box(x, -68, -.1, 4.3, 3.0, HEAD_UNDERSIDE + .2)
    s += e.rounded_box(x, -68, HEAD_UNDERSIDE, 8, 7, 1.6, .6)
    return s


@model
def heel_v22():
    s = e.rounded_box(0, -74.5, -16, 26, 29, 16, 3) + fitted_shoe()
    s -= v.socket_pose(e.cylinder(0, 0, -.1, 4.2, 9.2))
    s -= v.socket_pose(e.cylinder(0, 0, 9, 5.7, 21))
    # Keep the tested three slotted fingers, but fuse their flange into the heel.
    # There is no independently floating sleeve in this revision.
    socket = v.socket_body(SOCKET_BORE)
    flange = e.cylinder(0, 0, 9, 6.0, 1.6) - e.cylinder(0, 0, 8.9, SOCKET_BORE / 2, 1.8)
    socket += flange
    s += v.socket_pose(socket)
    for x in (-8, 8):
        s += mount_stud(x)
    s -= e.box(0, v.KEEPER_Y, -13.2, 3.5, 3.5, 14)
    return e.check_part(s, 'v2_2_fitted_heel_integral_4p35_socket', '#39434C')


def contact_ramp(x):
    # Short ramp on the free end of each arm. Only this pad intrudes into the
    # T-head by 0.10 mm; the 0.20 mm space below the arm allows that deflection.
    profile = bd.Plane.YZ * bd.Polygon((-68.4, 3.59), (-67.4, HEAD_UNDERSIDE + CLIP_PRELOAD),
        (-66.2, HEAD_UNDERSIDE + CLIP_PRELOAD), (-65.2, 3.59), align=None)
    return bd.Pos(0, -136, 0) * bd.mirror(bd.Pos(x - .75, 0, 0) * bd.extrude(profile, amount=1.5), about=bd.Plane.XZ)


@model
def mount_clip():
    s = e.rounded_box(0, -72.7, 2.4, 26, 2.1, 2.6, .5)
    for x in (-8, 8):
        fork = e.box(x, -68.5, 2.4, 9, 8.0, 1.2)
        fork -= e.box(x, -66.5, 2.3, 4.6, 6.3, 1.5)
        s += fork
    s = bd.Pos(0, -136, 0) * bd.mirror(s, about=bd.Plane.XZ)
    for x in (-8, 8):
        for offset in (-3.1, 3.1):
            s += contact_ramp(x + offset)
    # The reused T-keeper drops inside this frame after the clip has slid home.
    # Its head blocks the crossbar, preventing the preload clip backing out.
    for x in (-13.5, 13.5):
        s += e.box(x, -71.3, 2.4, 1.4, 18.1, 1.2)
    s += e.box(0, -79.75, 2.4, 28.4, 1.2, 1.2)
    return e.check_part(s, 'v2_2_preload_fork_slide_toward_USB', '#E5A649')


def key_body(width):
    profile = bd.Polygon((23.3, v.CY - 1.225), (30.3, v.CY - width / 2),
        (30.3, v.CY + width / 2), (23.3, v.CY + 1.225), align=None)
    s = bd.Pos(0, 0, v.KEY_Z - .7) * bd.extrude(profile, amount=1.4)
    s += e.rounded_box(32.6, v.CY, v.KEY_Z - .7, 4.8, 8.5, 2.6, .65)
    # Rectangular seven-segment strokes keep labels printable at a 0.4 mm nozzle
    # and avoid tiny font splines in the solid model.
    segments = {'0': 'abcdef', '2': 'abged', '3': 'abgcd', '5': 'afgcd'}
    bars = {'a': (0, 1, 1.35, .4), 'b': (.475, .5, .4, 1.0),
            'c': (.475, -.5, .4, 1.0), 'd': (0, -1, 1.35, .4),
            'e': (-.475, -.5, .4, 1.0), 'f': (-.475, .5, .4, 1.0),
            'g': (0, 0, 1.35, .4)}
    strokes, cursor = [], 0.0
    for char in f'{width:.2f}':
        if char == '.':
            strokes.append(e.box(cursor, -1, 0, .4, .4, .41))
            cursor += 1.15
        else:
            for segment in segments[char]:
                x, y, w, h = bars[segment]
                strokes.append(e.box(cursor + x, y, 0, w, h, .41))
            cursor += 1.8
    label = bd.Compound(children=strokes)
    center = label.bounding_box().center()
    label = bd.Pos(-center.X, -center.Y, 0) * label
    for stroke in label.solids():
        s += bd.Pos(32.6, v.CY, v.KEY_Z + 1.89) * bd.Rot(0, 0, 90) * stroke
    return s


@model
def key_320():
    return e.check_part(key_body(3.20), 'v2_2_key_3p20_easier', '#D79C5B')


@model
def key_335():
    return e.check_part(key_body(3.35), 'v2_2_key_3p35_firmer', '#D79C5B')


@model
def cable_reference_v22():
    s = e.cable_reference().shape
    s += e.along_y(bd.Cylinder(4.5, 12, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)),
                  e.USB_X, -78.5, e.USB_Z)
    s.label = 'ref_assumed_9mm_molded_strain_relief'
    s.color = '#22272B'
    return s


@model
def front_print_v22():
    return e.check_part(v.print_flip(front_v22().shape, e.FRONT_OUTER), 'v2_2_front_print', '#B8C2C7')


@model
def heel_print_v22():
    return e.check_part(bd.Pos(0, 8, 89) * bd.Rot(90, 0, 0) * heel_v22().shape,
                        'v2_2_heel_print_socket_axis_up', '#39434C')


@model
def clip_print_v22():
    s = bd.Pos(0, 71.3, -2.4) * mount_clip().shape
    return e.check_part(s, 'v2_2_clip_print_flat_no_supports', '#E5A649')


@model
def key_320_print():
    return e.check_part(bd.Pos(-29, -v.CY, -(v.KEY_Z - .7)) * key_320().shape,
                        'v2_2_key_3p20_print', '#D79C5B')


@model
def key_335_print():
    return e.check_part(bd.Pos(-29, -v.CY, -(v.KEY_Z - .7)) * key_335().shape,
                        'v2_2_key_3p35_print', '#D79C5B')


def hardwareless_parts():
    right = key_320().shape
    left = bd.Pos(0, v.CY, 0) * bd.Rot(0, 0, 180) * bd.Pos(0, -v.CY, 0) * right
    left.label = 'v2_2_key_3p20_left'
    return [rear_v22().shape, front_v22().shape, v.aperture_shroud().shape,
            right, left, heel_v22().shape, mount_clip().shape, v.heel_keeper().shape]


@model
def assembly_v22():
    return bd.Compound(children=[*hardwareless_parts(), e.board_reference().shape,
        cable_reference_v22().shape], label='hardware_free_pill_v2_2_fit_revision')


@model
def desktop_v22():
    return bd.Compound(children=[dock.desktop_dock().shape, dock.case_pose(assembly_v22().shape)],
                       label='v2_2_on_reused_desktop_stand')


@model
def print_first_v22():
    return bd.Compound(children=[bd.Pos(-22, 0, 0) * heel_print_v22().shape,
        bd.Pos(-22, -29, 0) * clip_print_v22().shape,
        bd.Pos(14, -12, 0) * key_320_print().shape,
        bd.Pos(14, 0, 0) * key_320_print().shape,
        bd.Pos(32, -12, 0) * key_335_print().shape,
        bd.Pos(32, 0, 0) * key_335_print().shape], label='v2_2_print_first_mount_and_labeled_keys')


@model
def case_pair_v22():
    return bd.Compound(children=[bd.Pos(-35, 0, 0) * rear_v22().shape,
        bd.Pos(35, 0, 0) * front_print_v22().shape], label='v2_2_reprint_back_and_front')


@model
def mechanism_detail_v22():
    crop = e.box(0, -75, -25, 70, 40, 70)
    rear = v.clipped_part(rear_v22().shape, crop, 'rear_end_section')
    front = v.clipped_part(front_v22().shape, crop, 'front_end_section')
    return bd.Compound(children=[rear, heel_v22().shape, v.heel_keeper().shape,
        bd.Pos(0, 10, 10) * mount_clip().shape,
        bd.Pos(0, 0, 32) * front], label='v2_2_mount_clip_and_cable_detail_exploded')


@model
def mount_installation_v22():
    crop = e.box(0, -75, -25, 70, 40, 70)
    rear = v.clipped_part(rear_v22().shape, crop, 'rear_end_section')
    first = bd.Compound(children=[rear.moved(bd.Location()), heel_v22().shape,
        bd.Pos(0, CLIP_INSERT_OFFSET, 10) * mount_clip().shape], label='1_lower_clip_then_slide_toward_USB')
    second = bd.Compound(children=[rear, heel_v22().shape, mount_clip().shape,
        bd.Pos(0, 0, 14) * v.heel_keeper().shape], label='2_insert_existing_T_keeper')
    return bd.Compound(children=[bd.Pos(-37, 0, 0) * first, bd.Pos(37, 0, 0) * second],
                       label='v2_2_mount_assembly_before_board_and_cable')


if __name__ == '__main__':
    assembly_v22()
    desktop_v22()
    print_first_v22()
    case_pair_v22()
    mechanism_detail_v22()
    mount_installation_v22()
