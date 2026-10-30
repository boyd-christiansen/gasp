"""Verify interchangeable mounting and an unobstructed geometric radar aperture."""
from pathlib import Path
import sys
import math
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import build123d as bd
from cadgen.geometry import closest_points, is_sound, boundary_edges
from enclosure import (assembly_open_aperture, front_radome, CLOSURE_XY,
                       LID_BOSS_BASE, FRONT_OUTER, cylinder, box)
from check_fit import world_parts, find_part, intersection


def main():
    kit = assembly_open_aperture().shape
    front = find_part(kit, 'front_open_aperture')
    closed = front_radome().shape
    rear = find_part(kit, 'rear_shell')
    antenna = find_part(kit, 'ref_U2')
    assert front.is_valid and is_sound(front) and len(front.solids()) == 1
    assert sum(len(boundary_edges(s)) for s in front.shells()) == 0
    # Every retained feature is identical to the original, apart from removed material.
    assert abs(intersection(front, closed) - front.volume) < 1e-4
    assert abs(closest_points(front, rear).distance) < 1e-5
    collisions = {}
    for other in world_parts(kit):
        if other.label == front.label:
            continue
        v = intersection(front, other)
        collisions[other.label] = v
        assert v < 1e-5, (other.label, v)
    for x, y in CLOSURE_XY:
        gauge = cylinder(x, y, 1.5, 1.25, 16)
        assert intersection(gauge, front) < 1e-6
        boss_region = cylinder(x, y, LID_BOSS_BASE, 3.71, FRONT_OUTER - LID_BOSS_BASE + 0.1)
        assert abs(intersection(boss_region, front) - intersection(boss_region, closed)) < 1e-4
    bounds = antenna.bounding_box()
    x, y, _ = bounds.center()
    z = bounds.max.Z
    height = FRONT_OUTER + 1 - z
    direct_path = box(x, y, z, bounds.size.X, bounds.size.Y, height)
    assert intersection(direct_path, front) < 1e-6
    # A square-pyramidal envelope expanding 50 degrees from all package edges.
    # This is geometric clearance, not an RF simulation or claimed field of view.
    growth = 2 * height * math.tan(math.radians(50))
    near = bd.Pos(x, y, z) * bd.Rectangle(bounds.size.X, bounds.size.Y)
    far = bd.Pos(x, y, z + height) * bd.Rectangle(bounds.size.X + growth, bounds.size.Y + growth)
    beam_envelope = bd.loft([near, far])
    assert intersection(beam_envelope, front) < 1e-5
    assert intersection(beam_envelope, rear) < 1e-5
    # Measure removed material's XY span, rather than copying design constants.
    removed = closed - front
    aperture_bounds = removed.bounding_box()
    assert abs(aperture_bounds.size.X - 42) < 1e-4
    assert abs(aperture_bounds.size.Y - 44) < 1e-4
    report = {'status': 'PASS', 'valid_closed_solid': True,
              'window_mm': [aperture_bounds.size.X, aperture_bounds.size.Y],
              'window_centre_xy_mm': [x, y],
              'material_in_direct_package_projection_mm3': intersection(direct_path, front),
              'clear_geometric_half_angle_deg': 50,
              'all_four_fastener_bosses_unchanged': True,
              'front_volume_mm3': front.volume,
              'interferences_mm3': collisions,
              'note': 'Geometric checks only; RF performance and physical printing remain untested.'}
    (Path(__file__).resolve().parent / 'open_aperture_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
