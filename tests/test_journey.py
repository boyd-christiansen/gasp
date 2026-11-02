"""Production journey gates, immutable recipes and capture provenance."""
import json
import numpy as np
from fastapi.testclient import TestClient
from gasp.server import create_app
from gasp.journey import BASELINE, SENTENCES, baseline_plan, custom_plan


def start(c, key, setup=None, reseated=False):
    return c.post(f'/api/collections/{key}/sessions', json={'setup':setup or {'subject':'Boyd'},'reseated':reseated})


def reviewed_session(app, c, key):
    result=start(c,key,reseated=True)
    assert result.status_code == 200, result.text
    session=result.json();store=app.state.store
    for step in session['collection']['plan']['steps']:
        _,extra=store.collection_record(session['id'],step['step_id'])
        t=store.save_trial(session['id'],step['target_text'],np.arange(11)*1_000_000_000,
                           np.ones((11,16,12),dtype=np.complex64),np.arange(11),extra={**extra,'articulation':step['articulation']})
        patch=c.patch(f"/api/sessions/{session['id']}/trials/{t['id']}",json={'confirmed_text':step['target_text'],'accepted':True,'base_revision':0})
        assert patch.status_code == 200, patch.text
    return session


def progress(c, subject='Boyd', source='simulator', profile=None):
    sha=profile or c.get('/api/live').json()['profile']['sha256']
    return c.get('/api/journey',params={'subject':subject,'source':source,'profile':sha}).json()['progress']


def test_protocol_counts_sentence_separation_and_stability():
    assert len(SENTENCES)==len(set(SENTENCES))==120
    texts=[]
    for b in BASELINE:
        first,second=baseline_plan(b['id']),baseline_plan(b['id'])
        assert first==second and len(first['steps'])==b['total']
        if b['id']!='calibration':
            sentences={s['target_text'] for s in first['steps'] if s['training_task']=='sentence'}
            assert not any(sentences&previous for previous in texts)
            texts.append(sentences)
            assert sum(s['training_task']=='control' for s in first['steps'])==12
    assert [len(s) for s in texts]==[60,30,30]


def test_progress_requires_review_and_isolates_person_profile_and_simulator(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        assert start(c,'calibration').status_code==400
        c.post('/api/connect',json={'source':'simulator'})
        assert start(c,'first-speech').status_code==400
        scope=dict(subject='Boyd',source='simulator',profile=c.get('/api/live').json()['profile']['sha256'])
        assert c.post('/api/learning/assignments',json=scope).status_code==400
        assert c.post('/api/collections',json={'name':'Book','template':'reader','content':'A short chapter.'}).status_code==400
        session=reviewed_session(app,c,'calibration')
        p=progress(c);assert p['steps'][0]['complete'] and p['steps'][1]['unlocked'] and not p['complete']
        assert not progress(c,source='serial')['steps'][0]['complete']
        assert not progress(c,subject='Another person')['steps'][0]['complete']
        assert not progress(c,profile='different')['steps'][0]['complete']
        trial=app.state.store.trials(session['id'])[0]
        c.patch(f"/api/sessions/{session['id']}/trials/{trial['id']}",json={'accepted':False,'base_revision':1})
        assert not progress(c)['steps'][1]['unlocked']


def test_full_journey_reseat_immutable_definition_and_setup(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        c.post('/api/connect',json={'source':'simulator'})
        reviewed_session(app,c,'calibration'); reviewed_session(app,c,'first-speech')
        assert start(c,'return-repeat').status_code==400
        reviewed_session(app,c,'return-repeat');reviewed_session(app,c,'independent-check')
        assert progress(c)['complete']
        definition=c.post('/api/collections',json={'name':'The Odyssey','template':'reader','content':'A chapter of original fixture text.','source_text':'Test fixture'}).json()
        assert definition['id'] and definition['version']==1
        session=start(c,definition['id'],{'subject':'Boyd','location':'Desk','distance_cm':45}).json()
        assert session['collection']['definition']['id']==definition['id']
        c.put('/api/preferences',json={'setup':{'subject':'Boyd','location':'Kitchen','distance_cm':60}})
        saved=c.get('/api/sessions/'+session['id']).json()
        assert saved['collection']['location']=='Desk' and saved['collection']['distance_cm']==45
        assert c.put('/api/collections/'+definition['id'],json={'name':'Changed'}).status_code==405
        assert c.get('/api/collections/'+definition['id']).json()['name']=='The Odyssey'
        scope=dict(subject='Boyd',source='simulator',profile=c.get('/api/live').json()['profile']['sha256'])
        first=c.post('/api/learning/assignments',json=scope)
        second=c.post('/api/learning/assignments',json=scope)
        assert first.status_code==second.status_code==200
        assert len(first.json()['content'].splitlines())==20
        assert not set(first.json()['content'].splitlines()) & set(second.json()['content'].splitlines())
        evaluation=c.post('/api/learning/assignments',json={**scope,'purpose':'validation','content':'An entirely new sentence for evaluation.'})
        assert evaluation.status_code==200,evaluation.text
        assert start(c,evaluation.json()['id']).status_code==400
        session=start(c,evaluation.json()['id'],reseated=True)
        assert session.status_code==200,session.text
        assert session.json()['collection']['visit_role']=='validation'
        assert progress(c)['complete']


def test_pose_distance_and_raw_passage_boundaries():
    plan=custom_plan({'template':'pose','content':'Say something.','distances':[35,55]})
    assert [s['distance_cm'] for s in plan['steps']]==[35,35,55,55]
    assert plan['steps'][0]['pair_id']!=plan['steps'][2]['pair_id']
    raw=custom_plan({'template':'reader','content':'word '*150},raw=True)
    assert len(raw['steps'])==10
    assert all(s['duration_s']<=25 and len(s['prompt_text'].split())<=35 for s in raw['steps'])
