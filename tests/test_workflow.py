import time
import json
import numpy as np
import pytest
from fastapi.testclient import TestClient
from subvocal.server import create_app
from subvocal.cli import seed_demo
from subvocal.storage import Store
from subvocal.training import train, predict
from subvocal.profile import bundled_profile


def test_capture_review_media_and_source_errors(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        assert c.get('/').status_code==200
        assert c.get('/api/health').json()['hardware_verified'] is False
        assert c.post('/api/connect',json={'source':'serial'}).status_code==400
        assert c.post('/api/connect',json={'source':'simulator'}).status_code==200
        session=c.post('/api/sessions',json={'name':'Visit A','subject':'Test'}).json()
        time.sleep(.15)
        state=c.get('/api/live').json()
        assert state['complex_available'] and state['synthetic'] and state['antenna_count']==12
        rec=c.post('/api/record',json={'label':'add a note','duration_s':.6}).json()
        assert c.post('/api/disconnect').status_code==400
        assert c.post('/api/record',json={'label':'other','duration_s':.6}).status_code==400
        for _ in range(30):
            result=c.get('/api/record/'+rec['id']).json()
            if result['status']!='recording':break
            time.sleep(.05)
        assert result['status']=='complete',result
        trial=result['trial'];tid=trial['id'];sid=session['id']
        assert trial['synthetic'] and trial['frames']>=8
        assert len(c.get(f'/api/sessions/{sid}/trials').json())==1
        assert c.get(f'/api/sessions/{sid}/trials/{tid}/signal').status_code==200
        assert c.get(f'/api/sessions/{sid}/trials/{tid}/download').content.startswith(b'PK')
        assert c.patch(f'/api/sessions/{sid}/trials/{tid}',json={'accepted':False,'label':'corrected'}).status_code==200
        assert not c.get(f'/api/sessions/{sid}/trials').json()[0]['accepted']
        assert c.put(f'/api/sessions/{sid}/trials/{tid}/media',content=b'test-reference',headers={'Content-Type':'video/webm'}).status_code==200
        assert c.get(f'/api/sessions/{sid}/trials/{tid}/media').content==b'test-reference'
        assert c.put(f'/api/sessions/{sid}/trials/{tid}/media',content=b'x',headers={'Content-Type':'video/webm'}).status_code==400
        assert c.post('/api/disconnect').status_code==200
        assert c.get('/api/live').json()['status']=='disconnected'


def test_training_provenance_group_split_checksum_and_prediction(tmp_path):
    store=Store(tmp_path);ids=seed_demo(store)
    report=train(store,ids,[ids[-1]])
    assert report['synthetic'] and report['train_examples']==24 and report['test_examples']==12
    assert {r['session'] for r in report['dataset'] if r['split']=='train'}.isdisjoint(report['test_session_ids'])
    assert report['accuracy']>.5  # Deliberately learnable fixture, not a speech claim.
    trial=store.trials(ids[0])[0];arr=store.load_signal(ids[0],trial['id'])
    result=predict(store,report['id'],arr['iq'],arr['timestamps_ns'],store.session(ids[0]),0)
    assert result['synthetic'] and result['label'] in report['labels']
    changed=store.session(ids[0]);changed['synthetic']=False
    with pytest.raises(ValueError,match='does not match'):predict(store,report['id'],arr['iq'],arr['timestamps_ns'],changed)
    with pytest.raises(ValueError,match='hold out'):train(store,ids,ids)
    path=store.trial_dir(ids[0],trial['id'])/'radar.npz';path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError,match='checksum'):train(store,ids,[ids[-1]])


def test_api_background_training_and_local_origin(tmp_path):
    app=create_app(tmp_path);ids=seed_demo(app.state.store)
    with TestClient(app) as c:
        assert c.get('/api/health',headers={'Host':'evil.example'}).status_code==403
        assert c.post('/api/connect',json={},headers={'Origin':'https://evil.example'}).status_code==403
        response=c.post('/api/train',json={'session_ids':ids,'test_session_ids':[ids[-1]]})
        assert response.status_code==200
        job_id=response.json()['id']
        for _ in range(200):
            job=c.get('/api/jobs/'+job_id).json()
            if job['status'] in ('complete','failed'):break
            time.sleep(.025)
        assert job['status']=='complete',job
        assert c.get('/api/models').json()[0]['id']==job['report']['id']
        assert c.post('/api/decode',json={'model_id':job['report']['id']}).status_code==403


def test_saved_prediction_provenance_quality_and_no_label_input(tmp_path):
    app=create_app(tmp_path, research_enabled=True);store=app.state.store;ids=seed_demo(store,sessions=2,repetitions=2)
    report=train(store,ids,[ids[-1]])
    with TestClient(app) as client:
        for sid,use in ((ids[0],'training'),(ids[-1],'held_out')):
            trial=store.trials(sid)[0]
            response=client.post('/api/predict-trial',json={'model_id':report['id'],
                'session_id':sid,'trial_id':trial['id'],'threshold':0})
            assert response.status_code==200,response.json()
            result=response.json();assert result['evaluation_use']==use and result['synthetic']
        sid=ids[0];trial=store.trials(sid)[0];arr=store.load_signal(sid,trial['id'])
        session=store.create_session('New fixture visit','synthetic-fixture','simulator',bundled_profile())
        new=store.save_trial(session['id'],trial['label'],arr['timestamps_ns'],arr['iq']+1,arr['frame_numbers'])
        body={'model_id':report['id'],'session_id':session['id'],'trial_id':new['id'],'threshold':0}
        result=client.post('/api/predict-trial',json=body).json()
        assert result['evaluation_use']=='new' and not result['session_seen']
        store.update_trial(session['id'],new['id'],{'label':'different prompt text'})
        corrected=client.post('/api/predict-trial',json=body).json()
        assert corrected['candidate']==result['candidate'] and corrected['score']==result['score']
        assert corrected['expected_label']=='different prompt text'
        assert client.get('/api/models',params={'session_id':sid}).json()[0]['id']==report['id']
        other=store.create_session('DCA fixture','synthetic-fixture','dca1000',bundled_profile('dca-raw'))
        assert client.get('/api/models',params={'session_id':other['id']}).json()==[]
        store.update_trial(session['id'],new['id'],{'accepted':False})
        assert client.post('/api/predict-trial',json=body).status_code==400
        store.update_trial(session['id'],new['id'],{'accepted':True})
        path=store.trial_dir(session['id'],new['id'])/'radar.npz'
        path.write_bytes(path.read_bytes()+b'tampered')
        assert 'checksum' in client.post('/api/predict-trial',json=body).json()['detail']
