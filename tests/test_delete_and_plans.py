"""Permanent collection deletion and reusable capture plans."""
import threading
import time
import numpy as np
from fastapi.testclient import TestClient
from gasp.server import create_app
from gasp.storage import atomic_json
from gasp import training


def session(c, name='Fixture'):
    response=c.post('/api/sessions',json={'name':name,'collection':{'deck_id':'commands-v1','mode':'voiced'}})
    assert response.status_code==200
    return response.json()


def delete(c,sid,confirm=True):
    return c.request('DELETE',f'/api/sessions/{sid}',json={'confirm':confirm})


def test_delete_removes_raw_audio_annotations_and_marker_only_for_target(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        c.post('/api/connect',json={'source':'simulator'})
        a,b=session(c),session(c)
        store=app.state.store
        t=store.save_trial(a['id'],'hello',np.arange(8)*100_000_000,
            np.ones((8,16,12),dtype=np.complex64),np.arange(8))
        (store.trial_dir(a['id'],t['id'])/'reference.wav').write_bytes(b'audio')
        atomic_json(store.trial_dir(a['id'],t['id'])/'annotations/1.json',{'text':'hello'})
        raw=tmp_path/'raw'/a['id']/'capture'
        raw.mkdir(parents=True);(raw/'adc.bin').write_bytes(b'raw')
        unrelated=tmp_path/'raw'/b['id'];unrelated.mkdir(parents=True);(unrelated/'adc.bin').write_bytes(b'keep')
        model=tmp_path/'models/existing.json';atomic_json(model,{'training_session':a['id']})
        assert delete(c,a['id'],False).status_code==400
        assert c.get(f"/api/sessions/{a['id']}/trials/{t['id']}/replay").status_code==200
        c.post(f"/api/sessions/{a['id']}/discard")
        assert delete(c,a['id']).status_code==200
        assert not store.session_dir(a['id']).exists()
        assert not (tmp_path/'raw'/a['id']).exists()
        assert not store.discard_marker(a['id']).exists()
        assert (unrelated/'adc.bin').read_bytes()==b'keep'
        assert store.session_dir(b['id']).exists() and model.exists()
        assert c.get('/api/recordings').json()==[] and c.get('/api/discarded-collections').json()==[]
        assert c.get(f"/api/sessions/{a['id']}/trials/{t['id']}/replay").status_code==404
        assert delete(c,a['id']).status_code==404
        assert delete(c,'bad!').status_code==400


def test_delete_guards_capture_training_and_redirected_paths(tmp_path,monkeypatch):
    release=threading.Event();entered=threading.Event()
    def train(*args,**kwargs):
        entered.set();assert release.wait(5);return {'fixture':True}
    monkeypatch.setattr(training,'train',train)
    app=create_app(tmp_path)
    with TestClient(app) as c:
        c.post('/api/connect',json={'source':'simulator'})
        a,b=session(c),session(c)
        engine=app.state.engine
        with engine.lock:engine.recording={'id':'test'}
        assert delete(c,b['id']).status_code==400
        with engine.lock:engine.recording=None
        job=c.post('/api/train',json={'session_ids':[a['id'],b['id']],'test_session_ids':[b['id']]}).json()
        assert entered.wait(2)
        try:assert delete(c,a['id']).status_code==400
        finally:release.set()
        for _ in range(100):
            if c.get('/api/jobs/'+job['id']).json()['status']=='complete':break
            time.sleep(.01)
        raw=tmp_path/'raw';raw.mkdir();(raw/a['id']).symlink_to(app.state.store.session_dir(b['id']),target_is_directory=True)
        assert delete(c,a['id']).status_code==400
        assert app.state.store.session_dir(a['id']).exists()
        (raw/a['id']).unlink()
        engine.last_trial={'session_id':b['id']}
        assert delete(c,b['id']).status_code==200
        assert engine.session is None and engine.last_trial is None


def test_plan_authoring_offline_persists_and_previews_same_capture_rules(tmp_path):
    definition={'name':'Desk phrases','deck_id':'custom-words','mode':'paired',
                'repetitions':2,'script_text':'hello world\nnext note','visit_role':'test'}
    with TestClient(create_app(tmp_path)) as c:
        preview=c.post('/api/plans/preview',json=definition).json()
        assert len(preview['steps'])==8
        assert c.get('/api/blocks').json()==[] and c.get('/api/scenes').json()==[]
        saved=c.post('/api/plans',json=definition).json()
        assert saved['script_text']==definition['script_text']
        assert c.post('/api/plans',json=dict(definition,name=' ')).status_code==400
        assert c.post('/api/plans',json=dict(definition,script_text='')).status_code==400
        assert c.post('/api/plans',json=dict(definition,repetitions=20)).status_code==422
        reader=dict(definition,deck_id='reader',mode='voiced',repetitions=1,script_text='word '*200,words_per_minute=130)
        regular=c.post('/api/plans/preview',json=reader).json()
        raw=c.post('/api/plans/preview?raw=true',json=reader).json()
        assert len(raw['steps'])>len(regular['steps'])
        assert all(s['duration_s']==25 for s in raw['steps'])
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/api/plans').json()==[saved]
        c.post('/api/connect',json={'source':'simulator'})
        created=c.post('/api/sessions',json={'name':saved['name'],'collection':saved}).json()
        plan=created['collection']['plan']
        assert len(plan['steps'])==len(preview['steps'])
        assert sorted(s['target_text'] for s in plan['steps'])==sorted(s['target_text'] for s in preview['steps'])
