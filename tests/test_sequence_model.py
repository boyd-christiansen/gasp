"""Small CPU-only model checks. Generated signals are not speech evidence."""
import json
import numpy as np
import pytest

from gasp.learning_data import digest
from gasp.learning_models import fit, evaluate, validate_weights
from gasp.sequence_model import minimum_ctc_frames, targets, sequence_features
from gasp.storage import Store
from gasp.profile import bundled_profile


def fixture(tmp_path,epochs=2):
    store=Store(tmp_path);profile=bundled_profile();rows=[]
    for group,split in enumerate(['train','validation']):
        session=store.create_session('Sequence fixture','test','simulator',profile)
        for repeat in range(4 if group==0 else 1):
            for i,label in enumerate(['a','b']):
                # Opposite phase ramps are deliberately easy to distinguish.
                stamps=np.arange(12,dtype=np.int64)*50_000_000+1
                phase=np.arange(12)*(.6 if i else -.6)
                values=np.broadcast_to(100*np.exp(1j*phase[:,None,None]),(12,64,12)).copy()
                values+=np.random.default_rng(group*20+repeat*2+i).normal(0,.1,values.shape)
                t=store.save_trial(session['id'],label,stamps,values,np.arange(12))
                rows.append(dict(session_id=session['id'],trial_id=t['id'],text=label,split=split,
                    annotation_revision=1,articulation='silent',control=False,acquisition_id=session['id'],
                    shape=t['shape'],profile=profile.summary(),start_s=0,end_s=t['duration_s'],
                    signal_sha256=t['sha256'],path=f"sessions/{session['id']}/trials/{t['id']}/radar.npz"))
    from gasp.learning_data import RECIPES
    recipe={**RECIPES['radar-ctc-v1'],'hidden_size':8,'epochs':epochs,'batch_size':4,'learning_rate':.01}
    return dict(task='sentences',recipe=recipe,rows=rows),store


def test_time_preservation_and_ctc_repeated_symbols(tmp_path):
    snapshot,store=fixture(tmp_path)
    x=sequence_features(tmp_path,snapshot['rows'][0],snapshot['recipe'])
    assert x.shape==(12,577) and np.isfinite(x).all()
    assert minimum_ctc_frames(targets('book'))==5
    assert minimum_ctc_frames(targets('ab'))==2


def test_ctc_fit_reload_resume_and_invalid_alignment(tmp_path):
    pytest.importorskip('torch')
    snapshot,store=fixture(tmp_path)
    out=tmp_path/'model'
    result=fit(snapshot,tmp_path,out)
    assert result['development']['metrics']['n']==2
    config=json.loads((out/'model.json').read_text())
    validate_weights(config,(out/'model.npz').read_bytes(),snapshot['rows'])
    first=evaluate(snapshot,tmp_path,out,'validation',lambda *a,**k:None,lambda:None)
    # An already-complete epoch checkpoint must reload without changing inference.
    resumed=fit(snapshot,tmp_path,out)
    assert resumed['model_sha256']==result['model_sha256']
    assert resumed['development']==first
    bad={**snapshot,'rows':[dict(snapshot['rows'][0],text='far more letters than measured frames')]}
    with pytest.raises(ValueError,match='Not enough measured frames'):
        fit(bad,tmp_path,tmp_path/'bad-model')


def test_tiny_overfit_distinguishes_two_phase_patterns(tmp_path):
    pytest.importorskip('torch')
    snapshot,_=fixture(tmp_path,epochs=320)
    snapshot['recipe'].update(hidden_size=16, learning_rate=.003)
    result=fit(snapshot,tmp_path,tmp_path/'model')
    assert result['development']['metrics']['wer']==0, result


def test_padding_cannot_change_short_take_predictions():
    torch=pytest.importorskip('torch')
    from gasp.sequence_model import network, batch
    torch.manual_seed(17)
    model=network(torch,4,8).eval()
    rng=np.random.default_rng(17)
    short=rng.normal(size=(8,4)).astype(np.float32)
    long=rng.normal(size=(30,4)).astype(np.float32)
    with torch.no_grad():
        alone=model(*batch(torch,[short],torch.device('cpu')))[0]
        together=model(*batch(torch,[short,long],torch.device('cpu')))[0,:8]
    torch.testing.assert_close(alone,together,rtol=1e-5,atol=1e-6)
