import json
import time
import numpy as np
import pytest
from fastapi.testclient import TestClient
from gasp import dca
from gasp.server import create_app
from gasp.profile import bundled_profile
from gasp.storage import Store, atomic_json
from gasp.training import train
from dca_emulator import DCAEmulator


def wait_record(client, rid):
    for _ in range(150):
        result = client.get('/api/record/'+rid).json()
        if result['status'] in {'complete', 'failed', 'cancelled'}:
            return result
        time.sleep(.05)
    raise AssertionError('Capture did not finish')


@pytest.fixture
def hardware(monkeypatch):
    emulated = DCAEmulator(data_port=None).start()
    monkeypatch.setattr(dca, 'DCAControl', emulated.make_control)
    monkeypatch.setattr(dca, 'DATA_PORT', emulated.data_port)
    try:
        yield emulated
    finally:
        emulated.close()


def connect(client, hardware):
    return client.post('/api/connect', json={'source':'dca1000', 'profile':'dca-raw',
        'cli_port':hardware.cli_port, 'host_ip':'127.0.0.1', 'board_ip':'127.0.0.1', 'confirm_layout':True})


def test_real_udp_and_serial_prompt_capture_review_training_and_switch(tmp_path, hardware):
    app = create_app(tmp_path, research_enabled=True)
    with TestClient(app) as client:
        assert connect(client, hardware).status_code == 200
        live = client.get('/api/live').json()
        assert live['source'] == 'dca1000' and live['dca']['status'] == 'armed'
        assert live['capture_ready'] and not live['live_decode_available']
        assert client.post('/api/decode', json={'model_id':'unused'}).status_code == 400
        sid = client.post('/api/sessions', json={'name':'EMULATED DCA visit', 'subject':'EMULATED'}).json()['id']
        assert client.post('/api/connect',json={'source':'simulator'}).status_code == 400
        rid = client.post('/api/record',json={'label':'add a note', 'duration_s':.5}).json()['id']
        assert client.post('/api/disconnect').status_code == 400
        result = wait_record(client, rid)
        assert result['status'] == 'complete', result
        trial = result['trial']; tid = trial['id']
        assert trial['source'] == 'dca1000' and not trial['synthetic']
        assert trial['shape'][1:] == [64, 12] and trial['frames'] >= 8
        assert trial['raw_quality']['packets'] > 0 and trial['raw_quality']['missing_bytes'] == 0
        assert trial['prompt_ready_monotonic_ns'] < trial['prompt_end_monotonic_ns']
        arr = app.state.store.load_signal(sid, tid)
        assert np.all(np.diff(arr['timestamps_ns']) > 0)
        assert np.argmax(abs(arr['iq'][0,:,0])) == 8
        assert client.get(f'/api/sessions/{sid}/trials/{tid}/signal').status_code == 200
        raw = client.get(f'/api/sessions/{sid}/trials/{tid}/raw/adc.bin')
        manifest = client.get(f'/api/sessions/{sid}/trials/{tid}/raw/manifest.json').json()
        assert raw.content and manifest['status'] == 'complete' and manifest['context']['label'] == 'add a note'
        assert client.get(f'/api/sessions/{sid}/trials/{tid}/raw/radar.cfg').status_code == 200
        assert client.get(f'/api/sessions/{sid}/trials/{tid}/raw/other').status_code == 404
        # A second physical capture on the same connection resets offsets without overwriting the first.
        second = client.post('/api/record',json={'label':'save this note','duration_s':.5}).json()['id']
        second_result = wait_record(client, second)
        assert second_result['status'] == 'complete', second_result
        assert second_result['trial']['raw_capture_dir'] != trial['raw_capture_dir']
        assert dca.STOP in hardware.dca_commands and hardware.commands.count('sensorStop') >= 3
        # Exercise the same training path with bounded duplicates of ADC fixtures.
        store = app.state.store
        second_session = store.create_session('EMULATED heldout', 'EMULATED', 'dca1000', bundled_profile('dca-raw'))
        for session in (store.session(sid), second_session):
            for label in ('add a note', 'save this note'):
                for _ in range(2):
                    store.save_trial(session['id'],label,arr['timestamps_ns'],arr['iq'],arr['frame_numbers'],
                                     extra={'source':'dca1000','synthetic':False,'articulation':'silent'})
        report = train(store,[sid,second_session['id']],[second_session['id']])
        assert report['source'] == 'dca1000' and report['test_examples'] == 4
        prediction = client.post('/api/predict-trial',json={'model_id':report['id'],
            'session_id':sid,'trial_id':tid,'threshold':0}).json()
        assert prediction['source'] == 'dca1000' and prediction['evaluation_use'] == 'training'
        assert client.get('/api/live').json()['last_trial']['trial_id'] == second_result['trial']['id']
        store.save_trial(sid,'add a note',arr['timestamps_ns'],arr['iq'],arr['frame_numbers'],
                         extra={'adc_quality':{'dropped_frames':2,'complete_frames':10}})
        response = client.post('/api/train',json={'session_ids':[sid,second_session['id']],
                                                'test_session_ids':[second_session['id']]})
        jid = response.json()['id']
        for _ in range(100):
            job = client.get('/api/jobs/'+jid).json()
            if job['status'] in {'complete','failed'}:break
            time.sleep(.03)
        assert job['status'] == 'complete', job
        assert any('ADC frames lost' in r['reason'] for r in job['report']['rejected_trials'])
        usb = store.create_session('USB distribution','EMULATED','serial',bundled_profile())
        with pytest.raises(ValueError,match='same subject, source and radar profile'):
            train(store,[sid,usb['id']],[usb['id']])
        assert client.post('/api/disconnect').status_code == 200
        assert client.post('/api/connect',json={'source':'simulator'}).status_code == 200
        state = client.get('/api/live').json()
        assert state['source'] == 'simulator' and state['session'] is None and state['dca'] is None


def test_cancel_and_no_packets_preserve_raw_but_do_not_add_training_trial(tmp_path, hardware):
    with TestClient(create_app(tmp_path)) as client:
        assert connect(client, hardware).status_code == 200
        sid = client.post('/api/sessions',json={'name':'EMULATED cancellation'}).json()['id']
        rid = client.post('/api/record',json={'label':'cancel me','duration_s':5}).json()['id']
        assert client.post('/api/record/'+rid+'/cancel').status_code == 200
        result = wait_record(client, rid)
        assert result['status'] == 'cancelled', result
        path = tmp_path/'raw'/sid/rid/'manifest.json'
        assert json.loads(path.read_text())['status'] == 'cancelled'
        assert not client.get(f'/api/sessions/{sid}/trials').json()
        hardware.no_data = True
        rid = client.post('/api/record',json={'label':'no packets','duration_s':.5}).json()['id']
        result = wait_record(client,rid)
        assert result['status'] == 'failed' and 'No DCA packets' in result['error']
        assert client.get('/api/live').json()['status'] == 'error'
        assert client.post('/api/disconnect').status_code == 200


def test_dca_requires_decoder_and_raw_profile(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.post('/api/connect',json={'source':'dca1000','profile':'dca-raw','cli_port':'unused'}).status_code == 400
        assert client.post('/api/connect',json={'source':'dca1000','cli_port':'unused','confirm_layout':True}).status_code == 400
        assert client.post('/api/connect',json={'source':'dca1000','host_ip':'not-an-ip'}).status_code == 422


def test_stop_failure_is_failed_even_when_cancelling(tmp_path, hardware):
    with TestClient(create_app(tmp_path)) as client:
        assert connect(client,hardware).status_code == 200
        client.post('/api/sessions',json={'name':'EMULATED stop failure'})
        assert client.post('/api/record',json={'label':'too long','duration_s':26}).status_code == 400
        hardware.fail_stop = True
        rid = client.post('/api/record',json={'label':'cancel','duration_s':5}).json()['id']
        client.post('/api/record/'+rid+'/cancel')
        result = wait_record(client,rid)
        assert result['status'] == 'failed' and 'Hardware stop failed' in result['error']
        assert client.get('/api/live').json()['status'] == 'error'
        hardware.fail_stop = False
        assert client.post('/api/disconnect').status_code == 200


def test_import_preserves_loss_gaps_for_training_filters(tmp_path):
    store = Store(tmp_path);profile = bundled_profile('dca-raw')
    session = store.create_session('loss fixture','EMULATED','dca1000',profile)
    folder = tmp_path/'raw'/'loss';folder.mkdir(parents=True)
    frame_bytes = profile.summary()['adc_bytes_per_frame']
    (folder/'adc.bin').write_bytes(bytes(frame_bytes*3))
    atomic_json(folder/'manifest.json',{'status':'complete','profile':profile.summary(),
        'missing_intervals':[[frame_bytes+1,frame_bytes+8]],'packets':1,'duplicates':0,
        'out_of_order':0,'missing_bytes':7,'bytes':frame_bytes*3,'tail_loss_unknown':True})
    trial = dca.import_capture(store,folder,session,'test')
    assert trial['adc_quality']['dropped_frames'] == 1
    assert trial['frame_gaps'] == profile.loops
    numbers = store.load_signal(session['id'],trial['id'])['frame_numbers']
    assert numbers[profile.loops] == 2*profile.loops


def test_manual_finish_retains_dca_take_for_review(tmp_path, hardware):
    with TestClient(create_app(tmp_path)) as c:
        assert connect(c,hardware).status_code == 200
        s = c.post('/api/sessions',json={'name':'EMULATED collection', 'collection':{
            'deck_id':'commands-v1','mode':'silent','visit_role':'train'}}).json()
        step = s['collection']['plan']['steps'][0]
        rid = c.post('/api/collect',json={'step_id':step['step_id'],'duration_s':20}).json()['id']
        for _ in range(100):
            if c.get('/api/record/'+rid).json()['status'] == 'recording': break
            time.sleep(.02)
        time.sleep(.55)
        assert c.post('/api/record/'+rid+'/stop').status_code == 200
        r = wait_record(c,rid)
        assert r['status'] == 'complete',r
        assert not r['trial']['accepted'] and r['trial']['review_status'] == 'pending'
        assert r['trial']['prompt_text'] == step['prompt_text']
        assert r['trial']['duration_s'] < 5
