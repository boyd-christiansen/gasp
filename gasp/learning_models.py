"""Versioned training/evaluation recipes. Inference receives radar, never labels."""
from collections import Counter
import io
import json
from pathlib import Path

import numpy as np
from scipy.special import expit, logsumexp, log_expit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .features import FeatureSpec, features
from .learning_data import file_hash, normalize_text, signal
from .storage import atomic_json


class Cancelled(Exception):
    pass


def edit_counts(expected, predicted):
    """Levenshtein counts with deterministic ties, for words or characters."""
    previous = [(i, 0, i, 0) for i in range(len(predicted) + 1)]
    for i, ref in enumerate(expected, 1):
        current = [(i, 0, 0, i)]
        for j, hyp in enumerate(predicted, 1):
            cost, sub, ins, deletion = previous[j-1]
            diagonal = (cost + (ref != hyp), sub + (ref != hyp), ins, deletion)
            cost, sub, ins, deletion = current[-1]
            insertion = (cost+1, sub, ins+1, deletion)
            cost, sub, ins, deletion = previous[j]
            removal = (cost+1, sub, ins, deletion+1)
            current.append(min((diagonal, insertion, removal), key=lambda item: item[0]))
        previous = current
    _, substitutions, insertions, deletions = previous[-1]
    return dict(substitutions=int(substitutions), insertions=int(insertions), deletions=int(deletions))


def metrics(task, predictions, classes=()):
    if not predictions:
        return None
    if task == "phrases":
        expected, actual = [r["expected"] for r in predictions], [r["predicted"] for r in predictions]
        labels = sorted(set(classes) | set(expected))
        return dict(n=len(expected), accuracy=float(accuracy_score(expected, actual)),
            macro_f1=float(f1_score(expected, actual, labels=labels, average="macro", zero_division=0)),
            majority_baseline=max(Counter(expected).values()) / len(expected),
            labels=labels, confusion_matrix=confusion_matrix(expected, actual, labels=labels).tolist())
    totals = Counter(); chars = 0; word_count = 0; char_count = 0
    for row in predictions:
        ref, hyp = normalize_text(row["expected"]), normalize_text(row["predicted"])
        counts = edit_counts(ref.split(), hyp.split())
        row.update(counts, errors=sum(counts.values()), reference_words=len(ref.split()))
        totals.update(counts)
        chars += sum(edit_counts(list(ref), list(hyp)).values())
        word_count += len(ref.split()); char_count += len(ref)
    return dict(n=len(predictions), wer=sum(totals.values())/max(1, word_count),
        cer=chars/max(1, char_count), reference_words=word_count, reference_characters=char_count, **totals)


def report(task, rows, hypotheses, split, classes=()):
    predictions = [dict(session_id=r["session_id"], trial_id=r["trial_id"],
        annotation_revision=r["annotation_revision"], acquisition_id=r["acquisition_id"],
        expected=r["text"], predicted=str(h), correct=(normalize_text(r["text"]) == normalize_text(str(h))
            if task == "sentences" else r["text"] == str(h)), control=r["control"],
        articulation=r["articulation"], split=split) for r, h in zip(rows, hypotheses)]
    return dict(split=split, metrics=metrics(task, predictions, classes), predictions=predictions,
        by_sitting={group: metrics(task, [p for p in predictions if p["acquisition_id"] == group], classes)
                    for group in sorted({p["acquisition_id"] for p in predictions})},
        by_mode={mode: metrics(task, [p for p in predictions if p["articulation"] == mode], classes)
                 for mode in sorted({p["articulation"] for p in predictions})})


def phrase_features(root, rows, recipe, notify, check):
    spec = FeatureSpec(range_min_m=recipe["range_min_m"], range_max_m=recipe["range_max_m"])
    xs = []
    for i, row in enumerate(rows):
        check()
        z, t = signal(root, row)
        xs.append(features(z, t, row["profile"]["range_step_m"], spec))
        notify("preparing", completed=i+1, total=len(rows))
    return np.asarray(xs, dtype=np.float64)


def fit_phrase(snapshot, root, out, notify, check):
    rows = [r for r in snapshot["rows"] if r["split"] == "train"]
    x = phrase_features(root, rows, snapshot["recipe"], notify, check)
    y = np.array([r["text"] for r in rows])
    notify("training")
    scaler = StandardScaler()
    classifier = OneVsRestClassifier(LogisticRegression(C=.1, max_iter=1500, solver="liblinear", random_state=17))
    duration_scaler = StandardScaler()
    duration_classifier = OneVsRestClassifier(LogisticRegression(C=.1, solver="liblinear", random_state=17))
    with threadpool_limits(limits=2):
        classifier.fit(scaler.fit_transform(x), y)
        duration_classifier.fit(duration_scaler.fit_transform(x[:, -1:]), y)
    check()
    np.savez_compressed(out / "model.npz", mean=scaler.mean_, scale=scaler.scale_,
        coef=np.stack([c.coef_[0] for c in classifier.estimators_]),
        intercept=np.array([c.intercept_[0] for c in classifier.estimators_]),
        duration_mean=duration_scaler.mean_, duration_scale=duration_scaler.scale_,
        duration_coef=np.stack([c.coef_[0] for c in duration_classifier.estimators_]),
        duration_intercept=np.array([c.intercept_[0] for c in duration_classifier.estimators_]))
    model = dict(recipe=snapshot["recipe"], classes=classifier.classes_.tolist(), task="phrases",
                 signal_shape=rows[0]["shape"][1:])
    atomic_json(out / "model.json", model)
    return model


def phrase_predict(out, x, model, duration=False):
    with np.load(out / "model.npz", allow_pickle=False) as weights:
        prefix = "duration_" if duration else ""
        if duration:
            x = x[:, -1:]
        scaled = (x - weights[prefix+"mean"]) / weights[prefix+"scale"]
        margins = np.einsum("ij,kj->ik", scaled, weights[prefix+"coef"], optimize=False) + weights[prefix+"intercept"]
        if margins.shape[1] == 1:
            p = expit(margins[:, 0]); scores = np.column_stack([1-p, p])
        else:
            log_scores = log_expit(margins)
            scores = np.exp(log_scores-logsumexp(log_scores, axis=1, keepdims=True))
        if not np.isfinite(scores).all():
            raise ValueError("Non-finite model output")
        return np.asarray(model["classes"])[scores.argmax(axis=1)].tolist()


def evaluate(snapshot, root, out, split, notify, check):
    rows = [r for r in snapshot["rows"] if r["split"] == split]
    model = json.loads((out / "model.json").read_text())
    if not rows:
        return report(snapshot["task"], [], [], split)
    if snapshot["task"] == "phrases":
        x = phrase_features(root, rows, model["recipe"], notify, check)
        notify("evaluating", split=split)
        hypotheses = phrase_predict(out, x, model)
        result = report("phrases", rows, hypotheses, split, model["classes"])
        result["metrics"]["duration_only_accuracy"] = float(accuracy_score(
            [r["text"] for r in rows], phrase_predict(out, x, model, duration=True)))
        return result
    from .sequence_model import predict
    hypotheses = predict(snapshot, root, out, rows, notify, check)
    return report("sentences", rows, hypotheses, split)


def fit(snapshot, root, out, notify=lambda *a, **k: None, check=lambda: None):
    # A routine fit never exposes final-test rows to a recipe.
    snapshot = {**snapshot, "rows": [r for r in snapshot["rows"] if r["split"] != "test"]}
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    if snapshot["task"] == "phrases":
        fit_phrase(snapshot, root, out, notify, check)
    else:
        from .sequence_model import fit_sequence
        fit_sequence(snapshot, root, out, notify, check)
    check()
    development = evaluate(snapshot, root, out, "validation", notify, check)
    model_hash = file_hash(out / "model.npz")
    return dict(task=snapshot["task"], model_sha256=model_hash,
                model_config_sha256=file_hash(out / "model.json"), development=development,
                limitations="Synthetic results do not measure speech recognition. Development results are not final-test results.")


def validate_weights(config, payload, rows):
    """Validate portable artifacts without importing PyTorch or executing pickle."""
    import zipfile
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 256*1024**2:
            raise ValueError("Expanded model weights are too large")
    with np.load(io.BytesIO(payload), allow_pickle=False) as weights:
        if config['task'] == 'phrases':
            classes = config.get('classes', [])
            if len(set(classes)) != len(classes) or not 2 <= len(classes) <= 1000:
                raise ValueError('Invalid phrase classes')
            count = len(classes) if len(classes)>2 else 1
            expected = dict(mean=(8193,), scale=(8193,), coef=(count,8193), intercept=(count,),
                            duration_mean=(1,),duration_scale=(1,),duration_coef=(count,1),duration_intercept=(count,))
        else:
            from .sequence_model import VOCAB
            hidden = config['recipe']['hidden_size']
            inputs = rows[0]['shape'][2]*16*3+1
            if config.get('input_size') != inputs or config.get('vocab') != VOCAB:
                raise ValueError('Invalid sequence model input or vocabulary')
            expected = {'front.0.weight':(hidden,inputs,3),'front.0.bias':(hidden,),
                        'front.2.weight':(hidden,hidden,3),'front.2.bias':(hidden,),
                        'output.weight':(len(VOCAB)+1,hidden*2),'output.bias':(len(VOCAB)+1,)}
            for layer in range(2):
                for direction in ('','_reverse'):
                    expected[f'encoder.weight_ih_l{layer}{direction}']=(hidden*3,hidden if layer==0 else hidden*2)
                    expected[f'encoder.weight_hh_l{layer}{direction}']=(hidden*3,hidden)
                    expected[f'encoder.bias_ih_l{layer}{direction}']=(hidden*3,)
                    expected[f'encoder.bias_hh_l{layer}{direction}']=(hidden*3,)
        if set(weights.files) != set(expected):
            raise ValueError('Model tensor names do not match the recipe')
        for key, shape in expected.items():
            value = weights[key]
            if value.shape != shape or value.dtype.kind != 'f' or not np.isfinite(value).all():
                raise ValueError('Invalid model tensor: '+key)
        if config['task']=='phrases' and (np.any(weights['scale']<=0) or np.any(weights['duration_scale']<=0)):
            raise ValueError('Invalid normalization scale')
