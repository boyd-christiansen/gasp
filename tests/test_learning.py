"""Frozen data, split integrity and the real local collect/train/evaluate API."""
import io
import json
import threading
import time
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient

from gasp.cli import seed_demo
from gasp import learning_data as data
from gasp import learning_models as models
from gasp.learning_runs import Runs
from gasp.server import create_app
from gasp.storage import Store, atomic_json


def prepared_store(root):
    store = Store(root)
    ids = seed_demo(store, sessions=3, repetitions=2)
    for sid, role in zip(ids, data.ROLES):
        session = store.session(sid)
        session['collection'] = dict(visit_role=role, acquisition_id=sid, plan=dict(task='phrases'))
        atomic_json(store.session_dir(sid)/'session.json', session)
        for take in store.trials(sid):
            store.update_trial(sid, take['id'], dict(confirmed_text=take['label'], accepted=True))
    scope = dict(subject='synthetic-fixture', source='simulator', profile=store.session(ids[0])['profile']['sha256'])
    return store, ids, scope


def wait(c, rid, expected='complete'):
    for _ in range(400):
        value = c.get('/api/learning/runs/'+rid).json()
        if value['status'] not in {'queued','preparing','training','evaluating','cancelling'}:
            assert value['status'] == expected, value
            return value
        time.sleep(.02)
    pytest.fail('Training did not finish')


def test_snapshot_pins_annotations_and_never_uses_test_for_fit(tmp_path, monkeypatch):
    store, ids, scope = prepared_store(tmp_path)
    inv = data.inventory(store, **scope)
    assert inv['ready'] and inv['counts']['train']['takes'] == 6
    snap = data.freeze(store, inv, 'phrase-v2')
    take = store.trials(ids[0])[0]
    store.update_trial(ids[0], take['id'], {'confirmed_text':'edited later','accepted':True})
    frozen = data.load_snapshot(store, snap['id'])
    assert next(r for r in frozen['rows'] if r['trial_id']==take['id'])['text'] == take['label']
    original = models.signal
    accessed = []
    def checked(root, row):
        assert row['split'] != 'test'
        accessed.append(row['split'])
        return original(root, row)
    monkeypatch.setattr(models, 'signal', checked)
    result = models.fit(frozen, tmp_path, tmp_path/'result')
    assert set(accessed) == {'train','validation'}
    assert result['development']['metrics']['n'] == 6
    assert 'duration_only_accuracy' in result['development']['metrics']
    manifest = tmp_path/'datasets'/f"{snap['id']}.json"
    value = json.loads(manifest.read_text()); value['rows'][0]['text']='tampered'
    atomic_json(manifest,value)
    with pytest.raises(ValueError, match='checksum'):data.load_snapshot(store,snap['id'])


def test_readiness_exclusions_mode_and_legacy_roles(tmp_path):
    store, ids, scope = prepared_store(tmp_path)
    take=store.trials(ids[0])[0]
    store.update_trial(ids[0],take['id'],{'confirmed_text':'pending edit'})
    inv=data.inventory(store,**scope)
    assert inv['counts']['train']['takes']==5 and not inv['ready']
    assert any(e['reason']=='Needs review' for e in inv['excluded'])
    assert not data.inventory(store,**{**scope,'source':'serial'})['rows']
    assert not data.inventory(store,**{**scope,'subject':'another person'})['rows']
    assert not data.inventory(store,**scope,exclude_sessions=[ids[0]])['ready']
    session=store.session(ids[1]);session.pop('collection');atomic_json(store.session_dir(ids[1])/'session.json',session)
    assert data.inventory(store,**scope)['counts']['validation']['takes']==0


def test_split_leakage_rules_are_task_specific(tmp_path):
    store, ids, scope=prepared_store(tmp_path)
    rows=data.inventory(store,**scope)['rows']
    assert not data.leakage_errors(rows,'phrases')
    assert any('sentence' in e for e in data.leakage_errors(rows,'sentences'))
    a,b=dict(rows[0]),dict(rows[6]);b['acquisition_id']=a['acquisition_id']
    assert any('sitting' in e for e in data.leakage_errors([a,b],'phrases'))
    b=dict(rows[6]);a['pair_id']=b['pair_id']='same-pair'
    assert any('paired' in e for e in data.leakage_errors([a,b],'phrases'))
    b=dict(rows[6]);b['signal_sha256']=a['signal_sha256'];a['pair_id']=None
    assert any('recording' in e for e in data.leakage_errors([a,b],'phrases'))


def test_api_train_then_explicit_final_evaluation_and_deletion(tmp_path):
    store,ids,scope=prepared_store(tmp_path)
    with TestClient(create_app(tmp_path)) as c:
        overview=c.get('/api/learning',params=scope).json()
        assert overview['phrase']['ready'] and not overview['runs']
        launch=c.post('/api/learning/runs',json=scope)
        assert launch.status_code==200,launch.text
        fit=wait(c,launch.json()['id'])
        assert fit['result']['development']['split']=='validation'
        assert not fit['result'].get('final_test')
        assert c.post(f"/api/learning/runs/{fit['id']}/final-check",json={}).status_code==400
        final=c.post(f"/api/learning/runs/{fit['id']}/final-check",json={'confirm':True})
        assert final.status_code==200,final.text
        result=wait(c,final.json()['id'])
        assert result['result']['final_test']['split']=='test'
        assert result['candidate_model_sha256']==fit['result']['model_sha256']
        assert c.post(f"/api/learning/runs/{fit['id']}/final-check",json={'confirm':True}).status_code==400
        assert len(c.get('/api/learning/dependencies/'+ids[0]).json())==1
        final_snapshot=c.get('/api/learning/datasets/'+result['dataset_id']).json()
        assert {r['split'] for r in final_snapshot['rows']} == {'test'}
        assert c.request('DELETE','/api/sessions/'+ids[0],json={'confirm':True}).status_code==200
        saved=c.get('/api/learning/runs/'+fit['id']).json()
        assert saved['status']=='complete' and not saved['availability']['available']
        assert saved['result']==fit['result']


def test_cancel_delete_guard_and_restart_reconciliation(tmp_path,monkeypatch):
    store,ids,scope=prepared_store(tmp_path)
    entered,release=threading.Event(),threading.Event()
    def fit(snap,root,out,notify,check):
        entered.set();release.wait(5);check()
        raise AssertionError('Cancelled job should not produce a model')
    monkeypatch.setattr(models,'fit',fit)
    with TestClient(create_app(tmp_path)) as c:
        run=c.post('/api/learning/runs',json=scope).json();assert entered.wait(2)
        assert c.request('DELETE','/api/sessions/'+ids[0],json={'confirm':True}).status_code==400
        assert c.post('/api/learning/runs/'+run['id']+'/cancel').status_code==200
        release.set();wait(c,run['id'],'cancelled')
    path=tmp_path/'training-runs'/run['id']/'run.json'
    saved=json.loads(path.read_text());saved['status']='training';atomic_json(path,saved)
    restarted=Runs(store)
    try:assert restarted.get(run['id'])['status']=='interrupted'
    finally:restarted.close()


def sentence_store(root):
    store,ids,scope=prepared_store(root)
    for j,sid in enumerate(ids):
        session=store.session(sid);session['collection']['plan']['task']='reading'
        atomic_json(store.session_dir(sid)/'session.json',session)
        for i,take in enumerate(store.trials(sid)):
            store.update_trial(sid,take['id'],{'confirmed_text':f'group {j} item {i}','accepted':True})
    # Eight training rows are the minimum pipeline check.
    for i in range(2):
        trial=store.trials(ids[0])[i];arr=store.load_signal(ids[0],trial['id'])
        t=store.save_trial(ids[0],f'extra {i}',arr['timestamps_ns'],arr['iq']+i+3,arr['frame_numbers'],extra={'articulation':'silent'})
        store.update_trial(ids[0],t['id'],{'confirmed_text':f'extra {i}','accepted':True})
    return store,ids,{**scope,'recipe_id':'radar-ctc-v1'}


def test_package_has_no_final_test_and_import_recomputes_scores(tmp_path):
    store,ids,scope=sentence_store(tmp_path)
    with TestClient(create_app(tmp_path)) as c:
        started=c.post('/api/learning/runs',json=scope)
        assert started.status_code==200,started.text
        run=wait(c,started.json()['id'],'prepared')
        package=c.get('/api/learning/runs/'+run['id']+'/package')
        assert package.status_code==200
        with zipfile.ZipFile(io.BytesIO(package.content)) as z:
            job=json.loads(z.read('job.json'))
            assert all(r['split']!='test' for r in job['snapshot']['rows'])
            assert ids[-1] not in z.read('job.json').decode()
            assert not any(ids[-1] in name for name in z.namelist())
        from gasp.sequence_model import network, VOCAB
        torch=pytest.importorskip('torch')
        inputs=job['snapshot']['rows'][0]['shape'][2]*16*3+1
        config=dict(recipe=job['snapshot']['recipe'],task='sentences',input_size=inputs,vocab=VOCAB)
        net=network(torch,inputs,config['recipe']['hidden_size'])
        weights_buffer=io.BytesIO()
        np.savez_compressed(weights_buffer,**{k:v.detach().numpy() for k,v in net.state_dict().items()})
        weights=weights_buffer.getvalue()
        import hashlib
        predictions=[dict(session_id=r['session_id'],trial_id=r['trial_id'],predicted=r['text'])
                     for r in job['snapshot']['rows'] if r['split']=='validation']
        receipt=dict(run_id=run['id'],job_sha256=job['sha256'],model_sha256=hashlib.sha256(weights).hexdigest(),
                     predictions=predictions,metrics={'wer':99},worker={'source':run['source']})
        payload=io.BytesIO()
        with zipfile.ZipFile(payload,'w') as z:
            z.writestr('result.json',json.dumps(receipt));z.writestr('model.json',json.dumps(config));z.writestr('model.npz',weights)
        response=c.post('/api/learning/runs/'+run['id']+'/result',content=payload.getvalue())
        assert response.status_code==200,response.text
        assert response.json()['result']['development']['metrics']['wer']==0
        # Export copies must not quietly preserve deleted source recordings.
        assert c.request('DELETE','/api/sessions/'+ids[0],json={'confirm':True}).status_code==200
        assert not (tmp_path/'training-runs'/run['id']/'package.zip').exists()


def test_word_error_rates_include_insertions_and_empty_predictions():
    assert models.edit_counts(['a','b'],['a','c','d'])==dict(substitutions=1,insertions=1,deletions=0)
    measured=models.metrics('sentences',[dict(expected='one two',predicted=''),dict(expected='three',predicted='three four')])
    assert measured['wer']==1 and measured['deletions']==2 and measured['insertions']==1


def test_manifest_race_and_signal_checksum_are_rejected(tmp_path):
    store,ids,scope=prepared_store(tmp_path)
    inventory=data.inventory(store,**scope);row=inventory['rows'][0]
    store.update_trial(row['session_id'],row['trial_id'],{'confirmed_text':'changed','accepted':True})
    with pytest.raises(ValueError,match='changed'):data.freeze(store,inventory,'phrase-v2')
    inventory=data.inventory(store,**scope)
    path=store.root/inventory['rows'][1]['path'];path.write_bytes(path.read_bytes()+b'tampered')
    with pytest.raises(ValueError,match='checksum'):data.freeze(store,inventory,'phrase-v2')


def test_scheduled_worker_roundtrip_and_final_candidate_integrity(tmp_path, monkeypatch):
    """Small CPU fixture with a simulated allocation ID; no rack job is submitted."""
    from gasp.learning_worker import execute
    monkeypatch.setitem(data.RECIPES, 'phrase-v2', {**data.RECIPES['phrase-v2'], 'runner':'package'})
    monkeypatch.setenv('SLURM_JOB_ID', 'unit-test-cpu-fixture')
    store,ids,scope=prepared_store(tmp_path)
    with TestClient(create_app(tmp_path)) as c:
        run=wait(c,c.post('/api/learning/runs',json=scope).json()['id'],'prepared')
        package=tmp_path/'training-runs'/run['id']/'package.zip'
        result=execute(package,tmp_path/'worker')
        imported=c.post('/api/learning/runs/'+run['id']+'/result',content=result.read_bytes())
        assert imported.status_code==200, imported.text
        assert imported.json()['result']['development']['metrics']['n']==6
        # Inference on new test data does not need the original training recordings.
        assert c.request('DELETE','/api/sessions/'+ids[0],json={'confirm':True}).status_code==200
        final=c.post('/api/learning/runs/'+run['id']+'/final-check',json={'confirm':True})
        assert final.status_code==200, final.text
        final_run=wait(c,final.json()['id'],'prepared')
        final_package=tmp_path/'training-runs'/final_run['id']/'package.zip'
        final_result=execute(final_package,tmp_path/'final-worker')
        # Reject changes to the candidate's decoder/class mapping as well as weights.
        tampered=io.BytesIO()
        with zipfile.ZipFile(final_result) as original, zipfile.ZipFile(tampered,'w') as altered:
            for name in original.namelist():
                payload=original.read(name)
                if name=='model.json':
                    config=json.loads(payload);config['classes']=list(reversed(config['classes']))
                    payload=json.dumps(config).encode()
                altered.writestr(name,payload)
        rejected=c.post('/api/learning/runs/'+final_run['id']+'/result',content=tampered.getvalue())
        assert rejected.status_code==400 and 'configuration' in rejected.text
        imported=c.post('/api/learning/runs/'+final_run['id']+'/result',content=final_result.read_bytes())
        assert imported.status_code==200,imported.text
        assert imported.json()['result']['final_test']['metrics']['n']==6


def test_mixed_mode_headline_does_not_hide_silent_errors():
    from gasp.learning_api import headline
    report=models.report('sentences',[
        dict(session_id='a',trial_id='1',annotation_revision=1,acquisition_id='a',text='hello',control=False,articulation='silent'),
        dict(session_id='a',trial_id='2',annotation_revision=1,acquisition_id='a',text='hello',control=False,articulation='voiced'),
    ],['wrong','hello'],'validation')
    assert report['metrics']['wer']==.5
    assert headline(report)['wer']==1
    assert headline({'metrics':None}) is None
