"""Stamp source identity into the packaged worker, without bundling a Git checkout."""
import hashlib
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/"gasp").glob("*.py")}
value = dict(commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
             dirty=bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)),
             source_sha256=hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
import sys
sys.path.insert(0, str(root))
from gasp import __version__
value["version"] = __version__
(root/"gasp/build-info.json").write_text(json.dumps(value, indent=2)+"\n")
