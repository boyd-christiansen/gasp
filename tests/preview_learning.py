"""Isolated, explicitly synthetic Training UI preview. Never use the live data root."""
from pathlib import Path
import argparse
import numpy as np
import uvicorn
from fastapi.responses import FileResponse, HTMLResponse
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
    from gasp.profile import bundled_profile
    session=store.create_session('Gap review fixture','synthetic-fixture','simulator',bundled_profile('usb-phase-20hz'))
    numbers=np.delete(np.arange(121),40)
    store.save_trial(session['id'],'Synthetic gap review',numbers*50_000_000,
        np.ones((120,64,12))*(100+20j),numbers,
        extra=dict(articulation='voiced',accepted=False,synthetic=True,prompt_text='Synthetic gap review'))
    from scipy.io import wavfile
    session=store.create_session('Timing review fixtures','synthetic-fixture','simulator',bundled_profile('usb-phase-20hz'))
    samples=np.arange(16000*7)/16000
    for label,centers,phonetic in [('Synthetic syllables',[1.2,1.6,2,3,3.4,3.8,4.8,5.2,5.6],True),
                                 ('Synthetic incomplete syllables',[1.2,1.6],True),
                                 ('Synthetic sentence',[1.2,1.6,2],False),
                                 ('Synthetic timeline sentence',[1.2,1.6,2],False)]:
        text='pa pa pa ta ta ta ka ka ka' if phonetic else 'Please open the window.'
        take=store.save_trial(session['id'],label,np.arange(141)*50_000_000,np.ones((141,64,12))*(100+20j),np.arange(141),
            extra=dict(articulation='voiced',accepted=False,synthetic=True,review_status='pending',
                       prompt_id='stops' if phonetic else 'sentence1',prompt_text=text,target_text=text))
        noise=.006*(.8+.6*np.sin(2*np.pi*3*samples)**2)*np.random.default_rng(42).normal(size=len(samples))
        speech=sum(.035*np.sin(2*np.pi*220*samples)*np.exp(-((samples-c)/.065)**2) for c in centers)
        wavfile.write(store.trial_dir(session['id'],take['id'])/'reference.wav',16000,(noise+speech).astype(np.float32))
        store.add_trial_fields(session['id'],take['id'],{'media':{'file':'reference.wav'}})
@app.get('/ui-check')
def ui_check():
    return FileResponse(Path(__file__).with_name('workspace_check.html'))

@app.get('/ui-regression.js')
def ui_regression():
    return FileResponse(Path(__file__).with_name('workspace_regression.js'),media_type='text/javascript')

@app.get('/native-preview')
def native_preview():
    # Test-only bridge: no microphone, permission prompt, or native API is used.
    html=Path('gasp/static/training.html').read_text()
    return HTMLResponse(html.replace('<script src="/static/training.js">',
        '<script src="/native-preview-bridge.js"></script><script src="/static/training.js">'))

@app.get('/native-preview-bridge.js')
def native_bridge():
    return FileResponse(Path(__file__).with_name('native_preview_bridge.js'),media_type='text/javascript')

@app.get('/failure-preview')
def failure_preview():
    html=Path('gasp/static/training.html').read_text()
    return HTMLResponse(html.replace('</body>', '<script src="/failure-regression.js"></script></body>'))

@app.get('/failure-regression.js')
def failure_regression():
    return FileResponse(Path(__file__).with_name('failure_regression.js'),media_type='text/javascript')

@app.get('/alignment-preview')
def alignment_preview():
    html=Path('gasp/static/training.html').read_text()
    return HTMLResponse(html.replace('</body>', '<script src="/alignment-regression.js"></script></body>'))

@app.get('/alignment-regression.js')
def alignment_regression():
    return FileResponse(Path(__file__).with_name('alignment_regression.js'),media_type='text/javascript')

uvicorn.run(app,host='127.0.0.1',port=args.port,access_log=False)
