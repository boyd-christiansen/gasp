"""Exercise the frozen capture worker without the source checkout or a venv.

Usage: python tests/smoke_bundle.py dist/Subvocal.app
All artifacts live in a temporary directory and use the labelled simulator.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen
import uuid


def main():
    app = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix='subvocal-bundle-smoke-') as folder:
        root = Path(folder)
        token = uuid.uuid4().hex + uuid.uuid4().hex
        env = dict(os.environ, SUBVOCAL_APP_TOKEN=token, PYTHONNOUSERSITE='1')
        with (root/'worker.log').open('w+') as log:
            process = subprocess.Popen([str(app/'Contents/Resources/capture/subvocal-capture'),
                '--data', str(root/'data'), '--ready-file', str(root/'ready.json')],
                cwd=root, env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic()+30
                while not (root/'ready.json').exists():
                    if process.poll() is not None or time.monotonic()>deadline:
                        log.seek(0); raise AssertionError(log.read() or 'Worker did not start')
                    time.sleep(.1)
                port = json.loads((root/'ready.json').read_text())['port']
                def api(path, method='GET', body=None):
                    data = json.dumps(body).encode() if body is not None else None
                    req = Request(f'http://127.0.0.1:{port}/api/{path}', data=data, method=method,
                                  headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                    with urlopen(req,timeout=10) as response:
                        return json.load(response)
                # The socket is bound just before uvicorn begins accepting requests.
                health = api('health')
                assert not health['transcription_enabled'] and not health['research_predictions_enabled']
                assert health['data_root'] == str((root/'data').resolve())
                api('connect','POST',{'source':'simulator'})
                time.sleep(.2)
                visits = []
                for visit in range(2):
                    session = api('sessions','POST',{'name':'APP BUNDLE SMOKE FIXTURE', 'subject':'synthetic-fixture',
                        'collection':{'deck_id':'commands-v1','mode':'silent','visit_role':'train' if visit == 0 else 'test','repetitions':2}})
                    visits.append(session['id'])
                    steps = session['collection']['plan']['steps']
                    chosen = {s['prompt_id'] for s in steps if s['articulation']=='silent'}
                    chosen = set(sorted(chosen)[:2])
                    for step in [s for s in steps if s['prompt_id'] in chosen]:
                        rec = api('collect','POST',{'step_id':step['step_id'],'duration_s':.6})
                        capture_deadline = time.monotonic()+15
                        while True:
                            assert time.monotonic()<capture_deadline,'Recording timed out'
                            result = api('record/'+rec['id'])
                            if result['status'] in {'complete','failed','cancelled'}: break
                            time.sleep(.05)
                        assert result['status']=='complete',result
                        trial = result['trial']; assert trial['synthetic'] and not trial['accepted']
                        verified = api(f"sessions/{session['id']}/trials/{trial['id']}",'PATCH',{
                            'confirmed_text':step['target_text'],'accepted':True})
                        assert verified['review_status']=='verified'
                job = api('train','POST',{'session_ids':visits,'test_session_ids':[visits[-1]],'articulation':'silent'})
                deadline = time.monotonic()+20
                while True:
                    result = api('jobs/'+job['id'])
                    if result['status'] in {'complete','failed'}: break
                    assert time.monotonic()<deadline,'Training job timed out'
                    time.sleep(.05)
                assert result['status']=='complete',result
                report = result['report']
                assert report['synthetic'] and report['train_examples']==4 and report['test_examples']==4
                api('disconnect','POST')
                print('Standalone bundle: launch, scripts, capture, human review, reserved holdout and CPU training passed (synthetic only)')
            finally:
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
                assert not (root/'ready.json').exists(),'Worker did not clean up its ready file'


if __name__ == '__main__':
    main()
