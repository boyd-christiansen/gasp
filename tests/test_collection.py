import time
import numpy as np
import pytest
from fastapi.testclient import TestClient
from gasp.collection import make_plan
from gasp.server import create_app
from gasp.cli import seed_demo
from gasp.storage import Store
from gasp.training import train


def wait_for(client, rid):
    for _ in range(150):
        r = client.get('/api/record/'+rid).json()
        if r['status'] in {'complete', 'failed', 'cancelled'}:
            return r
        time.sleep(.03)
    raise AssertionError('Capture never finished')


def test_plan_pairing_and_reproducible_order():
    a = make_plan('commands-v1', 'paired', 2, 'fixed')
    b = make_plan('commands-v1', 'paired', 2, 'fixed')
    assert [s['prompt_id'] for s in a['steps']] == [s['prompt_id'] for s in b['steps']]
    spoken = [s for s in a['steps'] if s['pair_id']]
    for i in range(0, len(spoken), 2):
        x, y = spoken[i:i+2]
        assert x['pair_id'] == y['pair_id']
        assert (x['articulation'], y['articulation']) == ('voiced', 'silent')
        assert x['step_id'] != y['step_id'] and x['prompt_text'] == y['prompt_text']
    assert {s['articulation'] for s in make_plan('calibration-v1')['steps']} == {'rest','negative','silent'}


def test_collection_finish_review_resume_cancel_and_audio(tmp_path):
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/training').status_code == 200
        assert not c.get('/api/health').json()['transcription_enabled']
        assert c.post('/api/decode',json={'model_id':'none'}).status_code == 403
        assert c.post('/api/predict-trial',json={'model_id':'none','session_id':'none','trial_id':'none'}).status_code == 403
        c.post('/api/connect',json={'source':'simulator'})
        sid = c.post('/api/sessions',json={'name':'Personal training', 'collection':{
            'deck_id':'commands-v1','mode':'paired','visit_role':'train','repetitions':2}}).json()['id']
        session = c.get('/api/sessions/'+sid).json()
        assert session['schema'] == 2 and session['collection']['plan']['mode'] == 'paired'
        step = session['collection']['plan']['steps'][0]
        time.sleep(.2)
        r = c.post('/api/collect',json={'step_id':step['step_id'],'duration_s':5,'reference_expected':True}).json()
        rid = r['id']
        c.post('/api/record/'+rid+'/events',json={'name':'cue_shown','estimated_server_ns':time.monotonic_ns(),'uncertainty_ms':2})
        time.sleep(.6)
        assert c.post('/api/record/'+rid+'/stop').status_code == 200
        result = wait_for(c,rid)
        assert result['status'] == 'complete', result
        t = result['trial']; tid = t['id']; path = f'/api/sessions/{sid}/trials/{tid}'
        assert t['schema'] == 2 and not t['accepted'] and t['review_status'] == 'pending'
        assert t['prompt_text'] == step['prompt_text'] and t['confirmed_text'] is None
        assert t['asr_raw_text'] is None and t['duration_s'] < 2
        assert t['capture_events'][0]['name'] == 'cue_shown'
        assert c.patch(path,json={'accepted':True}).status_code == 400
        assert c.patch(path,json={'label':'overwrite prompt'}).status_code == 400
        assert c.patch(path,json={'accepted':True,'confirmed_text':'actually said this','utterance_end_s':100}).status_code == 400
        kept = c.patch(path,json={'accepted':True,'confirmed_text':'actually said this'}).json()
        assert kept['label'] == 'actually said this' and kept['prompt_text'] == step['prompt_text']
        assert kept['review_status'] == 'verified' and kept['transcript_source'] == 'human_confirmed'
        wav = b'RIFF'+bytes(40)
        response = c.put(path+'/media',content=wav,headers={'Content-Type':'audio/wav','X-Audio-Timing':'{"first_sample_host_ns":123,"sample_rate_hz":48000}'})
        assert response.status_code == 200
        assert response.json()['native_audio_timing']['first_sample_host_ns'] == 123
        assert c.get(path+'/media').content == wav
        changed = c.patch(path,json={'confirmed_text':'changed later'}).json()
        assert changed['review_status'] == 'pending' and not changed['accepted']
        c.post('/api/disconnect')
        assert c.post('/api/sessions/'+sid+'/resume').status_code == 400
        c.post('/api/connect',json={'source':'simulator'})
        assert c.post('/api/sessions/'+sid+'/resume').status_code == 200
        time.sleep(.2)
        rid = c.post('/api/collect',json={'step_id':step['step_id'],'duration_s':20}).json()['id']
        assert c.post('/api/record/'+rid+'/cancel').status_code == 200
        assert wait_for(c,rid)['status'] == 'cancelled'
        assert len(c.get('/api/sessions/'+sid+'/trials').json()) == 1


def test_articulation_and_reserved_visit_guards(tmp_path):
    store = Store(tmp_path); ids = seed_demo(store, sessions=2, repetitions=2)
    t = store.trials(ids[0])[0]
    store.add_trial_fields(ids[0],t['id'],{'articulation':'voiced'})
    with pytest.raises(ValueError,match='cannot be pooled'):
        train(store,ids,[ids[-1]])
    # Filtering a mixed visit removes voiced samples rather than using them as silent labels.
    store.add_trial_fields(ids[0],t['id'],{'articulation':'silent'})
    s = store.session(ids[0]); from gasp.storage import atomic_json
    s['collection'] = {'visit_role':'test'}; atomic_json(store.session_dir(s['id'])/'session.json',s)
    with pytest.raises(ValueError,match='cannot be used for fitting'):
        train(store,ids,[ids[-1]],articulation='silent')
    s['collection']['visit_role'] = 'calibration'; atomic_json(store.session_dir(s['id'])/'session.json',s)
    with pytest.raises(ValueError,match='Calibration visits'):
        train(store,ids,[ids[0]],articulation='silent')


def test_installed_app_requires_launch_token(tmp_path):
    with TestClient(create_app(tmp_path,app_token='a'*64)) as c:
        assert c.get('/api/health').status_code == 403
        assert c.get('/desktop?token=wrong').status_code == 403
        assert c.get('/api/health',headers={'Authorization':'Bearer '+'a'*64}).status_code == 200
        assert c.get('/desktop?token='+'a'*64).status_code == 200
        assert c.get('/api/health').status_code == 200
        assert c.post('/api/connect',json={},headers={'Origin':'https://evil.example'}).status_code == 403


def test_reviewed_schema_training_filters_modes_and_preserves_trim(tmp_path):
    from gasp.training import reviewed_signal, predict_trial
    store = Store(tmp_path); ids = seed_demo(store,sessions=2,repetitions=2)
    for sid in ids:
        originals = store.trials(sid)
        for t in originals:
            store.add_trial_fields(sid,t['id'],{'schema':2,'collection_protocol':'personal-training-v1',
                'prompt_text':t['label'],'confirmed_text':None,'accepted':False,'review_status':'pending'})
            store.update_trial(sid,t['id'],{'confirmed_text':t['label'],'accepted':True,
                                          'utterance_start_s':.2,'utterance_end_s':2.7})
        original = originals[0]; arr = store.load_signal(sid,original['id'])
        # An unreviewed take must not enter the fitted data, even with a matching prompt.
        store.save_trial(sid,original['label'],arr['timestamps_ns'],arr['iq'],arr['frame_numbers'],extra={
            'collection_protocol':'personal-training-v1','review_status':'pending','accepted':False,'articulation':'silent'})
        # A verified voiced take must not enter a silent-mode experiment.
        store.save_trial(sid,original['label'],arr['timestamps_ns'],arr['iq'],arr['frame_numbers'],extra={
            'collection_protocol':'personal-training-v1','review_status':'verified','accepted':True,'articulation':'voiced'})
    with pytest.raises(ValueError,match='cannot be pooled'): train(store,ids,[ids[-1]])
    report = train(store,ids,[ids[-1]],articulation='silent')
    assert report['train_examples']==6 and report['test_examples']==6
    assert all(r['utterance_end_s']==2.7 and r['articulation']=='silent' for r in report['dataset'])
    trial = next(t for t in store.trials(ids[0]) if t.get('utterance_end_s')==2.7)
    trimmed = reviewed_signal(store,ids[0],trial['id'],trial)
    assert len(trimmed['iq']) < trial['frames']
    assert len(store.load_signal(ids[0],trial['id'])['iq']) == trial['frames']
    assert predict_trial(store,report['id'],ids[0],trial['id'],threshold=0)['evaluation_use']=='training'
