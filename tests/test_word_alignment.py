import hashlib

import numpy as np
import pytest
from scipy.io import wavfile
from fastapi.testclient import TestClient

from gasp import word_alignment as alignment
from gasp.profile import bundled_profile
from gasp.server import create_app
from gasp.storage import Store

VOCAB = {c: i for i, c in enumerate(['<pad>', '|', *"ABCDEFGHIJKLMNOPQRSTUVWXYZ'"])}


def spoken(text, leading=15):
    words, tokens, owners = alignment.transcript_tokens(text, VOCAB)
    labels = [0] * leading
    for token in tokens:
        labels.extend([int(token)] * 3 + [0])
    labels += [0] * 10
    logp = np.full((len(labels), len(VOCAB)), -15.)
    logp[np.arange(len(labels)), labels] = 0
    return logp, np.arange(len(labels)) * .02 + .5, VOCAB, len(labels) * .02


def test_ctc_repeated_characters_and_words():
    logp, _, _, _ = spoken('BOOK BOOK')
    _, tokens, _ = alignment.transcript_tokens('BOOK BOOK', VOCAB)
    path = alignment.ctc_path(logp, tokens)
    assert set(np.arange(1, 2 * len(tokens), 2)).issubset(path)
    assert np.all(np.diff(path) >= 0)
    with pytest.raises(alignment.AlignmentError, match='too long'):
        alignment.ctc_path(logp[:2], tokens)


def test_alignment_offsets_cue_and_original_word_spelling(monkeypatch):
    text = 'Please put the blue mug beside my keyboard.'
    monkeypatch.setattr(alignment, 'emissions', lambda *_: spoken(text))
    result = alignment.align_reference('unused.wav', text, .5, -.1, 10)
    assert [w['text'] for w in result] == text.split()
    assert all(w['source'] == 'forced_alignment' and .4 <= w['start_s'] < w['end_s'] <= 10 for w in result)
    assert all(a['end_s'] <= b['start_s'] for a, b in zip(result, result[1:]))
    assert result[0]['start_s'] > .5  # Leading silence is not spread across words.


def test_mismatched_audio_does_not_fabricate_boundaries(monkeypatch):
    monkeypatch.setattr(alignment, 'emissions', lambda *_: spoken('HELLO'))
    with pytest.raises(alignment.AlignmentError, match='does not match'):
        alignment.align_reference('unused.wav', 'The elephant is walking through a field.', 0, 0, 10)
    monkeypatch.setattr(alignment, 'emissions', lambda *_: spoken('A'))
    with pytest.raises(alignment.AlignmentError, match='do not overlap'):
        alignment.align_reference('unused.wav', 'A', 0, 20, 10)


def test_tokenization_preserves_numbers_and_punctuation():
    words, tokens, owners = alignment.transcript_tokens('5 small packages, don’t stop.', VOCAB)
    inverse = {i: c for c, i in VOCAB.items()}
    assert words == ['5', 'small', 'packages,', 'don’t', 'stop.']
    assert ''.join(inverse[t] for t in tokens) == "FIVE|SMALL|PACKAGES|DON'T|STOP"
    assert set(owners) == {-1, 0, 1, 2, 3, 4}
    with pytest.raises(alignment.AlignmentError):
        alignment.transcript_tokens('你好', VOCAB)


def test_audio_read_excludes_cue_keeps_stereo_signal_and_original(tmp_path):
    path = tmp_path/'reference.wav'
    signal = np.sin(np.arange(48000)*.1).astype(np.float32)*.1
    wavfile.write(path, 48000, np.column_stack([signal, -signal]))
    original = path.read_bytes()
    audio, origin = alignment.read_reference(path, .4)
    assert origin == .4 and len(audio) == 9600 and abs(audio).max() > .05
    assert path.read_bytes() == original
    wavfile.write(path, 16000, np.zeros(16000, dtype=np.int16))
    with pytest.raises(alignment.AlignmentError, match='too little audible'):
        alignment.read_reference(path, 0)


def test_windowed_inference_has_monotonic_audio_clock(monkeypatch, tmp_path):
    calls = []
    class Model:
        def get_inputs(self): return []
        def run(self, _, inputs):
            samples = inputs['input_values']
            calls.append(samples.shape[1])
            return [np.zeros((1, (samples.shape[1]-400)//320+1, len(VOCAB)))]
    path = tmp_path/'long.wav'
    wavfile.write(path, 16000, (.01*np.sin(np.arange(16000*42)*.1)).astype(np.float32))
    monkeypatch.setattr(alignment, 'load_model', lambda *_: (Model(), VOCAB))
    logp, clock, _, _ = alignment.emissions(path, .3)
    assert len(calls) == 3 and max(calls) <= 22*16000
    assert len(logp) == len(clock) and clock[0] >= .3 and clock[-1] < 42
    assert np.all(np.diff(clock) > 0) and np.max(np.diff(clock)) < .041


def test_model_missing_or_corrupt_is_actionable(tmp_path):
    with pytest.raises(alignment.AlignmentUnavailable, match='missing'):
        alignment.load_model(str(tmp_path))
    (tmp_path/'model-uint8.onnx').write_bytes(b'bad')
    with pytest.raises(alignment.AlignmentUnavailable, match='damaged'):
        alignment.load_model(str(tmp_path))


@pytest.mark.parametrize('a,b,expected', [('kitten','sitting',3), ('','abc',3), ('abc','',3), ('BOOK','BOOK',0), ('BOOK','BOOOK',1), ('ABAB','BABA',2)])
def test_edit_distance(a, b, expected):
    assert alignment.edit_distance(a, b) == expected


def test_endpoint_aligns_locally_without_mutating_take(monkeypatch, tmp_path):
    store = Store(tmp_path)
    session = store.create_session('Alignment', 'test', 'simulator', bundled_profile('usb-phase-20hz'))
    text = 'Please put the blue mug beside my keyboard.'
    take = store.save_trial(session['id'], text, np.arange(201)*50_000_000, np.ones((201,64,12)), np.arange(201),
                            extra=dict(articulation='voiced', accepted=False, target_text=text, prompt_id='sentence1'))
    folder = store.trial_dir(session['id'], take['id'])
    wavfile.write(folder/'reference.wav', 16000, np.ones(16000, dtype=np.float32)*.01)
    store.add_trial_fields(session['id'], take['id'], {'media': {'file': 'reference.wav'}})
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
    monkeypatch.setattr(alignment, 'emissions', lambda *_: spoken(text))
    with TestClient(create_app(tmp_path)) as client:
        url = f"/api/sessions/{session['id']}/trials/{take['id']}/suggest-timing"
        result = client.post(url, json={'text': text}).json()
        assert result['placed'] == 8 and not result['recognition_allowed']
        assert all(w['source'] == 'forced_alignment' for w in result['words'])
        monkeypatch.setattr(alignment, 'emissions', lambda *_: (_ for _ in ()).throw(alignment.AlignmentUnavailable('Model missing')))
        failure = client.post(url, json={'text': text}).json()
        assert failure['placed'] == 0 and failure['message'] == 'Model missing'
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
