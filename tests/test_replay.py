import json
import struct
import numpy as np
import pytest
from fastapi.testclient import TestClient
from gasp.server import create_app
from gasp.profile import bundled_profile
from gasp.storage import Store
from gasp.collection import make_plan
from gasp.protocol import HEADER, TL, MAGIC
from gasp.replay import Replay, radar_gaps


def test_missing_frame_locations_survive_wrap_and_display_decimation(tmp_path):
    # The uint32 wrap itself is continuous. One actual skip happens at 2 s.
    numbers = (np.arange(121, dtype=np.int64) + 0xffffffe0) & 0xffffffff
    keep = np.arange(121) != 40
    numbers = numbers[keep]
    stamps = 9_000_000_000 + np.arange(121)[keep]*50_000_000
    expected = [dict(start_s=1.95, end_s=2.05, missing_frames=1)]
    assert radar_gaps(numbers, stamps) == expected
    store = Store(tmp_path)
    session = store.create_session('gap fixture','synthetic','simulator',bundled_profile('usb-phase-20hz'))
    take = store.save_trial(session['id'],'synthetic gap',stamps,np.ones((120,64,12)),numbers)
    preview = Replay(store).preview(session['id'],take['id'],limit=5)
    assert preview['display_decimated'] and preview['gaps'] == [[1.95,2.05]]
    assert preview['gap_details'] == expected
    from gasp.audio_review import inspect_take
    original = (store.trial_dir(session['id'],take['id'])/'radar.npz').read_bytes()
    quality = inspect_take(store,session['id'],take['id'])
    assert quality['radar_gaps'] == preview['gap_details']
    assert quality['warnings'] == [{'code':'radar_gap','message':'1 radar frame missing (about 50 ms).'}]
    assert (store.trial_dir(session['id'],take['id'])/'radar.npz').read_bytes() == original


def fixture_take(root):
    store=Store(root);p=bundled_profile('usb-doppler-10hz')
    session=store.create_session('fixture','test-person','serial',p)
    rd=np.arange(64*16,dtype='<u2').reshape(64,16)
    point=np.array([[.1,.5,.2,-.3]],dtype='<f4')
    z=np.ones((3,64,12),np.complex64)*(100+20j)
    packets=[]
    for i in range(3):
        iq=np.stack([z[i].imag,z[i].real],axis=-1).astype('<i2').tobytes()
        payload=b''.join(TL.pack(k,len(v))+v for k,v in [(8,iq),(5,rd.tobytes()),(1,point.tobytes())])
        size=(40+len(payload)+31)//32*32
        packets.append(HEADER.pack(MAGIC,0x03060200,size,0xA6843,i,0,1,3,0)+payload+bytes(size-40-len(payload)))
    trial=store.save_trial(session['id'],'hello world',[100,1000000100,2000000100],z,[0,1,2],packets,{
        'collection_protocol':'fixture','confirmed_text':None,'prompt_text':'hello world','accepted':False,'review_status':'pending'})
    return store,session,trial,rd,point


def test_replay_uses_real_complex_doppler_and_points(tmp_path):
    store,s,t,rd,points=fixture_take(tmp_path);r=Replay(store)
    view=r.preview(s['id'],t['id'])
    assert view['capabilities']['range_doppler'] and view['capabilities']['points']
    assert view['i']==[100]*3 and view['q']==[20]*3
    assert view['all_time_s']==[0,1,2] and view['first_timestamp_ns']=='100'
    f=r.frame(s['id'],t['id'],1)
    np.testing.assert_array_equal(f['range_doppler'],np.fft.fftshift(rd,axes=1))
    np.testing.assert_allclose(f['points'],points)
    assert len(f['doppler_velocity_m_s'])==16


def test_annotations_revisions_and_original_artifacts(tmp_path):
    store,s,t,_,_=fixture_take(tmp_path)
    path=f"/api/sessions/{s['id']}/trials/{t['id']}"
    before=(store.trial_dir(s['id'],t['id'])/'radar.npz').read_bytes()
    words=[{'text':'hello','start_s':.1,'end_s':.8},{'text':'world','start_s':1,'end_s':1.8}]
    with TestClient(create_app(tmp_path)) as c:
        assert c.get('/api/recordings').json()[0]['subject']=='test-person'
        kept=c.patch(path,json={'confirmed_text':'hello world','words':words,'accepted':True,'base_revision':0}).json()
        assert kept['accepted'] and kept['annotation_revision']==1
        assert c.patch(path,json={'confirmed_text':'stale','base_revision':0}).status_code==400
        assert c.patch(path,json={'words':[dict(words[0],end_s=1.4),words[1]],'base_revision':1}).status_code==400
        updated=c.patch(path,json={'words':[dict(words[0],end_s=.7),words[1]],'base_revision':1}).json()
        assert not updated['accepted'] and updated['review_status']=='pending'
        assert updated['annotation_revision']==2 and updated['prompt_text']=='hello world'
        assert c.get(path+'/replay').status_code==200 and c.get(path+'/frame?index=1').status_code==200
        assert len(list((store.trial_dir(s['id'],t['id'])/'annotations').glob('*.json')))==2
    assert (store.trial_dir(s['id'],t['id'])/'radar.npz').read_bytes()==before


def test_reader_preserves_book_order_and_resumes_by_passage():
    script=' '.join(f'word{i}' for i in range(365))
    p=make_plan('reader','voiced',1,script_text=script,words_per_minute=130)
    assert len(p['steps'])==4
    assert ' '.join(s['prompt_text'] for s in p['steps'])==script
    assert max(s['duration_s'] for s in p['steps'])<=180
    assert p['task']=='reading' and p['script_sha256']
    with pytest.raises(ValueError):make_plan('reader',script_text='')
    w=make_plan('custom-words','silent',2,'fixed',script_text='blue\nmug\nadd a note')
    assert len(w['steps'])==6 and {s['prompt_text'] for s in w['steps']}=={'blue','mug','add a note'}


def test_reader_capture_conditions_and_compact_library(tmp_path):
    import time
    with TestClient(create_app(tmp_path)) as c:
        assert c.post('/api/connect', json={'source':'simulator'}).status_code == 200
        script=' '.join(f'word{i}' for i in range(250))
        session=c.post('/api/sessions',json={'name':'Reader QA','subject':'test-person','collection':{
            'deck_id':'reader','mode':'voiced','repetitions':1,'script_text':script,
            'location':'test-room','enclosure':'test-case','mount':'desk','yaw_deg':10}}).json()
        sid=session['id']; plan=session['collection']['plan']
        assert len(plan['steps'])==3 and plan['script_text']==script
        summary=c.get('/api/blocks').json()[0]['collection']
        assert 'script_text' not in summary and 'steps' not in summary['plan']
        time.sleep(.2)
        rid=c.post('/api/collect',json={'step_id':plan['steps'][0]['step_id'],
            'duration_s':100,'capture_method':'reader','reader_follow':'paced','reader_wpm':130}).json()['id']
        time.sleep(.6)
        assert c.post('/api/record/'+rid+'/stop').status_code==200
        for _ in range(100):
            result=c.get('/api/record/'+rid).json()
            if result['status'] in {'complete','failed'}:break
            time.sleep(.03)
        assert result['status']=='complete',result
        t=result['trial']
        assert t['task']=='reading' and t['capture_method']=='reader' and not t['accepted']
        assert t['capture_conditions']['yaw_deg']==10 and t['capture_conditions']['location']=='test-room'
        assert t['script_sha256']==plan['script_sha256'] and t['reader_wpm']==130
        assert c.post('/api/sessions/'+sid+'/resume').json()['collection']['plan']==plan


def test_legacy_review_status_and_trim_validation(tmp_path):
    store=Store(tmp_path);p=bundled_profile('usb-phase-20hz')
    s=store.create_session('legacy','test-person','simulator',p)
    t=store.save_trial(s['id'],'hello',[1,1000000001,2000000001],np.ones((3,64,12)),[1,2,3])
    assert store.update_trial(s['id'],t['id'],{'accepted':False})['review_status']=='rejected'
    assert store.update_trial(s['id'],t['id'],{'accepted':True})['review_status']=='verified'
    with pytest.raises(ValueError,match='boundaries'):
        store.update_trial(s['id'],t['id'],{'utterance_end_s':10})


def test_dca_doppler_uses_complete_bursts_and_preserves_missing_samples(tmp_path):
    store=Store(tmp_path);p=bundled_profile('dca-raw')
    s=store.create_session('raw fixture','test-person','dca1000',p)
    n=np.arange(31,dtype=np.uint32)
    t=np.array([round((int(i)//16*.02+(int(i)%16)*p.tx_count*p.chirp_period_us*1e-6)*1e9) for i in n])
    z=np.broadcast_to(np.exp(2j*np.pi*3*(n%16)/16)[:,None,None],(31,64,12))
    trial=store.save_trial(s['id'],'burst fixture',t,z,n)
    replay=Replay(store)
    assert replay.preview(s['id'],trial['id'])['capabilities']['range_doppler']
    complete=replay.frame(s['id'],trial['id'],3)
    assert np.argmax(complete['range_doppler'][8])==11
    assert complete['doppler_unit']=='Relative dB'
    assert replay.frame(s['id'],trial['id'],20)['range_doppler'] is None
