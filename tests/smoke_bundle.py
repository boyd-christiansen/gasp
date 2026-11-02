"""Exercise the frozen capture worker without the source checkout or a venv.

Usage: python tests/smoke_bundle.py dist/Gasp.app
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
    with tempfile.TemporaryDirectory(prefix='gasp-bundle-smoke-') as folder:
        root = Path(folder)
        token = uuid.uuid4().hex + uuid.uuid4().hex
        env = dict(os.environ, GASP_APP_TOKEN=token, PYTHONNOUSERSITE='1')
        with (root/'worker.log').open('w+') as log:
            parent = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE)
            process = subprocess.Popen([str(app/'Contents/Resources/capture/gasp-capture'),
                '--data', str(root/'data'), '--ready-file', str(root/'ready.json'), '--parent-pid', str(parent.pid)],
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
                for asset in ['studio.js','timeline.js','journey.css','learning.js','learning.css','workspace-ui.js','workspace.css','capture-review.js','logo-particles.js','brand/face-open.png','brand/face-partial.png','brand/face-closed.png']:
                    req = Request(f'http://127.0.0.1:{port}/static/{asset}',
                                  headers={'Authorization':'Bearer '+token})
                    with urlopen(req,timeout=10) as response:
                        assert response.status == 200 and response.read(), asset
                assert (app/'Contents/Resources/Gasp.icns').stat().st_size > 0
                definition = {'name':'Offline saved plan','deck_id':'custom-words',
                              'script_text':'hello world\nnext note','mode':'voiced','repetitions':1}
                saved_plan = api('plans','POST',definition)
                assert saved_plan in api('plans')
                assert len(api('plans/preview','POST',definition)['steps']) == 2
                assert len(api('collections/calibration')['plan']['steps']) == 12
                assert len(api('collections/first-speech')['plan']['steps']) == 220
                assert not api('journey')['progress']['complete']
                assert api('preferences')['setup']['subject'] == 'Boyd'
                assert not api('blocks')
                api('connect','POST',{'source':'simulator'})
                time.sleep(.2)
                scene = api('scenes','POST',{'name':'Packaged app fixture','subject':'synthetic-fixture'})
                visits = []
                for visit in range(2):
                    session = api('sessions','POST',{'name':'APP BUNDLE SMOKE FIXTURE', 'subject':'synthetic-fixture',
                        'collection':{'scene_id':scene['id'],'deck_id':'commands-v1','mode':'silent','visit_role':'train' if visit == 0 else 'test','repetitions':2}})
                    assert session['collection']['scene_snapshot'] == scene
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
                scope=dict(subject='synthetic-fixture',source='simulator',profile=api('live')['profile']['sha256'])
                assert api('learning')['destinations'][1]['available'] is False
                inspected=api('learning/inspect','POST',scope)
                assert inspected['ready'] and inspected['counts']['test']['takes']==4
                learning=api('learning/runs','POST',scope)
                deadline=time.monotonic()+20
                while True:
                    learning=api('learning/runs/'+learning['id'])
                    if learning['status'] in {'complete','failed'}: break
                    assert time.monotonic()<deadline,'Learning run timed out'
                    time.sleep(.05)
                assert learning['status']=='complete',learning
                assert learning['result']['development']['metrics'] is None
                assert learning['source']['version']=='0.7.1' and len(learning['source']['source_sha256'])==64
                final=api('learning/runs/'+learning['id']+'/final-check','POST',{'confirm':True})
                deadline=time.monotonic()+20
                while True:
                    final=api('learning/runs/'+final['id'])
                    if final['status'] in {'complete','failed'}: break
                    assert time.monotonic()<deadline,'Final check timed out'
                    time.sleep(.05)
                assert final['status']=='complete',final
                assert final['result']['final_test']['metrics']['n']==4
                api(f'sessions/{visits[0]}/discard','POST')
                assert len(api('blocks')) == 1 and len(api('recordings')) == 4
                assert api('discarded-collections')[0]['id'] == visits[0]
                assert any(m['id'] == report['id'] for m in api('models'))
                api(f'sessions/{visits[0]}/restore','POST')
                assert len(api('blocks')) == 2 and len(api('recordings')) == 8
                assert not api('discarded-collections')
                api(f'sessions/{visits[0]}','DELETE',{'confirm':True})
                assert not (root/'data/sessions'/visits[0]).exists()
                assert len(api('blocks')) == 1 and len(api('recordings')) == 4
                assert any(m['id'] == report['id'] for m in api('models'))
                api('disconnect','POST')
                api('connect','POST',{'source':'simulator'})
                parent.terminate(); parent.wait(timeout=5)
                assert process.wait(timeout=10)==0, 'Worker must exit when its native parent disappears'
                print('Standalone bundle: launch, scripts, capture, human review, reserved holdout, CPU training, plan authoring and permanent deletion passed (synthetic only)')
                print('Native parent exit: capture worker stopped and released its source')
            finally:
                if parent.poll() is None:
                    parent.terminate(); parent.wait(timeout=5)
                if process.poll() is None:
                    process.send_signal(signal.SIGINT)
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait()
                assert not (root/'ready.json').exists(),'Worker did not clean up its ready file'


if __name__ == '__main__':
    main()
