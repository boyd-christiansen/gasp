from pathlib import Path
from cadgen import export
from desktop_dock import desktop_dock, dock_fit_test, desktop_assembly, desktop_assembly_open

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    out = ROOT / 'exports_dock'
    out.mkdir(exist_ok=True)
    for name, part in [('desktop_dock_20deg', desktop_dock), ('optional_cradle_fit_test', dock_fit_test)]:
        export(part(), out / f'{name}.step', out / f'{name}.stl')
    for name, part in [('assembly_on_dock', desktop_assembly), ('assembly_open_on_dock', desktop_assembly_open)]:
        export(part(), out / f'{name}.step', out / f'{name}.glb')
