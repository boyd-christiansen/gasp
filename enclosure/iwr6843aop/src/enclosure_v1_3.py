"""v1.3 rear revision from physical PLA print feedback.

Reinforce the four board-edge saddles without moving the PCB or fasteners.
Add a 45-degree roof to the 1/4-20 access bore to reduce internal support.
The existing front, retainer, washers, nut and desktop dock remain compatible.
"""
import math
import build123d as bd
from cadgen import model
import enclosure as e
from enclosure_v1_2 import rear_standard_ties, assembled_washers

SADDLES = [(-11.7, 44), (-11.7, 14), (-7.15, -42), (7.4, -42)]
SADDLE_TOP_WIDTH = 2.8
SADDLE_TOP_LENGTH = 6.0
SADDLE_ROOT_WIDTH = 6.8
SADDLE_ROOT_LENGTH = 10.0


def reinforced_saddle(x, y):
    outward = -1 if x < 0 else 1
    # Preserve the original inner edge, so added width grows away from components.
    inner = x - outward * .6
    top_x = inner + outward * SADDLE_TOP_WIDTH / 2
    root_x = inner + outward * SADDLE_ROOT_WIDTH / 2
    root = bd.Pos(root_x, y, e.FLOOR - .1) * bd.RectangleRounded(SADDLE_ROOT_WIDTH, SADDLE_ROOT_LENGTH, 1.2)
    top = bd.Pos(top_x, y, e.PCB_BACK - 1) * bd.RectangleRounded(SADDLE_TOP_WIDTH, SADDLE_TOP_LENGTH, .6)
    s = bd.loft([root, top])
    s += e.rounded_box(top_x, y, e.PCB_BACK - 1.1, SADDLE_TOP_WIDTH, SADDLE_TOP_LENGTH, 1.1, .6)
    # The upper saddle's root meets a cover column. Keep its original bore
    # clear while allowing the two structures to share a broad foundation.
    for hx, hy in e.CLOSURE_XY:
        s -= e.cylinder(hx, hy, -.2, 1.45, e.LID_BOSS_BASE + .5)
    assert s.is_valid and len(s.solids()) == 1
    assert abs(s.bounding_box().max.Z - e.PCB_BACK) < 1e-6
    return s


def mount_roof_relief():
    # Tangent 45-degree roof above the original Ø6.8 circular clearance bore.
    r = 3.4
    tangent = r / math.sqrt(2)
    triangle = bd.Polygon((-tangent, tangent), (tangent, tangent), (0, r * math.sqrt(2)), align=None)
    return e.along_y(bd.extrude(triangle, amount=23.2), 0, -65.9, e.NUT_Z)


@model
def rear_reinforced():
    s = rear_standard_ties().shape
    for x, y in SADDLES:
        s += reinforced_saddle(x, y)
    s -= mount_roof_relief()
    return e.check_part(s, 'rear_shell_v1_3_reinforced_saddles', '#343C44')


@model
def rear_reinforced_print():
    # Preserve the cavity-up orientation; heel rests on the plate at Z=0.
    # External support is still required beneath the raised rear floor/spine.
    s = bd.Pos(0, 0, -e.HEEL_BACK) * rear_reinforced().shape
    assert abs(s.bounding_box().min.Z) < 1e-5
    return e.check_part(s, 'rear_shell_v1_3_print_cavity_up', '#343C44')


@model
def assembly_v1_3():
    return bd.Compound(children=[rear_reinforced().shape, e.front_radome().shape,
        e.nut_retainer().shape, e.board_reference().shape, e.quarter_inch_nut().shape,
        e.cable_reference().shape, *assembled_washers()], label='pill_enclosure_v1_3')


@model
def saddle_comparison():
    # Actual old and new geometry, separated for close-up inspection.
    old = e.box(0, 0, 0, 1.2, 4, e.PCB_BACK - e.FLOOR)
    old.label = 'old_1p2mm_blade'; old.color = '#B78C65'
    new = bd.Pos(30 + 11.7, -14, -e.FLOOR) * reinforced_saddle(-11.7, 14)
    new.label = 'new_2p8mm_saddle_with_6p8mm_root'; new.color = '#499B8A'
    return bd.Compound(children=[old, new], label='board_edge_support_before_and_after')


if __name__ == '__main__':
    rear_reinforced()
    rear_reinforced_print()
    assembly_v1_3()
    saddle_comparison()
