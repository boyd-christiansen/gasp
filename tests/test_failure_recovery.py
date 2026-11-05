"""Failure-path checks use disposable data; never touch a user's recordings."""
import json
import time
import numpy as np
import pytest
from fastapi.testclient import TestClient
from gasp.server import create_app
from gasp.storage import Store
from gasp.profile import bundled_profile
from gasp.audio_review import inspect_take


def sample(root, gaps=False):
    store=Store(root)
    session=store.create_session('Failure fixture','synthetic-fixture','simulator',bundled_profile('usb-phase-20hz'))
    numbers=np.delete(np.arange(81),30) if gaps else np.arange(81)
    take=store.save_trial(session['id'],'Please continue',numbers*50_000_000,np.ones((len(numbers),64,12)),numbers,
        extra=dict(articulation='voiced',accepted=False,review_status='pending',confirmed_text='Please continue'))
    return store,session['id'],take['id']


def test_partial_boundary_is_durable_draft_but_not_verified(tmp_path):
    store,sid,tid=sample(tmp_path)
    words=[dict(text='Please',start_s=.5,end_s=None),dict(text='continue',start_s=None,end_s=None)]
    path=f'/api/sessions/{sid}/trials/{tid}'
    with TestClient(create_app(tmp_path)) as c:
        r=c.patch(path,json=dict(words=words,base_revision=0))
        assert r.status_code==200,r.text
        assert r.json()['review_status']=='pending'
        assert Store(tmp_path).trials(sid)[0]['words'][0]['start_s']==.5
        # Keeping without resending words must not bypass interval validation.
        r=c.patch(path,json=dict(accepted=True,base_revision=1))
        assert r.status_code==400 and 'unfinished' in r.text
        words[0]['end_s']=.8
        r=c.patch(path,json=dict(words=words,accepted=True,base_revision=1))
        assert r.status_code==200 and r.json()['accepted']
        # Whole-utterance supervision does not require word timings.
        assert c.patch(path,json=dict(words=[],accepted=True,base_revision=2)).status_code==200


@pytest.mark.parametrize('start,end',[(float('nan'),None),(-.1,None),(5,None),(.9,.5)])
def test_invalid_partial_boundaries_cannot_corrupt_drafts(tmp_path,start,end):
    store,sid,tid=sample(tmp_path)
    before=(store.trial_dir(sid,tid)/'trial.json').read_bytes()
    with pytest.raises(ValueError):
        store.update_trial(sid,tid,{'words':[dict(text='Please',start_s=start,end_s=end),dict(text='continue')]})
    assert (store.trial_dir(sid,tid)/'trial.json').read_bytes()==before


def test_audio_attachment_retry_and_conflicting_retry(tmp_path):
    store,sid,tid=sample(tmp_path)
    with TestClient(create_app(tmp_path)) as c:
        url=f'/api/sessions/{sid}/trials/{tid}/media'
        headers={'Content-Type':'audio/wav','X-Audio-Timing':json.dumps({'frames':8000,'sample_rate_hz':16000})}
        first=c.put(url,content=b'original recording',headers=headers)
        assert first.status_code==200,first.text
        assert c.put(url,content=b'original recording',headers=headers).json()==first.json()
        assert c.put(url,content=b'different recording',headers=headers).status_code==400
        assert c.put(url,content=b'original recording',headers={**headers,'X-Audio-Timing':'{}'}).status_code==400
        assert (store.trial_dir(sid,tid)/'reference.wav').read_bytes()==b'original recording'


def test_audio_recovers_after_manifest_write_failure(tmp_path,monkeypatch):
    store,sid,tid=sample(tmp_path);app=create_app(tmp_path)
    original=app.state.store.add_trial_fields
    def fail(*args,**kwargs):raise OSError('Disk write interrupted')
    with TestClient(app,raise_server_exceptions=False) as c:
        url=f'/api/sessions/{sid}/trials/{tid}/media'
        monkeypatch.setattr(app.state.store,'add_trial_fields',fail)
        assert c.put(url,content=b'surviving audio',headers={'Content-Type':'audio/wav'}).status_code==500
        monkeypatch.setattr(app.state.store,'add_trial_fields',original)
        assert c.put(url,content=b'surviving audio',headers={'Content-Type':'audio/wav'}).status_code==200
        assert c.get(f'/api/sessions/{sid}/trials/{tid}').json()['media']['bytes']==15


@pytest.mark.parametrize('timing',['[]','null','{"frames":NaN}','{broken'])
def test_invalid_audio_metadata_leaves_no_orphan(tmp_path,timing):
    store,sid,tid=sample(tmp_path)
    with TestClient(create_app(tmp_path)) as c:
        url=f'/api/sessions/{sid}/trials/{tid}/media'
        assert c.put(url,content=b'audio',headers={'Content-Type':'audio/wav','X-Audio-Timing':timing}).status_code==400
        assert not list(store.trial_dir(sid,tid).glob('reference*'))
        assert not list(store.trial_dir(sid,tid).glob('*.upload'))
        assert c.put(url,content=b'',headers={'Content-Type':'audio/wav'}).status_code==400


@pytest.mark.parametrize('failure',['reported','stalled'])
def test_sensor_failure_ends_active_capture_and_allows_reconnect(tmp_path,failure):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        assert c.post('/api/connect',json={'source':'simulator'}).status_code==200
        session=c.post('/api/collections/calibration/sessions',json={'setup':{'subject':'synthetic-fixture'}}).json()
        step=next(x for x in session['collection']['plan']['steps'] if x['prompt_id']=='jaw')
        time.sleep(.25)
        r=c.post('/api/collect',json={'step_id':step['step_id']});assert r.status_code==200,r.text
        rid=r.json()['id'];engine=app.state.engine
        if failure=='reported':engine._error('USB disconnected')
        else:engine.source.close()
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            status=c.get('/api/record/'+rid).json()
            if status['status']=='failed':break
            time.sleep(.05)
        assert status['status']=='failed',status
        assert not engine.recording and not app.state.store.trials(session['id'])
        assert c.post('/api/disconnect').status_code==200
        assert engine.error is None
        assert c.post('/api/connect',json={'source':'simulator'}).status_code==200


def test_small_gap_is_advisory_and_still_located(tmp_path):
    store,sid,tid=sample(tmp_path,gaps=True)
    quality=inspect_take(store,sid,tid)
    warning=next(w for w in quality['warnings'] if w['code']=='radar_gap')
    assert not warning['requires_action']
    assert quality['radar_gaps']
