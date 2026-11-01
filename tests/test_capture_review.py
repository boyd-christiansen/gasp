import time
import numpy as np
from scipy.io import wavfile
from fastapi.testclient import TestClient
from gasp.audio_review import analyze_audio, acoustic_words, propose_words, inspect_take, processing_window
from gasp.server import create_app
from gasp.storage import Store
from gasp.profile import bundled_profile
from gasp.collection import capture_mode, capture_limit
from gasp.journey import baseline_plan


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


def test_movement_release_can_be_reviewed_without_timed_minimum(tmp_path):
    app=create_app(tmp_path)
    with TestClient(app) as c:
        c.post('/api/connect',json={'source':'simulator'})
        session=c.post('/api/collections/calibration/sessions',json={'setup':{'subject':'test'}}).json()
        step=next(s for s in session['collection']['plan']['steps'] if s['prompt_id']=='jaw')
        time.sleep(.2)
        rid=c.post('/api/collect',json={'step_id':step['step_id'],'capture_method':'hold'}).json()['id']
        assert app.state.engine.recording['duration_s']==60
        time.sleep(.7)
        stopped=c.post('/api/record/'+rid+'/stop')
        assert stopped.status_code==200,stopped.text
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            result=c.get('/api/record/'+rid).json()
            if result['status'] in {'complete','failed'}:break
            time.sleep(.05)
        assert result['status']=='complete',result
        take=result['trial'];path=f"/api/sessions/{session['id']}/trials/{take['id']}"
        assert .5<take['capture_duration_s']<3 and take['required_duration_s'] is None
        assert 'too_short' not in {w['code'] for w in c.get(path+'/quality').json()['warnings']}
        review=c.patch(path,json={'accepted':True,'confirmed_text':'','words':[]})
        assert review.status_code==200,review.text
        progress=c.get('/api/journey',params={'subject':'test','source':'simulator','profile':session['profile']['sha256']}).json()['progress']
        assert progress['steps'][0]['verified']==1


def test_old_plans_infer_interaction_without_rewriting_them():
    steps=baseline_plan('calibration')['steps']
    for step in steps:
        legacy={k:v for k,v in step.items() if k!='capture_mode'}
        assert capture_mode(legacy)==('timed' if step['prompt_id']=='still' else 'hold')
        if step['articulation']=='negative':
            assert capture_limit(legacy)==60 and capture_limit(legacy,raw=True)==25


def test_continuous_and_quiet_but_audible_audio_are_not_called_missing(tmp_path):
    rate=16000;t=np.arange(rate*4)/rate
    store=Store(tmp_path);s=store.create_session('speech','test','serial',bundled_profile('usb-phase-20hz'))
    take=store.save_trial(s['id'],'a complete utterance',np.arange(81)*50_000_000,
        np.ones((81,64,12)),np.arange(81),extra={'articulation':'voiced'})
    path=store.trial_dir(s['id'],take['id'])/'reference.wav'
    store.add_trial_fields(s['id'],take['id'],{'media':{'file':'reference.wav'}})
    # Neither a full-window utterance nor a low-gain syllable sequence implies
    # that the microphone dropped words. The old percentile*4 gate rejected both.
    for envelope in [np.full_like(t,.02),.0015+sum(.004*np.exp(-((t-c)/.15)**2) for c in [.5,1,1.5,2,2.5,3])]:
        wavfile.write(path,rate,(envelope*np.sin(2*np.pi*220*t)).astype(np.float32))
        before=path.read_bytes()
        quality=inspect_take(store,s['id'],take['id'])
        assert 'quiet_audio' not in {w['code'] for w in quality['warnings']}
        assert path.read_bytes()==before  # Analysis must never gate the saved audio.
    wavfile.write(path,rate,np.zeros_like(t,dtype=np.float32))
    assert 'quiet_audio' in {w['code'] for w in inspect_take(store,s['id'],take['id'])['warnings']}


def test_quality_detects_partial_syllable_audio_and_radar_gap(tmp_path):
    store=Store(tmp_path);p=bundled_profile('usb-phase-20hz');s=store.create_session('speech','test','serial',p)
    t=store.save_trial(s['id'],'pa pa pa · ta ta ta · ka ka ka',np.arange(101)*50_000_000,np.ones((101,64,12)),np.arange(101)+np.r_[np.zeros(50),np.ones(51)],extra={'articulation':'voiced','prompt_text':'pa pa pa · ta ta ta · ka ka ka','prompt_id':'plosives','target_text':'pa pa pa · ta ta ta · ka ka ka'})
    x=np.arange(16000*5)/16000
    audio=sum(.1*np.sin(2*np.pi*220*x)*np.exp(-((x-c)/.06)**2) for c in [.7,1.2]).astype(np.float32)
    wavfile.write(store.trial_dir(s['id'],t['id'])/'reference.wav',16000,audio)
    store.add_trial_fields(s['id'],t['id'],{'media':{'file':'reference.wav'}})
    q=inspect_take(store,s['id'],t['id'])
    assert {w['code'] for w in q['warnings']}=={'radar_gap','incomplete_reference'}


def test_cue_is_excluded_before_peak_detection_and_recognition(tmp_path):
    import io
    rate=16000;t=np.arange(rate*5)/rate
    # A loud start cue must not displace the first of nine quieter syllables.
    centers=np.arange(9)*.4+1
    speech=sum(.03*np.sin(2*np.pi*220*t)*np.exp(-((t-c)/.05)**2) for c in centers)
    cue=.5*np.sin(2*np.pi*880*t)*np.exp(-((t-.3)/.04)**2)
    samples=(speech+cue).astype(np.float32)
    store=Store(tmp_path);s=store.create_session('cue test','test','serial',bundled_profile('usb-phase-20hz'))
    take=store.save_trial(s['id'],'pa pa pa · ta ta ta · ka ka ka',np.arange(101)*50_000_000,
        np.ones((101,64,12)),np.arange(101),extra={'articulation':'voiced','prompt_text':'pa pa pa · ta ta ta · ka ka ka'})
    path=store.trial_dir(s['id'],take['id'])/'reference.wav';wavfile.write(path,rate,samples)
    timing={'first_sample_host_ns':1_000_000_000,'processing_start_host_ns':1_700_000_000,'duration_s':5,'cue_protocol':'short-tone-v1'}
    store.add_trial_fields(s['id'],take['id'],{'media':{'file':'reference.wav','native_audio_timing':timing}})
    original=path.read_bytes()
    with TestClient(create_app(tmp_path)) as c:
        url=f"/api/sessions/{s['id']}/trials/{take['id']}"
        draft=c.post(url+'/suggest-timing',json={'text':take['label'],'audio_offset_s':.2}).json()['words']
        assert len(draft)==9 and all(w['start_s'] is not None for w in draft)
        assert draft[0]['start_s']<1.2<draft[0]['end_s']
        assert all(w['start_s']>=.9 for w in draft)
        processed=c.get(url+'/media?processing=true')
        assert processed.status_code==200 and float(processed.headers['X-Audio-Processing-Start-S'])==.7
        actual_rate,actual=wavfile.read(io.BytesIO(processed.content))
        assert actual_rate==rate and np.array_equal(actual,samples[11200:])
        assert c.get(url+'/media').content==original and path.read_bytes()==original
        # Recognition also ignores anchors inside the cue window; preserve text.
        result=c.post(url+'/suggest-timing',json={'text':'hello','recognized':[{'text':'hello','start':.3,'end':.4}]}).json()
        assert result['placed']==0
    wavfile.write(path,rate,cue.astype(np.float32))
    assert 'quiet_audio' in {w['code'] for w in inspect_take(store,s['id'],take['id'])['warnings']}


def test_legacy_cue_window_is_explicitly_an_estimate():
    take={'duration_s':4,'capture_events':[{'name':'cue_shown','estimated_server_ns':1_300_000_000}],
          'media':{'native_audio_timing':{'first_sample_host_ns':1_000_000_000}}}
    assert processing_window(take)=={'start_s':.7,'source':'legacy_pop_estimate'}
    take['media']['native_audio_timing']['cue_protocol']='short-tone-v1'
    assert processing_window(take)=={'start_s':0,'source':None}
