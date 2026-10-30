"""IWR6843AOPEVM Rev G full-board enclosure, dimensions in millimetres.

XY is the board plane, +Y up, +Z toward the radome. J1/data USB exits -Y.
Vendor reference is a PCB outline plus component envelopes, not a vendor STEP.
"""
import json
import math
from pathlib import Path

import build123d as bd
from cadgen import model

ROOT = Path(__file__).resolve().parents[1]
WIDTH, HEIGHT = 52.0, 174.0
WALL, FLOOR = 2.4, 2.4
PCB_BACK = 10.4
PCB_THICK = 1.6256
ANTENNA_HEIGHT = 0.964999
RADOME_THICK = 1.6
AIR_GAP = 3 * 299792458 / 62e9 * 1000 / 2  # 3 half wavelengths at 62 GHz
FRONT_INNER = PCB_BACK + PCB_THICK + ANTENNA_HEIGHT + AIR_GAP
FRONT_OUTER = FRONT_INNER + RADOME_THICK
SEAM = 14.0
CLOSURE_XY = [(-18.6, -47), (18.6, -47), (-18.6, 47), (18.6, 47)]
LID_BOSS_BASE = 10.4
USB_X, USB_Z = -0.3938, PCB_BACK - 1.45
NUT_Y, NUT_Z = -84.2, -8.0
HEEL_BACK = -16.0
M2_INSERT_BORE, M25_INSERT_BORE = 3.0, 3.3
OPEN_WINDOW_WIDTH, OPEN_WINDOW_HEIGHT, OPEN_WINDOW_RADIUS = 42.0, 44.0, 3.0


def data():
    return json.loads((ROOT / "vendor/board_geometry.json").read_text())


def box(x, y, z, dx, dy, dz):
    return bd.Pos(x, y, z) * bd.Box(dx, dy, dz, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))


def cylinder(x, y, z, radius, height):
    return bd.Pos(x, y, z) * bd.Cylinder(radius, height, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN))


def capsule(w, h, z, thickness):
    return bd.Pos(0, 0, z) * bd.extrude(bd.SlotOverall(h, w, rotation=90), amount=thickness)


def rounded_box(x, y, z, dx, dy, dz, r):
    return bd.Pos(x, y, z) * bd.extrude(bd.RectangleRounded(dx, dy, r), amount=dz)


def check_part(s, name, color):
    assert s.is_valid, name
    assert len(s.solids()) == 1, (name, len(s.solids()))
    assert s.volume > 0, name
    s.label, s.color = name, color
    return s


def along_y(shape, x, y, z):
    # Local +Z becomes world -Y; local XY becomes the mounting land's XZ.
    return bd.Pos(x, y, z) * bd.Rot(90, 0, 0) * shape


def usb_exit():
    # A split opening allows the shell to close around a connected cable.
    return along_y(bd.extrude(bd.RectangleRounded(14, 11, 2), amount=34), USB_X, -57, USB_Z + 1)


def nut_recess():
    hexagon = bd.RegularPolygon(11.5 / math.sqrt(3), 6)
    trap = along_y(bd.extrude(hexagon, amount=6.0), 0, NUT_Y + 3, NUT_Z)
    loading = box(0, NUT_Y, HEEL_BACK - 1, 13.4, 6.0, NUT_Z - HEEL_BACK + 1)
    return trap + loading


@model
def rear_shell():
    s = capsule(WIDTH, HEIGHT, 0, SEAM)
    edges = [e for e in s.edges() if abs(e.bounding_box().min.Z) < 1e-6 and abs(e.bounding_box().max.Z) < 1e-6]
    s = bd.fillet(edges, radius=1.5)
    s -= capsule(WIDTH - 2 * WALL, HEIGHT - 2 * WALL, FLOOR, SEAM + 1)
    # Continuous locating tongue; 0.30 mm radial clearance to front skirt.
    lip = capsule(48.2, 170.2, SEAM - 0.2, 2.5) - capsule(45.8, 167.8, SEAM - 0.3, 2.8)
    s += lip
    # Four structural columns carry the cover screw loads.
    for x, y in CLOSURE_XY:
        s += cylinder(x, y, FLOOR - 0.1, 3.7, LID_BOSS_BASE - FLOOR + 0.1)
        s -= cylinder(x, y, -0.2, 1.45, LID_BOSS_BASE + 0.5)
        s -= cylinder(x, y, -0.2, 2.6, 1.7)  # rear counterbore, 1.5 mm seat
    # The only two mounting holes on the depanelled board are 2.54 mm.
    for h in data()["mounting_holes"]:
        x, y = h["xy"]
        s += cylinder(x, y, FLOOR - 0.1, 2.65, PCB_BACK - FLOOR + 0.1)
        s -= cylinder(x, y, PCB_BACK - 4.0, M2_INSERT_BORE / 2, 4.2)
        s -= cylinder(x, y, PCB_BACK - 6.0, 1.05, 6.2)
    # Edge saddles stop the long board flexing; contact only the PCB margins.
    for x, y in [(-11.7, 44), (-11.7, 14), (-7.15, -42), (7.4, -42)]:
        s += box(x, y, FLOOR - 0.1, 1.2, 4.0, PCB_BACK - FLOOR + 0.1)
    # Rear heel with a real metal 1/4-20 nut, loaded through a covered rear slot.
    heel = rounded_box(0, -74.5, HEEL_BACK, 26, 29, 3.8 - HEEL_BACK, 3)
    spine = rounded_box(0, -55, -4.0, 22, 22, 6.5, 3)
    s += heel + spine
    s -= nut_recess()
    s -= along_y(bd.Cylinder(3.4, 23, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)), 0, -66, NUT_Z)
    for x in [-9, 9]:
        s -= cylinder(x, NUT_Y, HEEL_BACK - 0.1, M2_INSERT_BORE / 2, 4.1)
        s -= cylinder(x, NUT_Y, HEEL_BACK - 0.1, 1.05, 7)
    s -= usb_exit()
    # Rear ventilation over the heatsink and the upper electronics. Slots are 2 mm.
    for y in [-29, -24, -19, -14, 8, 13, 18, 23, 28, 33, 38]:
        s -= rounded_box(0, y, -0.2, 15 if y < 0 else 13, 2, FLOOR + 0.4, 0.9)
    # Cable-tie bridge, under the plug boot; tie acts as a load stop, not a seal.
    s += box(USB_X, -74, FLOOR - 0.1, 11, 3.0, 2.6)
    for x in [USB_X - 3.6, USB_X + 3.6]:
        s -= box(x, -74, HEEL_BACK - 0.2, 2.4, 3.8, 6 - HEEL_BACK)
    # Small rear access to S3; front switches are exposed by removing the cover.
    s -= rounded_box(4.2, -11.95, -0.2, 8, 5, FLOOR + 0.4, 1)
    return check_part(s, "rear_shell", "#343C44")


@model
def front_radome():
    outer = capsule(WIDTH, HEIGHT, SEAM, FRONT_OUTER - SEAM)
    edges = [e for e in outer.edges() if abs(e.bounding_box().min.Z - FRONT_OUTER) < 1e-6]
    outer = bd.fillet(edges, radius=5.5)
    cavity = capsule(WIDTH - 2 * RADOME_THICK, HEIGHT - 2 * RADOME_THICK, SEAM - 1, FRONT_INNER - SEAM + 1)
    edges = [e for e in cavity.edges() if abs(e.bounding_box().min.Z - FRONT_INNER) < 1e-6]
    cavity = bd.fillet(edges, radius=5.5 - RADOME_THICK)
    s = outer - cavity
    for x, y in CLOSURE_XY:
        s += cylinder(x, y, LID_BOSS_BASE, 3.7, FRONT_INNER - LID_BOSS_BASE + 0.1)
        s -= cylinder(x, y, LID_BOSS_BASE - 0.1, M25_INSERT_BORE / 2, 4.1)
        s -= cylinder(x, y, LID_BOSS_BASE - 0.1, 1.35, 8.4)
    s -= usb_exit()
    # At the antenna centre the front is a homogeneous 1.6 mm wall.
    assert abs(s.bounding_box().max.Z - FRONT_OUTER) < 1e-5
    return check_part(s, "front_radome", "#E3E7E7")


def radar_window_centre():
    antenna = next(c for c in data()["components"] if c["name"] == "U2")
    return ((antenna["xmin"] + antenna["xmax"]) / 2,
            (antenna["ymin"] + antenna["ymax"]) / 2)


@model
def front_open_aperture():
    # Same skirt and fasteners as the closed front, with no membrane over U2.
    x, y = radar_window_centre()
    opening = rounded_box(x, y, LID_BOSS_BASE - 1,
                          OPEN_WINDOW_WIDTH, OPEN_WINDOW_HEIGHT,
                          FRONT_OUTER - LID_BOSS_BASE + 2, OPEN_WINDOW_RADIUS)
    s = front_radome().shape - opening
    return check_part(s, "front_open_aperture", "#E3E7E7")


@model
def nut_retainer():
    p = rounded_box(0, NUT_Y, HEEL_BACK - 2.4, 25.4, 9, 2.4, 2)
    # A locating pad leaves 0.20 mm behind the nut, maintaining screw alignment.
    p += box(0, NUT_Y, HEEL_BACK - 0.1, 10, 5.5, NUT_Z - 5.55625 - 0.2 - HEEL_BACK + 0.1)
    for x in [-9, 9]:
        p -= cylinder(x, NUT_Y, HEEL_BACK - 2.6, 1.15, 2.8)
    return check_part(p, "nut_retainer", "#59636C")


@model
def board_reference():
    d = data()
    pcb = bd.Pos(0, 0, PCB_BACK) * bd.extrude(bd.Polygon(*[tuple(p) for p in d["outline"]], align=None), amount=PCB_THICK, dir=(0, 0, 1))
    for h in d["mounting_holes"]:
        pcb -= cylinder(*h["xy"], PCB_BACK - 0.1, h["diameter"] / 2, PCB_THICK + 0.2)
    pcb.label, pcb.color = "pcb_PROC091G", "#B93938"
    assert pcb.is_valid and len(pcb.solids()) == 1 and pcb.volume > 0
    assert 25 < pcb.bounding_box().size.X < 26
    assert 115 < pcb.bounding_box().size.Y < 116
    assert abs(pcb.bounding_box().size.Z - PCB_THICK) < 1e-5
    children = [pcb]
    seen = set()
    for c in sorted(d["components"], key=lambda b: (b["xmax"]-b["xmin"])*(b["ymax"]-b["ymin"]), reverse=True):
        if c["name"] in seen:
            continue
        seen.add(c["name"])
        h = max(c["height"], 3.5 if c["name"] in ["J6", "J10"] else 1.2)
        if c["name"] == "U2":
            h = ANTENNA_HEIGHT
        z = PCB_BACK + PCB_THICK if c["layer"] == "TOP" else PCB_BACK - h
        b = box((c["xmin"]+c["xmax"])/2, (c["ymin"]+c["ymax"])/2, z,
                c["xmax"]-c["xmin"], c["ymax"]-c["ymin"], h)
        b.label = "ref_" + c["name"]
        b.color = "#C6A460" if c["name"] == "U2" else "#888F96" if c["name"].startswith("J") else "#20282C"
        children.append(b)
    # Conservative clearance envelope; heatsink shape/attachment must be dry-fitted.
    hs = box(0.2, -20.1, PCB_BACK - 5.8, 17.6, 30.0, 5.8)
    hs.label, hs.color = "ref_heatsink_envelope", "#252B30"
    children.append(hs)
    return bd.Compound(children=children, label="reference_board_not_printable")


@model
def quarter_inch_nut():
    n = along_y(bd.extrude(bd.RegularPolygon(11.1125 / math.sqrt(3), 6), amount=5.55625), 0, NUT_Y + 2.778125, NUT_Z)
    n -= along_y(bd.Cylinder(2.6, 6.0, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)), 0, NUT_Y + 3, NUT_Z)
    return check_part(n, "hardware_1_4_20_nut_threads_schematic", "#BBA16A")


@model
def cable_reference():
    boot = rounded_box(USB_X, -68.5, USB_Z - 3, 11, 20, 6, 1.5)
    cable = along_y(bd.Cylinder(2.2, 33, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)), USB_X, -77.5, USB_Z)
    s = boot + cable
    return check_part(s, "ref_straight_USB_boot_11x20x6_cable_4p4", "#222A31")


@model
def assembly():
    return bd.Compound(children=[rear_shell().shape, front_radome().shape,
                                nut_retainer().shape, board_reference().shape,
                                quarter_inch_nut().shape, cable_reference().shape],
                       label="IWR6843AOP_pill_enclosure")


@model
def assembly_open_aperture():
    return bd.Compound(children=[rear_shell().shape, front_open_aperture().shape,
                                nut_retainer().shape, board_reference().shape,
                                quarter_inch_nut().shape, cable_reference().shape],
                       label="IWR6843AOP_open_aperture_enclosure")


@model
def exploded():
    front = bd.Pos(0, 0, 36) * front_radome().shape
    board = bd.Pos(0, 0, 14) * board_reference().shape
    retainer = bd.Pos(0, 0, -16) * nut_retainer().shape
    nut = bd.Pos(0, 0, -7) * quarter_inch_nut().shape
    return bd.Compound(children=[rear_shell().shape, front, board, retainer, nut], label="exploded_assembly")


if __name__ == "__main__":
    assembly()
    exploded()
    front_open_aperture()
    assembly_open_aperture()
