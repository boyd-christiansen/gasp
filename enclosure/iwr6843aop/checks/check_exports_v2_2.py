"""Verify delivered STL topology and 3MF meshes after applying all placements."""
from pathlib import Path
import json
import struct
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from check_meshes_v2 import inspect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'exports_v2_2'
NS = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}


def transformed(point, transform):
    t = [float(x) for x in transform.split()] if transform else [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
    return tuple(sum(point[j] * t[j * 3 + k] for j in range(3)) + t[9 + k] for k in range(3))


def inspect_3mf(path, expected):
    with zipfile.ZipFile(path) as archive:
        root = ET.fromstring(archive.read('3D/3dmodel.model'))
    assert root.attrib['unit'] == 'millimeter'
    objects = {o.attrib['id']: o for o in root.findall('m:resources/m:object', NS)}
    leaves = []

    def visit(obj_id, chain):
        obj = objects[obj_id]
        mesh = obj.find('m:mesh', NS)
        if mesh is None:
            for c in obj.findall('m:components/m:component', NS):
                visit(c.attrib['objectid'], [c.get('transform')] + chain)
            return
        vertices = []
        for vertex in mesh.findall('m:vertices/m:vertex', NS):
            p = tuple(float(vertex.attrib[c]) for c in 'xyz')
            for transform in chain:
                p = transformed(p, transform)
            vertices.append(p)
        faces = [tuple(int(t.attrib[k]) for k in ('v1', 'v2', 'v3'))
                 for t in mesh.findall('m:triangles/m:triangle', NS)]
        raw = bytearray(b'3MF mesh verification'.ljust(80, b'\0') + struct.pack('<I', len(faces)))
        for face in faces:
            points = [v for i in face for v in vertices[i]]
            raw.extend(struct.pack('<12fH', 0, 0, 0, *points, 0))
        with tempfile.TemporaryDirectory() as td:
            stl = Path(td) / 'mesh.stl'
            stl.write_bytes(raw)
            result = inspect(stl)
        result['name'] = obj.get('name')
        leaves.append(result)

    for item in root.findall('m:build/m:item', NS):
        visit(item.attrib['objectid'], [item.get('transform')])
    assert len(leaves) == expected, (path.name, len(leaves))
    return {'objects': len(leaves), 'millimeters': True, 'placed_meshes': leaves}


if __name__ == '__main__':
    counts = {'PRINT_FIRST_mount_and_keys.stl': 6, 'REPRINT_case_pair.stl': 2}
    report = {'status': 'PASS', 'stl': {}, '3mf': {}}
    for path in sorted(OUT.rglob('*.stl')):
        report['stl'][str(path.relative_to(OUT))] = inspect(path, counts.get(path.name, 1))
    for name, count in [('PRINT_FIRST_mount_and_keys', 6), ('REPRINT_case_pair', 2)]:
        report['3mf'][name] = inspect_3mf(OUT / (name + '.3mf'), count)
        stl_vol = sum(report['stl'][name + '.stl']['component_volume_mm3'])
        mf_vol = sum(sum(x['component_volume_mm3']) for x in report['3mf'][name]['placed_meshes'])
        assert abs(stl_vol - mf_vol) < stl_vol * .001
    (ROOT / 'checks/mesh_v2_2_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': report['status'], 'stl_files': len(report['stl']),
                      '3mf_plate_quantities': {k: v['objects'] for k, v in report['3mf'].items()}}))
