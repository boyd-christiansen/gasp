"""Manual browser QA only: python tests/preview_dca.py. Uses isolated test-data.

No hardware is contacted. Select the EMULATED CLI port and 127.0.0.1 for both
IPv4 addresses. Never interpret its hardware-shaped fixture as a speech result.
"""
from pathlib import Path
import uvicorn
from dca_emulator import DCAEmulator
from subvocal import dca, server

if __name__ == '__main__':
    peer = DCAEmulator().start()
    dca.DCAControl = peer.make_control
    server.ports = lambda: [{'device':peer.cli_port,'description':'EMULATED radar CLI · no physical hardware',
                            'interface':'EMULATED CLI', 'serial_number':None,'manufacturer':'TEST FIXTURE',
                            'vid':None,'pid':None}]
    try:
        app = server.create_app(Path('test-data/dca-browser'))
        uvicorn.run(app,host='127.0.0.1',port=8765,access_log=False)
    finally:
        peer.close()
