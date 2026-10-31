#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")/.."
export UV_CACHE_DIR="$PWD/.cache/uv"
if command -v uv >/dev/null; then
  uv sync --extra dev --python 3.12
else
  python3 -m venv .venv
  .venv/bin/python -m pip install -e '.[dev]'
fi
echo 'Ready. Run ./scripts/run.sh or double-click Start Gasp.command.'
