"""Isolated, explicitly synthetic Training UI preview. Never use the live data root."""
from pathlib import Path
import argparse
import uvicorn
from gasp.cli import seed_demo
from gasp.server import create_app
from gasp.storage import atomic_json

parser=argparse.ArgumentParser()
parser.add_argument('--data',default='test-data/learning-preview')
parser.add_argument('--port',type=int,default=8891)
args=parser.parse_args()
root=Path(args.data).resolve()
if not root.is_relative_to(Path('test-data').resolve()):
    parser.error('Preview data must be inside test-data/')
app=create_app(root);store=app.state.store
if not store.sessions():
    ids=seed_demo(store,sessions=3,repetitions=4)
    for sid,role in zip(ids,['train','validation','test']):
        session=store.session(sid)
        session['collection']=dict(visit_role=role,acquisition_id=sid,plan=dict(task='phrases',calibration=False,steps=[]))
        atomic_json(store.session_dir(sid)/'session.json',session)
        for t in store.trials(sid):
            store.update_trial(sid,t['id'],dict(confirmed_text=t['label'],accepted=True))
    atomic_json(root/'preferences.json',dict(setup=dict(subject='synthetic-fixture',location='UI verification',distance_cm=45),
        connection=dict(source='simulator',profile='usb-phase-20hz'),reference_audio=False))
uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False)
