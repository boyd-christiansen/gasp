"""Lossless collection discard and its acquisition/training boundaries."""
import hashlib
import threading
import time

import numpy as np
import pytest
from fastapi.testclient import TestClient
from gasp.server import create_app
from gasp import training


def start(client, name='Collection'):
    return client.post('/api/sessions', json={'name':name,'collection':{
        'deck_id':'commands-v1','mode':'voiced'}}).json()


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def test_discard_restore_preserves_files_and_hides_training_inputs(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        c.post('/api/connect',json={'source':'simulator'})
        a,b=start(c,'First'),start(c,'Second')
        store=app.state.store
        t=store.save_trial(a['id'],'hello',np.arange(8)*100_000_000,
            np.ones((8,16,12),dtype=np.complex64),np.arange(8))
        (store.trial_dir(a['id'],t['id'])/'reference.wav').write_bytes(b'keep reference media')
        before=hashes(tmp_path/'sessions')
        assert len(c.get('/api/recordings').json())==1
        assert c.post(f"/api/sessions/{a['id']}/discard").status_code==200
        assert c.post(f"/api/sessions/{a['id']}/discard").status_code==200
        assert [s['id'] for s in c.get('/api/blocks').json()]==[b['id']]
        assert c.get('/api/recordings').json()==[]
        discarded=c.get('/api/discarded-collections').json()
        assert discarded[0]['id']==a['id'] and discarded[0]['trial_count']==1
        assert 'steps' not in discarded[0]['collection']['plan']
        assert c.post(f"/api/sessions/{a['id']}/resume").status_code==400
        assert c.post('/api/train',json={'session_ids':[a['id'],b['id']],
            'test_session_ids':[b['id']]}).status_code==400
        with pytest.raises(ValueError,match='discarded'):
            training.train(store,[a['id'],b['id']],[b['id']])
        assert hashes(tmp_path/'sessions')==before
        assert c.post(f"/api/sessions/{a['id']}/restore").status_code==200
        assert c.post(f"/api/sessions/{a['id']}/restore").status_code==200
        assert c.get('/api/discarded-collections').json()==[]
        assert len(c.get('/api/recordings').json())==1
        assert c.post(f"/api/sessions/{a['id']}/resume").status_code==200
        assert hashes(tmp_path/'sessions')==before
        assert c.post('/api/sessions/missing/discard').status_code==404
        assert c.post('/api/sessions/bad!/restore').status_code==400


def test_discard_clears_active_collection_and_blocks_an_active_take(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        c.post('/api/connect',json={'source':'simulator'})
        a=start(c)
        engine=app.state.engine
        with engine.lock:
            engine.recording={'id':'active-test-take'}
        try:
            result=c.post(f"/api/sessions/{a['id']}/discard")
            assert result.status_code==400 and 'active recording' in result.json()['detail']
            assert len(c.get('/api/blocks').json())==1
        finally:
            with engine.lock:
                engine.recording=None
        engine.last_trial={'session_id':a['id'],'trial_id':'old'}
        assert c.post(f"/api/sessions/{a['id']}/discard").status_code==200
        assert engine.session is None and engine.last_trial is None
        assert c.post('/api/collect',json={'step_id':a['collection']['plan']['steps'][0]['step_id']}).status_code==400


def test_discard_waits_for_queued_and_running_training(tmp_path,monkeypatch):
    release=threading.Event()
    entered=threading.Event()
    def train(*args,**kwargs):
        entered.set()
        assert release.wait(5)
        return {'test':'fixture'}
    monkeypatch.setattr(training,'train',train)
    with TestClient(create_app(tmp_path)) as c:
        c.post('/api/connect',json={'source':'simulator'})
        a,b,d,e=[start(c,str(i)) for i in range(4)]
        j1=c.post('/api/train',json={'session_ids':[a['id'],b['id']],
            'test_session_ids':[b['id']]}).json()
        assert entered.wait(2)
        j2=c.post('/api/train',json={'session_ids':[d['id'],e['id']],
            'test_session_ids':[e['id']]}).json()
        try:
            for s in [a,d]:
                result=c.post(f"/api/sessions/{s['id']}/discard")
                assert result.status_code==400 and 'training' in result.json()['detail']
        finally:
            release.set()
        for job in [j1,j2]:
            for _ in range(100):
                if c.get('/api/jobs/'+job['id']).json()['status']=='complete':break
                time.sleep(.01)
            else:pytest.fail('Training job did not complete')
        assert c.post(f"/api/sessions/{a['id']}/discard").status_code==200
        assert c.post(f"/api/sessions/{d['id']}/discard").status_code==200
