import time
import numpy as np
from scipy.io import wavfile
from fastapi.testclient import TestClient
from gasp.audio_review import analyze_audio, acoustic_words, propose_words, inspect_take
from gasp.server import create_app
from gasp.storage import Store
from gasp.profile import bundled_profile


def test_alignment_preserves_script_and_missing_words():
    result=propose_words('pa · pa ta ka',[
        {'text':'pa','start':0,'end':.2}, {'text':'unexpected','start':.25,'end':.3},
        {'text':'pa','start':.4,'end':.6}, {'text':'ka','start':.8,'end':1}],.1,2)
    assert [w['text'] for w in result]==['pa','pa','ta','ka']
    assert [w['start_s'] for w in result]==[.1,.5,None,.9]
    assert propose_words('hello',[{'text':'hello','start':-.5,'end':.3}],0,1)[0]['start_s']==0


def test_acoustic_drafts_require_enough_sound_bursts(tmp_path):
    rate=16000;t=np.arange(rate*4)/rate
    def audio(centers):
        return sum(.1*np.sin(2*np.pi*220*t)*np.exp(-((t-c)/.06)**2) for c in centers).astype(np.float32)
    wavfile.write(tmp_path/'full.wav',rate,audio([.6,1.5,2.4]))
    a=analyze_audio(tmp_path/'full.wav')
    draft=acoustic_words('pa · ta ka',a,.3,4.4)
    assert len(draft)==3 and all(w['source']=='acoustic_estimate' for w in draft)
    assert draft[0]['start_s']<.9<draft[0]['end_s']
    wavfile.write(tmp_path/'partial.wav',rate,audio([.6,1.5]))
    assert acoustic_words('pa ta ka',analyze_audio(tmp_path/'partial.wav'),0,4)==[]


def test_control_review_has_no_transcript_or_word_annotations(tmp_path):
    store=Store(tmp_path);p=bundled_profile('usb-phase-20hz')
    s=store.create_session('control','test','simulator',p)
    t=store.save_trial(s['id'],'[rest]',np.arange(161)*50_000_000,np.ones((161,64,12)),np.arange(161),
        extra={'articulation':'rest','collection_protocol':'test','required_duration_s':8,'review_status':'pending','accepted':False})
    with TestClient(create_app(tmp_path)) as c:
        path=f"/api/sessions/{s['id']}/trials/{t['id']}"
        r=c.patch(path,json={'accepted':True,'words':[], 'confirmed_text':''})
        assert r.status_code==200,r.text
        assert r.json()['accepted'] and r.json()['words']==[] and r.json()['confirmed_text']==''
        assert r.json()['label']=='[rest]' and r.json()['sample_kind']=='control'
        assert c.post(path+'/suggest-timing',json={}).json()['words']==[]


def test_action_stop_is_checked_during_recording(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        c.post('/api/connect',json={'source':'simulator'})
        session=c.post('/api/collections/calibration/sessions',json={'setup':{'subject':'test','distance_cm':45}}).json()
        time.sleep(.2)
        rid=c.post('/api/collect',json={'step_id':session['collection']['plan']['steps'][0]['step_id']}).json()['id']
        time.sleep(.55)
        stopped=c.post('/api/record/'+rid+'/stop')
        assert stopped.status_code==400 and 'countdown' in stopped.text
        assert c.get('/api/record/'+rid).json()['status']=='recording'
        c.post('/api/record/'+rid+'/cancel')


def test_quality_detects_partial_syllable_audio_and_radar_gap(tmp_path):
    store=Store(tmp_path);p=bundled_profile('usb-phase-20hz');s=store.create_session('speech','test','serial',p)
    t=store.save_trial(s['id'],'pa pa pa · ta ta ta · ka ka ka',np.arange(101)*50_000_000,np.ones((101,64,12)),np.arange(101)+np.r_[np.zeros(50),np.ones(51)],extra={'articulation':'voiced','prompt_text':'pa pa pa · ta ta ta · ka ka ka','prompt_id':'plosives','target_text':'pa pa pa · ta ta ta · ka ka ka'})
    x=np.arange(16000*5)/16000
    audio=sum(.1*np.sin(2*np.pi*220*x)*np.exp(-((x-c)/.06)**2) for c in [.7,1.2]).astype(np.float32)
    wavfile.write(store.trial_dir(s['id'],t['id'])/'reference.wav',16000,audio)
    store.add_trial_fields(s['id'],t['id'],{'media':{'file':'reference.wav'}})
    q=inspect_take(store,s['id'],t['id'])
    assert {w['code'] for w in q['warnings']}=={'radar_gap','incomplete_reference'}
