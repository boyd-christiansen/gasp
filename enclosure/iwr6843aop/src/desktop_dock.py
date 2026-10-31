"""Drop-in tabletop dock for the single-board pill enclosure v1.2.

Dock-local axes: X across, Y behind the radar, Z up the mount socket.
World: Z up, radar looks toward -Y and 20 degrees above horizontal.
The smooth pin locates inside the existing nut; the heel rests on the cradle.
This is a gravity-retained desk dock, not a threaded or locking attachment.
"""
import build123d as bd
from cadgen import model
import enclosure as e
from enclosure_v1_2 import assembly_v1_2, assembly_open_v1_2

PITCH = 20.0
SEAT_HEIGHT = 30.0
FOOT_WIDTH, FOOT_DEPTH, FOOT_THICKNESS = 100.0, 120.0, 5.0
FOOT_Y = 12.0
PIN_DIAMETER, PIN_LENGTH = 4.5, 7.4
CRADLE_HEIGHT = 10.0
CRADLE_INNER_WIDTH = 26.8
CRADLE_BACK = 10.8


def dock_pose(shape):
    return bd.Pos(0, 0, SEAT_HEIGHT) * bd.Rot(-PITCH, 0, 0) * shape


def case_pose(shape):
    # Case mount face is Y=-89, axis X=0/Z=-8, facing down the case's -Y.
    return dock_pose(bd.Rot(90, 0, 0) * bd.Pos(0, 89, -e.NUT_Z) * shape)


def smooth_pin():
    # Broad lead at the root stays below the metal nut, which starts 2.022 mm
    # inside the heel. The long 4.5 mm section clears the internal thread crests.
    pin = bd.Pos(0, 0, -.1) * bd.Cone(3.0, PIN_DIAMETER / 2, .9,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    pin += e.cylinder(0, 0, .7, PIN_DIAMETER / 2, PIN_LENGTH - .7 - .6)
    pin += bd.Pos(0, 0, PIN_LENGTH - .6) * bd.Cone(PIN_DIAMETER / 2, 1.65, .6,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))
    return pin


def cradle():
    floor = e.rounded_box(0, 3.9, -4, 32.8, 19.8, 4, 3)
    walls = e.rounded_box(0, 3.9, -.1, 32.8, 19.8, CRADLE_HEIGHT + .1, 3)
    # U-shaped cradle leaves the front, USB cable and curved pill body free.
    # Slight opening taper helps the enclosure slide into the pocket.
    pocket = bd.loft([
        bd.Pos(0, -4.6, -.2) * bd.Rectangle(CRADLE_INNER_WIDTH, 30.8),
        bd.Pos(0, -4.35, CRADLE_HEIGHT + .2) * bd.Rectangle(CRADLE_INNER_WIDTH + 1, 31.3)])
    walls -= pocket
    # Open-top reliefs for the two rear retainer screw heads, up to 4.5 mm OD
    # and 2.5 mm projection. They also leave the screw heads accessible.
    for x in [-9, 9]:
        walls -= e.box(x, 13, 1.8, 6, 7, 12)
    result = floor + walls + smooth_pin()
    return e.check_part(result, 'drop_in_heel_cradle', '#343C44')


@model
def desktop_dock():
    foot = e.rounded_box(0, FOOT_Y, 0, FOOT_WIDTH, FOOT_DEPTH, FOOT_THICKNESS, 25)
    foot = bd.fillet(foot.faces().sort_by(bd.Axis.Z)[-1].edges(), 1.2)
    # Open groove leads the USB cable toward the front edge of the foot.
    # Its 2.5 mm floor keeps the underside flat and avoids a trapped tunnel.
    foot -= e.rounded_box(e.USB_X, -36, 2.5, 7.4, 40, 4, 3)
    # A tapered solid pedestal joins the sloping cradle to the flat foot.
    lower = bd.Pos(0, 5, 4.5) * bd.RectangleRounded(46, 38, 8)
    upper = dock_pose(bd.Pos(0, 3.9, -3.8) * bd.RectangleRounded(32.8, 19.8, 3))
    pedestal = bd.loft([lower, upper])
    result = foot + pedestal + dock_pose(cradle())
    bounds = result.bounding_box()
    assert abs(bounds.min.Z) < 1e-6
    assert abs(bounds.size.X - FOOT_WIDTH) < 1e-5
    assert abs(bounds.size.Y - FOOT_DEPTH) < 1e-5
    return e.check_part(result, 'single_board_desktop_dock_20deg', '#343C44')


@model
def dock_fit_test():
    # Optional small coupon: the exact cradle and pin, without the full stand.
    result = bd.Pos(0, 0, 4) * cradle()
    return e.check_part(result, 'optional_cradle_fit_test', '#E5A649')


@model
def desktop_assembly():
    return bd.Compound(children=[desktop_dock().shape, case_pose(assembly_v1_2().shape)],
                       label='single_board_enclosure_on_drop_in_dock')


@model
def desktop_assembly_open():
    return bd.Compound(children=[desktop_dock().shape, case_pose(assembly_open_v1_2().shape)],
                       label='open_front_enclosure_on_drop_in_dock')


if __name__ == '__main__':
    desktop_dock()
    dock_fit_test()
    desktop_assembly()
    desktop_assembly_open()
