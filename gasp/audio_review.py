"""Local, non-destructive audio checks and draft annotation assistance.

Acoustic suggestions are NOT forced alignment. Recognition anchors must match the
script; isolated syllable suggestions need enough distinct acoustic peaks.
"""
import json
import re
import warnings
import numpy as np
from .collection import capture_mode
from .replay import radar_gaps
from scipy.io import wavfile
from scipy.ndimage import uniform_filter1d, binary_closing, binary_opening
from scipy.signal import find_peaks


def speech_tokens(text):
    return [t for t in text.split() if re.search(r"\w", t)]


def is_control(take):
    return take.get("articulation") in {"rest", "negative"}


def is_syllable_exercise(take):
    return take.get('prompt_id') in {'stops', 'plosives', 'nasals', 'fricatives', 'vowels'} or '·' in take.get('prompt_text', '')


def processing_window(take):
    """Audio-relative exclusion; never changes the original WAV or radar clock."""
    timing = (take.get('media') or {}).get('native_audio_timing') or {}
    first = timing.get('first_sample_host_ns')
    end = timing.get('processing_start_host_ns')
    source = 'cue_completion' if end else None
    if first and not end and not timing.get('cue_protocol'):
        cue = next((e for e in take.get('capture_events', []) if e['name']=='cue_shown'), None)
        if cue:
            # Older builds played macOS Pop without recording its completion.
            # Its audible portion is ~210 ms; allow output latency and decay.
            end = cue['estimated_server_ns'] + 400_000_000
            source = 'legacy_pop_estimate'
    start = max(0, (end-first)/1e9) if first and end else 0
    return dict(start_s=min(start, timing.get('duration_s', take['duration_s'])), source=source)


def analyze_audio(path, start_s=0):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", wavfile.WavFileWarning)
        rate, x = wavfile.read(path)
    if x.dtype.kind in "iu":
        bits = np.iinfo(x.dtype)
        x = (x.astype(np.float64) - (128 if x.dtype == np.uint8 else 0)) / max(abs(bits.min), bits.max)
    else:
        x = x.astype(np.float64)
    if x.ndim > 1:
        # Use the channel with most signal; opposite-polarity stereo must not cancel.
        x = x[:, np.argmax(np.mean(x*x, axis=0))]
    if rate <= 0 or not len(x) or not np.isfinite(x).all():
        raise ValueError("Invalid reference audio")
    size = max(1, round(rate * .01))
    padded = np.pad(x, (0, (-len(x)) % size)).reshape(-1, size)
    rms = np.sqrt(np.mean(padded*padded, axis=1))
    envelope = uniform_filter1d(rms, 3)
    start_frame = min(len(x), max(0, int(np.ceil(start_s*rate))))
    signal = x[start_frame:]
    # Exclude the cue before threshold/peak estimation, not after detecting it.
    # Leave the time axis intact so suggestions stay in original audio time.
    first_bin = min(len(envelope), max(0, int(np.ceil(start_s/.01))))
    envelope[:first_bin] = 0
    tail = envelope[first_bin:]
    peak = float(np.max(np.abs(signal))) if len(signal) else 0
    # A continuous utterance can occupy the entire window: its quiet percentile
    # is not necessarily background noise. Never set the gate above the signal.
    threshold = max(.0003, min(float(np.percentile(tail, 20))*2,
                              float(tail.max())*.2)) if len(tail) else .0003
    active = binary_opening(binary_closing(envelope > threshold, structure=np.ones(3)), structure=np.ones(3))
    edges = np.diff(np.r_[False, active, False].astype(int))
    regions = [[max(start_s, int(a)*.01-.02), min(len(x)/rate, int(b)*.01+.02)]
               for a,b in zip(np.where(edges == 1)[0], np.where(edges == -1)[0]) if b-a >= 5]
    peaks, _ = find_peaks(envelope, distance=12, prominence=max(threshold, float(envelope.max())*.10))
    peaks = [int(p) for p in peaks if active[p]]
    return dict(duration_s=len(x)/rate, sample_rate_hz=int(rate), peak=peak,
                clipped_fraction=float(np.mean(abs(signal)>=.995)) if len(signal) else 0, active_s=float(active.sum()*.01),
                audible_s=float(np.sum(envelope > .001)*.01),
                regions=regions, peaks_s=[p*.01 for p in peaks], peak_strengths=[float(envelope[p]) for p in peaks],
                processing_start_s=start_s, envelope=envelope.tolist())


def inspect_take(store, sid, tid):
    path = store.trial_dir(sid, tid)
    take = json.loads((path/'trial.json').read_text())
    result = {'kind':'control' if is_control(take) else 'speech', 'warnings':[], 'audio':None, 'radar_gaps':[],
              'processing_window':processing_window(take)}
    if take.get('frame_gaps'):
        # Read only timing/sequence arrays, not the potentially large I/Q cube.
        with np.load(path/'radar.npz', allow_pickle=False) as signal:
            result['radar_gaps'] = radar_gaps(signal['frame_numbers'], signal['timestamps_ns'])
        count = take['frame_gaps']
        profile = store.session(sid)['profile']
        unit = 'sample' if profile.get('lvds_adc') else 'frame'
        estimate = f" (about {count/profile['frame_hz']*1000:.0f} ms)" if not profile.get('lvds_adc') and profile.get('frame_hz',0)>0 else ''
        result['warnings'].append({'code':'radar_gap','message':f"{count} radar {unit}{'' if count==1 else 's'} missing{estimate}."})
    planned = take.get('required_duration_s') if capture_mode(take) == 'timed' else None
    if capture_mode(take) == 'timed' and not planned:
        steps=store.session(sid).get('collection',{}).get('plan',{}).get('steps',[])
        planned=next((s['duration_s'] for s in steps if s['step_id']==take.get('plan_step_id')),None)
    duration = take.get('capture_duration_s', take['duration_s'])
    if is_control(take) and planned and duration < .8*planned:
        result['warnings'].append({'code':'too_short','message':f"Recorded {duration:.1f} s; this timed reference needs {planned:g} s. Record it again."})
    media = take.get('media')
    if not media:
        if take.get('reference_expected') and not take.get('synthetic'):
            result['warnings'].append({'code':'missing_audio','message':'The microphone reference was not saved. Record this take again.'})
        return result
    timing = media.get('native_audio_timing') or {}
    if timing.get('sample_discontinuities', 0):
        result['warnings'].append({'code':'audio_gap','message':'The microphone stream was interrupted. Listen before keeping this take.'})
    if timing.get('microphone_mode') == 'voice_isolation':
        result['warnings'].append({'code':'voice_isolation','message':'macOS Voice Isolation was active. Use Standard microphone mode for syllable capture.'})
    if not media['file'].endswith('.wav'):
        return result
    try:
        a = analyze_audio(path/media['file'], result['processing_window']['start_s'])
    except (ValueError, OSError) as exc:
        result['warnings'].append({'code':'unreadable_audio','message':f'Cannot inspect reference audio: {exc}'})
        return result
    result['audio'] = {k:v for k,v in a.items() if k != 'envelope'}
    if not is_control(take) and take.get('articulation') in {'voiced','whisper'}:
        tokens = speech_tokens(take.get('target_text') or take.get('label',''))
        phonetic = is_syllable_exercise(take)
        if a['audible_s'] < .18:
            result['warnings'].append({'code':'quiet_audio','message':'The microphone level is very low. Listen to check that the full prompt is audible; this level check cannot tell whether speech is missing.'})
        elif phonetic and len(a['peaks_s']) < max(2, len(tokens)*.5):
            result['warnings'].append({'code':'incomplete_reference','message':f"Automatic timing found {len(a['peaks_s'])} distinct sound peaks for {len(tokens)} prompted sounds. Sounds can blend together; listen to check the take before continuing."})
        if a['clipped_fraction'] > .005:
            result['warnings'].append({'code':'clipping','message':'Reference audio is clipping. Lower the microphone input level and record again.'})
    return result


def propose_words(text, recognized, offset, duration):
    """Match only recognized words in order; never replace the reviewed transcript."""
    tokens = speech_tokens(text)
    normal = lambda s: re.sub(r'[^\w]', '', s.casefold())
    reference = [normal(s) for s in tokens]
    hypotheses = [normal(w.get('text', w.get('word',''))) for w in recognized]
    # LCS tolerates insertions/deletions and preserves repeated-word order.
    if len(tokens)*len(recognized) > 4_000_000:
        raise ValueError('Align a shorter passage')
    dp = np.zeros((len(tokens)+1, len(recognized)+1), dtype=np.int32)
    for i in range(len(tokens)-1,-1,-1):
        for j in range(len(recognized)-1,-1,-1):
            dp[i,j] = 1+dp[i+1,j+1] if reference[i] == hypotheses[j] else max(dp[i+1,j],dp[i,j+1])
    out = [dict(text=t,start_s=None,end_s=None,source='manual') for t in tokens]
    i=j=0; end=0
    while i<len(tokens) and j<len(recognized):
        if reference[i] == hypotheses[j]:
            w=recognized[j]
            a=max(0, float(w.get('start_s',w.get('start',0)))+offset)
            b=min(duration, float(w.get('end_s',w.get('end',0)))+offset)
            if np.isfinite(a) and np.isfinite(b) and a>=end and b>a:
                out[i].update(start_s=a,end_s=b,source='speech_estimate');end=b
            i+=1;j+=1
        elif dp[i+1,j] >= dp[i,j+1]: i+=1
        else: j+=1
    return out


def acoustic_words(text, audio, offset, duration, group_text=None):
    """Draft isolated sounds from audible regions, never from a forced count.

    The permissive quality-check gate deliberately includes quiet audio. It is
    unsuitable for annotation: fan/mic noise then looks like extra syllables.
    Use a separate noise-relative gate here, leaving the WAV and QC untouched.
    No recognition is implied; the user must confirm the sounds and their order.
    """
    tokens = speech_tokens(text)
    envelope = np.asarray(audio['envelope'])
    start = audio.get('processing_start_s', 0)
    tail = envelope[int(np.ceil(start * 100)):]
    if not tokens or not len(tail):
        return []
    noise = float(np.percentile(tail, 20))
    threshold = max(.0003, noise * 1.75, float(tail.max()) * .025)
    active = binary_opening(binary_closing(envelope > threshold, structure=np.ones(5)), structure=np.ones(7))
    edges = np.diff(np.r_[False, active, False].astype(int))
    regions = list(zip(np.where(edges == 1)[0], np.where(edges == -1)[0]))
    groups = [speech_tokens(g) for g in (group_text or text).split('·')]
    # Keep original grouping after the editor removes separators, but never
    # apply a recipe to a changed transcript.
    if [t.casefold() for g in groups for t in g] != [t.casefold() for t in tokens]:
        groups = []
    if len(regions) == len(tokens):
        bounds = regions
    elif len(groups) > 1 and len(regions) == len(groups) and all(groups):
        bounds = []
        for group, (a, b) in zip(groups, regions):
            peaks, _ = find_peaks(envelope[a:b], distance=18,
                prominence=max(noise * .6, float(envelope[a:b].max()) * .08), height=threshold)
            if len(peaks) != len(group):
                return []
            peaks = peaks + a
            cuts = [a] + [int(lo + np.argmin(envelope[lo:hi+1])) for lo, hi in zip(peaks, peaks[1:])] + [b]
            bounds.extend(zip(cuts, cuts[1:]))
    else:
        # Do not discard extra bursts or invent missing sounds to fit the script.
        return []
    result = []
    for i, (a, b) in enumerate(bounds):
        lo = max(start, a * .01 - .02)
        hi = min(audio['duration_s'], b * .01 + .02)
        if i: lo = max(lo, (bounds[i-1][1] + a) * .005)
        if i+1 < len(bounds): hi = min(hi, (b + bounds[i+1][0]) * .005)
        lo, hi = max(0, lo + offset), min(duration, hi + offset)
        if hi <= lo:
            return []
        result.append(dict(text=tokens[i], start_s=lo, end_s=hi, source='acoustic_estimate'))
    return result
