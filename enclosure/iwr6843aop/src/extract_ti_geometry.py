"""Extract mechanical reference coordinates from TI SPRR418A, PROC091 Rev G.

Source coordinates are inches in ODB++, mils in Altium ASCII. The enclosure
uses +Y toward the broad power-only end, +Z toward the antenna, and mm.
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
TI = ROOT / "vendor/sprr418/Rev.G"


def mil(value):
    return float(value.removesuffix("mil")) * 0.0254


def main():
    profile = TI / "Fabrication Package/ODB/odb/steps/pcb/profile"
    points = [tuple(float(x) * 25.4 for x in line.split()[1:3])
              for line in profile.read_text().splitlines()
              if line.startswith(("OB ", "OS "))]
    cx = (min(p[0] for p in points) + max(p[0] for p in points)) / 2
    cy = (min(p[1] for p in points) + max(p[1] for p in points)) / 2

    def xy(x, y):
        return [round(-(y - cy), 6), round(x - cx, 6)]

    def altium_xy(x, y):
        # Verified against J1/J5/U2 in ODB++ component placement reports.
        return xy(mil(x) - 0.692 * 25.4, mil(y) - 1.534 * 25.4)

    records = [dict(s.split("=", 1) for s in line.strip().split("|") if "=" in s)
               for line in (TI / "Altium Sources/PROC091G_ASCII.PcbDoc").read_text(errors="replace").splitlines()]
    components = {d["ID"]: d for d in records if d.get("RECORD") == "Component"}
    holes = []
    for d in records:
        if d.get("RECORD") == "Pad" and d.get("COMPONENT") in ("96", "171"):
            holes.append({"xy": altium_xy(d["X"], d["Y"]), "diameter": mil(d["HOLESIZE"])})
    keep = {"U2", "J1", "J2", "J3", "J5", "J6", "J7", "J8", "J10", "J11", "S1", "S2", "S3", "SW2", "SW3"}
    bodies = []
    for d in records:
        if d.get("RECORD") != "ComponentBody":
            continue
        c = components.get(d.get("COMPONENT"), {})
        name = c.get("SOURCEDESIGNATOR", "")
        if name not in keep:
            continue
        ps = [altium_xy(v, d["VY" + k[2:]]) for k, v in d.items()
              if k.startswith("VX") and k[2:].isdigit() and "VY" + k[2:] in d]
        if not ps:
            continue
        h = max(mil(c.get("HEIGHT", "0mil")), mil(d.get("OVERALLHEIGHT", "0mil")))
        if name == "U2":
            h = mil(c["HEIGHT"])
        bodies.append({"name": name, "layer": c["LAYER"],
                       "xmin": min(p[0] for p in ps), "xmax": max(p[0] for p in ps),
                       "ymin": min(p[1] for p in ps), "ymax": max(p[1] for p in ps),
                       "height": round(h, 6), "source_model": d.get("MODEL.NAME", "")})
    # TP20 lacks a height-bearing component body in the Altium extraction.
    # Its position and part number come from TI; the Keystone 4953 drawing
    # gives a roughly 9 mm exposed loop and 4 mm insertion post. Use a
    # conservative 3 mm square, independent of terminal clocking, and 9.2 mm
    # height; the opposite-face tail is bounded separately at 2.6 mm.
    tp20 = next(c for c in components.values() if c.get("SOURCEDESIGNATOR") == "TP20")
    tx, ty = altium_xy(tp20["X"], tp20["Y"])
    for name, layer, height in (("TP20", "BOTTOM", 9.2), ("TP20_tail", "TOP", 2.6)):
        bodies.append({"name": name, "layer": layer,
                       "xmin": tx - 1.5, "xmax": tx + 1.5,
                       "ymin": ty - 1.5, "ymax": ty + 1.5,
                       "height": height, "source_model": "",
                       "source_part": "Keystone 4953; TP20 on GND",
                       "source_drawing": "https://www.keyelco.com/product-pdf.cfm?p=1307",
                       "geometry_note": "Conservative clearance envelope; not exact terminal geometry."})
    data = {"source": "TI SPRR418A / PROC091G (2021-09-02)",
            "url": "https://www.ti.com/lit/zip/sprr418", "pcb_thickness": 1.6256,
            "outline": [xy(*p) for p in points[:-1]], "mounting_holes": holes,
            "components": bodies,
            "note": "Unpanelled full board; fabrication rails excluded. Component bodies are bounding envelopes, not a populated vendor STEP."}
    out = ROOT / "vendor/board_geometry.json"
    out.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({"origin_odb_mm": [cx, cy], "mounting_holes": holes,
                      "components": bodies}, indent=2))


if __name__ == "__main__":
    main()
