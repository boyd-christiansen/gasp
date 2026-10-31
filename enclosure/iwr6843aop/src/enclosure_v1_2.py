"""v1.2: common 2.5 mm cable ties and two printable PCB washers.

The original enclosure.py and its model identities remain unchanged.
"""
import math
import build123d as bd
from cadgen import model
from cadgen.geometry import overlap_volume
from enclosure import (
    rear_shell, front_radome, front_open_aperture, nut_retainer,
    board_reference, quarter_inch_nut, cable_reference, check_part,
    box, cylinder, data, USB_X, FLOOR, HEEL_BACK, PCB_BACK, PCB_THICK,
)


@model
def rear_standard_ties():
    s = rear_shell().shape
    # Refill and widen the anchor bridge before making the larger through-slots.
    # This leaves 1.1 mm outside each slot and 4.2 mm between the slots.
    s += box(USB_X, -74, FLOOR - 0.1, 12.4, 3.0, 2.6)
    for x in [USB_X - 3.6, USB_X + 3.6]:
        s -= box(x, -74, HEEL_BACK - 0.2, 3.0, 3.8, 6 - HEEL_BACK)
        gauge = box(x, -74, HEEL_BACK - 1, 2.8, 3.4, 7 - HEEL_BACK)
        assert overlap_volume(s, gauge) < 1e-6, "Tie slot clearance"
    bridge = box(USB_X, -74, FLOOR, 4.2, 3.0, 2.4)
    assert abs(overlap_volume(s, bridge) - bridge.volume) < 1e-5
    return check_part(s, "rear_shell_v1_2_standard_ties", "#343C44")


@model
def pcb_washer():
    # Three layers at 0.20 mm; a slightly oversized bore for an M2 screw.
    s = cylinder(0, 0, 0, 2.2, 0.6) - cylinder(0, 0, -0.1, 1.15, 0.8)
    bounds = s.bounding_box().size
    assert abs(bounds.X - 4.4) < 1e-6 and abs(bounds.Z - 0.6) < 1e-6
    assert abs(s.volume - math.pi * (2.2**2 - 1.15**2) * 0.6) < 1e-6
    return check_part(s, "pcb_washer_OD4p4_ID2p3_T0p6", "#E5A649")

@model
def washer_print_pair():
    return bd.Compound(children=[bd.Pos(-4, 0, 0) * pcb_washer().shape,
                                 bd.Pos(4, 0, 0) * pcb_washer().shape],
                       label="two_printable_PCB_washers")


def assembled_washers():
    return [bd.Pos(*h["xy"], PCB_BACK + PCB_THICK) * pcb_washer().shape
            for h in data()["mounting_holes"]]


@model
def assembly_v1_2():
    return bd.Compound(children=[rear_standard_ties().shape, front_radome().shape,
        nut_retainer().shape, board_reference().shape, quarter_inch_nut().shape,
        cable_reference().shape, *assembled_washers()], label="pill_enclosure_v1_2")


@model
def assembly_open_v1_2():
    return bd.Compound(children=[rear_standard_ties().shape, front_open_aperture().shape,
        nut_retainer().shape, board_reference().shape, quarter_inch_nut().shape,
        cable_reference().shape, *assembled_washers()], label="open_aperture_enclosure_v1_2")


@model
def v1_2_changed_parts():
    return bd.Compound(children=[rear_standard_ties().shape,
        bd.Pos(35, -65, 10) * pcb_washer().shape,
        bd.Pos(35, -55, 10) * pcb_washer().shape], label="v1_2_rear_and_washers")


if __name__ == "__main__":
    rear_standard_ties()
    pcb_washer()
    washer_print_pair()
    assembly_v1_2()
    assembly_open_v1_2()
    v1_2_changed_parts()
