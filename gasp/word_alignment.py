"""Offline English transcript alignment. Suggestions never verify a take.

Wav2Vec2 supplies acoustic character probabilities; a CTC Viterbi path aligns
the supplied transcript. This does not use Siri, a language-model transcript,
or evenly spaced word boundaries. Original audio is never modified.
"""
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import threading
import unicodedata
import warnings

import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly
from scipy.special import log_softmax

from .audio_review import speech_tokens

SAMPLE_RATE = 16000
_inference_lock = threading.Lock()


class AlignmentError(ValueError):
    """The reference needs attention rather than invented word boundaries."""


class AlignmentUnavailable(AlignmentError):
    pass


def model_directory():
    if os.environ.get('GASP_ALIGNMENT_MODEL'):
        return Path(os.environ['GASP_ALIGNMENT_MODEL'])
    bundled = Path(__file__).parent / 'models' / 'alignment-en'
    if bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parents[1] / '.cache' / 'alignment-en'


@lru_cache(maxsize=1)
def load_model(directory):
    root = Path(directory)
    manifest = json.loads(Path(__file__).with_name('alignment_model.json').read_text())
    for name, item in manifest['files'].items():
        path = root / name
        if not path.is_file():
            raise AlignmentUnavailable('The local word-timing model is missing. Reinstall Gasp to restore it.')
        if path.stat().st_size != item['bytes'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise AlignmentUnavailable('The local word-timing model is damaged. Reinstall Gasp to restore it.')
    try:
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.intra_op_num_threads = min(4, os.cpu_count() or 1)
        options.inter_op_num_threads = 1
        session = ort.InferenceSession(str(root / manifest['model_file']), options,
                                       providers=['CPUExecutionProvider'])
    except Exception as exc:
        raise AlignmentUnavailable('The local word-timing engine could not start. Reinstall Gasp to restore it.') from exc
    return session, json.loads((root / 'vocab.json').read_text())


def read_reference(path, start_s):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', wavfile.WavFileWarning)
            rate, samples = wavfile.read(path)
    except (OSError, ValueError) as exc:
        raise AlignmentError('The reference audio could not be read. Restore the WAV reference and retry.') from exc
    if rate <= 0 or samples.ndim not in (1, 2) or not len(samples):
        raise AlignmentError('The reference audio could not be read.')
    if len(samples) / rate > 185:
        raise AlignmentError('Split this recording into passages of three minutes or less for word timing.')
    if samples.dtype.kind in 'iu':
        info = np.iinfo(samples.dtype)
        samples = (samples.astype(np.float32) - (128 if info.bits == 8 else 0)) / max(abs(info.min), info.max)
    else:
        samples = samples.astype(np.float32)
    if not np.isfinite(samples).all():
        raise AlignmentError('The reference contains invalid audio samples.')
    if samples.ndim == 2:
        samples = samples[:, np.argmax(np.mean(samples * samples, axis=0))]
    first = max(0, int(math.ceil(start_s * rate)))
    samples = samples[first:]
    if len(samples) < rate * .1 or np.max(np.abs(samples), initial=0) < .0001:
        raise AlignmentError('There is too little audible audio after the start cue to place words.')
    divisor = math.gcd(rate, SAMPLE_RATE)
    samples = resample_poly(samples, SAMPLE_RATE // divisor, rate // divisor).astype(np.float32)
    return samples, first / rate


@lru_cache(maxsize=8)
def _cached_emissions(path, modified_ns, size, start_s, directory):
    # File identity and exclusion window are part of the cache key. Transcript
    # edits reuse acoustic work; replacing audio or changing the cue does not.
    with _inference_lock:
        session, vocab = load_model(directory)
        samples, origin = read_reference(path, start_s)
        duration = len(samples) / SAMPLE_RATE
        outputs, clocks = [], []
        for begin in range(0, len(samples), SAMPLE_RATE * 20):
            end = min(len(samples), begin + SAMPLE_RATE * 20)
            lo, hi = max(0, begin - SAMPLE_RATE), min(len(samples), end + SAMPLE_RATE)
            chunk = samples[lo:hi]
            chunk = (chunk - chunk.mean()) / np.sqrt(chunk.var() + 1e-7)
            inputs = {'input_values': chunk[None, :].astype(np.float32)}
            if any(item.name == 'attention_mask' for item in session.get_inputs()):
                inputs['attention_mask'] = np.ones((1, len(chunk)), dtype=np.int64)
            try:
                logits = session.run(None, inputs)[0][0]
            except Exception as exc:
                raise AlignmentUnavailable('The local word-timing engine could not process this audio. Reopen Gasp and retry.') from exc
            # The pinned model has a 400-sample receptive field and 320-sample stride.
            clock = (lo + np.arange(len(logits)) * 320 + 200) / SAMPLE_RATE
            keep = (clock >= begin / SAMPLE_RATE) & (clock < end / SAMPLE_RATE)
            outputs.append(logits[keep]); clocks.append(clock[keep] + origin)
        return log_softmax(np.concatenate(outputs), axis=-1), np.concatenate(clocks), vocab, duration


def emissions(path, start_s):
    path = Path(path).resolve()
    stat = path.stat()
    return _cached_emissions(str(path), stat.st_mtime_ns, stat.st_size, float(start_s), str(model_directory()))


_SMALL = 'ZERO ONE TWO THREE FOUR FIVE SIX SEVEN EIGHT NINE TEN ELEVEN TWELVE THIRTEEN FOURTEEN FIFTEEN SIXTEEN SEVENTEEN EIGHTEEN NINETEEN'.split()
_TENS = ['', '', 'TWENTY', 'THIRTY', 'FORTY', 'FIFTY', 'SIXTY', 'SEVENTY', 'EIGHTY', 'NINETY']


def number_text(value):
    if value < 20: return _SMALL[value]
    if value < 100: return _TENS[value // 10] + (' ' + number_text(value % 10) if value % 10 else '')
    if value < 1000: return _SMALL[value // 100] + ' HUNDRED' + (' ' + number_text(value % 100) if value % 100 else '')
    if value < 10000: return number_text(value // 1000) + ' THOUSAND' + (' ' + number_text(value % 1000) if value % 1000 else '')
    return ' '.join(_SMALL[int(c)] for c in str(value))


def transcript_tokens(text, vocab):
    import re
    words = speech_tokens(text)
    tokens, owners = [], []
    for index, word in enumerate(words):
        normalized = unicodedata.normalize('NFKD', word.replace('’', "'")).encode('ascii', 'ignore').decode().upper()
        normalized = re.sub(r'\d+', lambda match: number_text(int(match[0])) if len(match[0]) < 5
                            else ' '.join(_SMALL[int(c)] for c in match[0]), normalized)
        normalized = re.sub(r"[^A-Z' ]", '', normalized).strip(" '")
        if not normalized:
            raise AlignmentError('Automatic word timing currently supports English words and numbers. Check the transcript and retry.')
        if tokens:
            tokens.append(vocab['|']); owners.append(-1)
        for character in normalized.replace(' ', '|'):
            tokens.append(vocab[character]); owners.append(index)
    if not tokens:
        raise AlignmentError('Add the spoken text before placing words.')
    return words, np.asarray(tokens), np.asarray(owners)


def ctc_path(log_probabilities, tokens, blank=0):
    """Full CTC path: blanks and repeated labels retain their proper states."""
    frames, _ = log_probabilities.shape
    labels = np.full(len(tokens) * 2 + 1, blank, dtype=np.int64)
    labels[1::2] = tokens
    if frames * len(labels) > 50_000_000:
        raise AlignmentError('This passage is too long for word timing. Split it into shorter recordings.')
    minimum = len(tokens) + int(np.sum(tokens[1:] == tokens[:-1]))
    if minimum > frames:
        raise AlignmentError('The transcript is too long for this audio. Check the spoken text and retry.')
    skip = np.zeros(len(labels), dtype=bool)
    skip[2:] = (labels[2:] != blank) & (labels[2:] != labels[:-2])
    scores = np.full(len(labels), -np.inf); scores[0] = 0
    previous = np.zeros((frames, len(labels)), dtype=np.uint8)
    for t, row in enumerate(log_probabilities):
        best = scores.copy()
        advance = scores[:-1] > best[1:]
        best[1:] = np.maximum(best[1:], scores[:-1])
        previous[t, 1:] = advance.astype(np.uint8)
        jump = skip[2:] & (scores[:-2] > best[2:])
        best[2:] = np.where(jump, scores[:-2], best[2:])
        previous[t, 2:] = np.where(jump, 2, previous[t, 2:])
        scores = best + row[labels]
    state = len(labels) - (1 if scores[-1] >= scores[-2] else 2)
    if not np.isfinite(scores[state]):
        raise AlignmentError('The words could not be matched to this audio. Check the transcript and retry.')
    path = np.empty(frames, dtype=np.int32)
    for t in range(frames - 1, -1, -1):
        path[t] = state
        state -= int(previous[t, state])
    return path


def edit_distance(a, b):
    # Myers' bit-vector distance avoids a quadratic Python loop for passages.
    if not a: return len(b)
    masks = {}
    for i, character in enumerate(a):
        masks[character] = masks.get(character, 0) | (1 << i)
    positive, negative, distance, top = ~0, 0, len(a), 1 << (len(a)-1)
    for character in b:
        equal = masks.get(character, 0)
        vertical = equal | negative
        horizontal = (((equal & positive) + positive) ^ positive) | equal
        plus = negative | ~(horizontal | positive)
        minus = positive & horizontal
        distance += bool(plus & top) - bool(minus & top)
        plus = (plus << 1) | 1
        positive = (minus << 1) | ~(vertical | plus)
        negative = vertical & plus
    return distance


def align_reference(path, text, start_s, offset, duration):
    logp, clock, vocab, _ = emissions(path, start_s)
    words, tokens, owners = transcript_tokens(text, vocab)
    inverse = {i: c for c, i in vocab.items()}
    greedy = logp.argmax(axis=1)
    recognized = ''.join(inverse[int(token)] for i, token in enumerate(greedy)
                         if token and (i == 0 or token != greedy[i-1]))
    target = ''.join(inverse[int(token)] for token in tokens)
    if not recognized or edit_distance(target, recognized) / max(1, len(target)) > .65:
        raise AlignmentError('The audio does not match enough of this transcript to place words reliably. Listen, correct the text if needed, then retry.')
    states = ctc_path(logp, tokens, vocab['<pad>'])
    bounds = []
    for index, word in enumerate(words):
        token_indices = np.flatnonzero(owners == index)
        frames = np.flatnonzero(np.isin(states, token_indices * 2 + 1))
        if not len(frames):
            raise AlignmentError('Some words could not be matched. Check the transcript and retry.')
        lo = max(start_s, float(clock[frames[0]]) - .03)
        hi = float(clock[frames[-1]]) + .03
        bounds.append([lo, hi])
    for left, right in zip(bounds, bounds[1:]):
        if left[1] > right[0]:
            left[1] = right[0] = (left[1] + right[0]) / 2
    result = []
    for word, (lo, hi) in zip(words, bounds):
        lo, hi = max(0, lo + offset), min(duration, hi + offset)
        if hi <= lo:
            raise AlignmentError('Audio and radar timing do not overlap for every word. Check the audio offset.')
        result.append(dict(text=word, start_s=round(lo, 4), end_s=round(hi, 4), source='forced_alignment'))
    return result
