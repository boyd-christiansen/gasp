"""Frozen capture worker. A fresh local app token protects each launch."""
import argparse
import json
import os
from pathlib import Path
import socket
import uvicorn
from subvocal.server import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--ready-file', required=True)
    args = parser.parse_args()
    token = os.environ.get('SUBVOCAL_APP_TOKEN')
    if not token or len(token) < 32:
        raise SystemExit('An app session token is required')
    app = create_app(args.data, app_token=token, research_enabled=False)
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    sock.listen(128)
    ready = Path(args.ready_file)
    tmp = ready.with_suffix('.tmp')
    tmp.write_text(json.dumps({'port': sock.getsockname()[1], 'pid': os.getpid()}))
    tmp.replace(ready)
    try:
        uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False)).run(sockets=[sock])
    finally:
        ready.unlink(missing_ok=True)
        sock.close()


if __name__ == '__main__':
    main()
