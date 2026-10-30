#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
if [[ ! -x .venv/bin/python ]]; then
  ./scripts/bootstrap.sh
fi
./scripts/run.sh &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT INT TERM
.venv/bin/python - <<'PY'
import time, urllib.request, webbrowser
for attempt in range(120):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=1) as response:
            if response.status == 200:
                webbrowser.open('http://127.0.0.1:8765')
                break
    except OSError:
        time.sleep(0.5)
else:
    print('Server is still starting. Open http://127.0.0.1:8765 when it is ready.')
PY
wait "$server_pid"
