"""Check the delivered binary STL topology, winding, connectivity and volume."""
from pathlib import Path
from collections import defaultdict
import json
import struct

ROOT = Path(__file__).resolve().parents[1]


def inspect(path):
    raw = path.read_bytes()
    count, = struct.unpack_from('<I', raw, 80)
    assert len(raw) == 84 + count * 50
    edges = defaultdict(list)
    volume = 0.0
    points = []
    for i in range(count):
        coords = struct.unpack_from('<12fH', raw, 84 + i * 50)[3:12]
        vertices = [tuple(round(v, 5) for v in coords[j:j+3]) for j in (0, 3, 6)]
        assert len(set(vertices)) == 3, (path.name, 'degenerate triangle', i)
        points.extend(vertices)
        a, b, c = vertices
        volume += (a[0]*(b[1]*c[2]-b[2]*c[1]) + a[1]*(b[2]*c[0]-b[0]*c[2]) + a[2]*(b[0]*c[1]-b[1]*c[0])) / 6
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            edges[tuple(sorted((a, b)))].append((i, 1 if a < b else -1))
    bad = [e for e, faces in edges.items() if len(faces) != 2]
    wrong = [e for e, faces in edges.items() if sum(f[1] for f in faces) != 0]
    assert not bad and not wrong, (path.name, len(bad), len(wrong))
    neighbors = defaultdict(set)
    for faces in edges.values():
        a, b = faces[0][0], faces[1][0]
        neighbors[a].add(b)
        neighbors[b].add(a)
    seen, pending = set(), [0]
    while pending:
        i = pending.pop()
        if i in seen:
            continue
        seen.add(i)
        pending.extend(neighbors[i] - seen)
    assert len(seen) == count and volume > 0, (path.name, 'connectivity or winding')
    return {'triangles': count, 'watertight': True, 'consistent_winding': True,
            'connected_surface': True, 'volume_mm3': volume,
            'bounds_mm': [max(p[k] for p in points) - min(p[k] for p in points) for k in range(3)]}


if __name__ == '__main__':
    report = {p.name: inspect(p) for p in sorted((ROOT / 'exports_dock').glob('*.stl'))}
    assert set(report) == {'desktop_dock_20deg.stl', 'optional_cradle_fit_test.stl'}
    (ROOT / 'checks/dock_mesh_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
