"""Check the built relief against the preserved solid water-impact profile."""
import ast
import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import build123d as bd
from cadgen.geometry import overlap_volume
import capture_enclosure as c


def profile_functions(path):
    return {
        node.name: ast.dump(node, include_attributes=False)
        for node in ast.parse(path.read_text()).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main():
    original = profile_functions(ROOT / 'references/ripple_panel_original.py')
    used = profile_functions(ROOT / 'src/water_profile.py')
    for name, function in used.items():
        assert function == original[name], ('profile function changed', name)

    cover = c.ripple_cover_print().shape
    front = c.front_bezel().shape
    cx, cy = c.chip_xy()
    report = {
        'source': 'references/ripple_panel_original.py — solid ripple panel',
        'original_source_sha256': hashlib.sha256((ROOT / 'references/ripple_panel_original.py').read_bytes()).hexdigest(),
        'unaltered_profile_functions': list(used),
        'centre_cassette_xy_mm': [cx, cy],
        'xy_scale': c.RIPPLE_XY_SCALE,
        'z_scale': c.RIPPLE_Z_SCALE,
        'native_surface_samples': [],
        'vent_overlap_mm3': [],
        'limits': ['Surface samples verify the fitted CAD, not a physical print.',
                   'The central jet is removed by the antenna opening; the perimeter and fastener lands are blended.'],
    }
    probes = [(radius, 180) for radius in [40, 45, 60, 65, 70, 75, 90, 95, 100, 110, 115, 130]]
    probes += [(65, angle) for angle in [90, 120, 240]]
    for radius, angle in probes:
        x = cx + radius * math.cos(math.radians(angle))
        y = cy + radius * math.sin(math.radians(angle))
        ray = bd.Edge.make_line((x, y, -1), (x, y, 20))
        hits = ray.intersect(cover) or []
        heights = [v.center().Z for hit in hits for v in hit.vertices()]
        assert heights, ('no surface at probe', radius, angle)
        actual = max(heights)
        intended = c.ripple_height(x, y)
        assert abs(min(heights)) < 1e-5, ('back is not flat', radius, angle)
        assert abs(actual - intended) < .05, ('profile mismatch', radius, angle, actual, intended)
        report['native_surface_samples'].append({'radius_mm': radius, 'angle_deg': angle,
                                                'actual_height_mm': actual, 'target_height_mm': intended})
    ring = [p['actual_height_mm'] for p in report['native_surface_samples'] if p['radius_mm'] == 65]
    report['65mm_ring_height_range_mm'] = max(ring) - min(ring)
    assert report['65mm_ring_height_range_mm'] < .03, 'ripple is not concentric about chip'

    # Gauge all seven entire arc paths, independently against both built layers.
    for part, z in [(front, c.SEAM - .1), (cover, -.1)]:
        for index, tool in enumerate(c.ripple_vent_tools(z, 21)):
            volume = sum(overlap_volume(a, b) for a in part.solids() for b in tool.solids())
            assert volume < 1e-5, ('blocked vent', part.label, index, volume)
            report['vent_overlap_mm3'].append({'part': part.label, 'slot': index + 1, 'overlap': volume})

    # Optional regression check when the prior deliverable is present locally.
    archive = ROOT / 'capture_stack_enclosure_v1_1.zip'
    if archive.exists():
        unchanged = ['rear_shell', 'table_base', 'cable_guide', 'dca_washer_1p8',
                     'carrier_washer_0p8', 'radar_washer_0p6', 'fit_coupon']
        with zipfile.ZipFile(archive) as prior:
            for name in unchanged:
                suffix = f'exports/{name}.stl'
                matches = [p for p in prior.namelist() if p.endswith(suffix)]
                assert len(matches) == 1
                assert prior.read(matches[0]) == (ROOT / suffix).read_bytes(), ('changed print', name)
        report['unchanged_STLs_vs_v1_1'] = unchanged
    report['status'] = 'PASS'
    (ROOT / 'checks/ripple_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
