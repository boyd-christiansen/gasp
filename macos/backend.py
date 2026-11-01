"""Frozen capture worker. A fresh local app token protects each launch."""
import argparse
import json
import os
from pathlib import Path
import socket
import threading
import uvicorn
from gasp.server import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True)
    parser.add_argument('--ready-file', required=True)
    parser.add_argument('--parent-pid', type=int)
    args = parser.parse_args()
    token = os.environ.get('GASP_APP_TOKEN')
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
    server = uvicorn.Server(uvicorn.Config(app, log_level='warning', access_log=False))
    stopped = threading.Event()

    def watch_parent():
        # The native shell can crash before its normal shutdown handler runs.
        # Exit through the server lifespan so serial ports and readers are closed.
        while not stopped.wait(1):
            try:
                os.kill(args.parent_pid, 0)
            except ProcessLookupError:
                server.should_exit = True
                return
            except PermissionError:
                pass

    if args.parent_pid is not None:
        if args.parent_pid <= 1:
            raise SystemExit('Invalid parent process')
        threading.Thread(target=watch_parent, daemon=True, name='native-parent-watch').start()
    try:
        server.run(sockets=[sock])
    finally:
        stopped.set()
        ready.unlink(missing_ok=True)
        sock.close()


if __name__ == '__main__':
    main()
