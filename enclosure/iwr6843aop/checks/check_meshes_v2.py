"""Validate exported STL topology and print placement, including multi-part plates."""
from pathlib import Path
from collections import defaultdict
import json
import struct

ROOT = Path(__file__).resolve().parents[1]


def inspect(path, expected=1):
    raw = path.read_bytes()
    count, = struct.unpack_from('<I', raw, 80)
    assert len(raw) == 84 + count * 50
    edges = defaultdict(list)
    points = []
    volumes = []
    for i in range(count):
        coords = struct.unpack_from('<12fH', raw, 84 + i * 50)[3:12]
        vertices = [tuple(round(v, 5) for v in coords[j:j+3]) for j in (0, 3, 6)]
        assert len(set(vertices)) == 3, (path.name, 'degenerate triangle', i)
        points.extend(vertices)
        a, b, c = vertices
        volumes.append((a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2])
                        + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6)
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            edges[tuple(sorted((a, b)))].append((i, 1 if a < b else -1))
    assert all(len(f) == 2 for f in edges.values()), (path.name, 'open/nonmanifold edge')
    assert all(sum(t[1] for t in f) == 0 for f in edges.values()), (path.name, 'winding')
    neighbors = defaultdict(set)
    for faces in edges.values():
        a, b = faces[0][0], faces[1][0]
        neighbors[a].add(b)
        neighbors[b].add(a)
    remaining, component_volumes, component_min_z = set(range(count)), [], []
    while remaining:
        seen, pending = set(), [next(iter(remaining))]
        while pending:
            i = pending.pop()
            if i in seen:
                continue
            seen.add(i)
            pending.extend(neighbors[i] - seen)
        remaining -= seen
        volume = sum(volumes[i] for i in seen)
        assert volume > 0
        component_volumes.append(volume)
        component_min_z.append(min(points[i * 3 + j][2] for i in seen for j in range(3)))
    assert len(component_volumes) == expected, (path.name, len(component_volumes), expected)
    assert all(abs(z) < .001 for z in component_min_z), (path.name, 'off bed', component_min_z)
    return {'triangles': count, 'watertight': True, 'consistent_winding': True,
            'connected_parts': expected, 'component_volume_mm3': component_volumes,
            'each_part_on_bed': True,
            'bounds_mm': [max(p[k] for p in points) - min(p[k] for p in points) for k in range(3)]}


if __name__ == '__main__':
    counts = {'two_locking_keys.stl': 2, 'three_socket_trials.stl': 3, 'PRINT_FIRST_fit_coupons.stl': 10}
    report = {p.name: inspect(p, counts.get(p.name, 1)) for p in sorted((ROOT / 'exports_v2').glob('*.stl'))}
    (ROOT / 'checks/mesh_v2_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'files': len(report), 'parts': sum(x['connected_parts'] for x in report.values())}))
