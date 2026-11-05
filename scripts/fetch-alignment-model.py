"""Fetch only pinned public model artifacts; never reads recording data."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import urllib.request

project = Path(__file__).resolve().parents[1]
manifest = json.loads((project/'gasp/alignment_model.json').read_text())
cache = project/'.cache/alignment-en'
cache.mkdir(parents=True, exist_ok=True)


def valid(path, spec):
    return (path.is_file() and path.stat().st_size == spec['bytes']
            and hashlib.sha256(path.read_bytes()).hexdigest() == spec['sha256'])


for name, spec in manifest['files'].items():
    target = cache/name
    if not valid(target, spec):
        url = f"https://huggingface.co/{manifest['repository']}/resolve/{manifest['revision']}/{spec['remote']}"
        temporary = target.with_suffix('.download')
        try:
            print(f'Downloading local alignment model: {name}', flush=True)
            with urllib.request.urlopen(url, timeout=120) as response, temporary.open('wb') as output:
                shutil.copyfileobj(response, output)
            if not valid(temporary, spec):
                raise SystemExit(f'Checksum failed for {name}; refusing to package the model')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    if len(sys.argv) > 1:
        destination = Path(sys.argv[1]); destination.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination/name)
print('Pinned English alignment model verified.')
