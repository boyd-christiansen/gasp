"""Keep dependency license notices with the standalone application."""
import importlib.metadata as metadata
from pathlib import Path
import shutil
import sys
import sysconfig

root = Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=True)
for dist in metadata.distributions():
    for entry in dist.files or []:
        name = Path(entry).name.lower()
        if name.startswith(('license', 'copying', 'notice')):
            source = Path(dist.locate_file(entry))
            if source.is_file():
                parts = [p for p in Path(entry).parts if p not in {'.', '..'}]
                target = root / (dist.metadata['Name']+'-'+dist.version) / Path(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
python_license = Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt'
if not python_license.is_file():
    raise SystemExit('Python runtime license not found; do not distribute this bundle')
shutil.copy2(python_license, root / 'Python-LICENSE.txt')
shutil.copy2('LICENSE', root / 'Gasp-LICENSE.txt')
