#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  ./scripts/bootstrap.sh
fi
exec .venv/bin/python -m gasp --data data serve --port 8765
