from collections import Counter
import hashlib
import json
from pathlib import Path
import time
import uuid
import joblib
import numpy as np
from scipy.special import expit, log_expit, logsumexp
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.pipeline import make_pipeline
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
from .features import FeatureSpec, features
from .storage import atomic_json, checked_id


def trial_quality_error(trial):
    if not trial.get("accepted", True):
        return "Trial is excluded; review it before prediction"
    if trial.get("frame_gaps", 0) / max(1, trial["frames"]) > 0.05:
        return "More than 5% missing frames"
    adc = trial.get("adc_quality", {})
    if adc.get("dropped_frames", 0) / max(1, adc.get("complete_frames", 0)) > 0.05:
        return "More than 5% ADC frames lost to UDP gaps"
    return None


def model_scores(model, x):
    """OvR logistic scores without Accelerate's spurious matmul FP flags on macOS.

    Equivalent to sklearn OvR predict_proba; einsum(optimize=False) uses direct
    accumulation rather than BLAS. Validate finite results instead of silencing
    numerical warnings globally.
    """
    scaled = model.steps[0][1].transform(np.asarray(x, dtype=np.float64))
    classifier = model.steps[-1][1]
    margins = np.stack([np.einsum("ij,j->i", scaled, estimator.coef_[0], optimize=False)
                        + estimator.intercept_[0] for estimator in classifier.estimators_], axis=1)
    if not np.isfinite(margins).all():
        raise ValueError("Non-finite model score")
    if margins.shape[1] == 1:
        p = expit(margins[:, 0])
        return np.column_stack([1-p, p])
    log_scores = log_expit(margins)
    return np.exp(log_scores-logsumexp(log_scores, axis=1, keepdims=True))


def reviewed_signal(store, sid, tid, trial):
    arr = store.load_signal(sid, tid)
    if "utterance_start_s" in trial or "utterance_end_s" in trial:
        relative = (arr["timestamps_ns"]-arr["timestamps_ns"][0])/1e9
        keep = (relative >= trial.get("utterance_start_s", 0)) & (relative <= trial.get("utterance_end_s", trial["duration_s"]))
        arr = {k: v[keep] for k, v in arr.items()}
    return arr


def train(store, session_ids, test_session_ids, spec=None, articulation=None):
    spec = spec or FeatureSpec()
    session_ids, test_session_ids = list(dict.fromkeys(session_ids)), list(dict.fromkeys(test_session_ids))
    if len(session_ids) < 2 or not test_session_ids or not set(test_session_ids) < set(session_ids):
        raise ValueError("Choose at least two sessions and explicitly hold out one or more whole sessions")
    sessions = [store.session(s) for s in session_ids]
    provenance = {(s["synthetic"], s["subject"], s["profile"]["sha256"], s["source"]) for s in sessions}
    if len(provenance) != 1:
        raise ValueError("Use the same subject, source and radar profile; never mix simulator and hardware data")
    for session in sessions:
        role = session.get("collection", {}).get("visit_role")
        if role == "calibration" and session["id"] in test_session_ids:
            raise ValueError("Calibration visits cannot be held-out evaluation data")
        if role in {"validation", "test"} and session["id"] not in test_session_ids:
            raise ValueError("Reserved validation/test visits cannot be used for fitting")
    modes = {t.get("articulation", "silent") for s in sessions for t in store.trials(s["id"])
             if t.get("accepted", True) and t.get("articulation", "silent") in {"silent", "voiced", "whisper"}}
    if articulation is None and len(modes) > 1:
        raise ValueError("Select one articulation mode; voiced, whispered and silent takes cannot be pooled")
    articulation = articulation or next(iter(modes), "silent")
    rows, xs, labels, groups = [], [], [], []
    channel_shapes = set()
    rejected = []
    for session in sessions:
        for trial in store.trials(session["id"]):
            if not trial.get("accepted", True):
                continue
            if trial.get("articulation", "silent") not in {articulation, "rest", "negative"}:
                continue
            if trial.get("collection_protocol") and trial.get("review_status") != "verified":
                continue
            problem = trial_quality_error(trial)
            if problem:
                rejected.append({"id": trial["id"], "reason": problem})
                continue
            signal_path = store.trial_dir(session["id"], trial["id"]) / "radar.npz"
            digest = hashlib.sha256(signal_path.read_bytes()).hexdigest()
            if digest != trial["sha256"]:
                raise ValueError(f"Trial checksum mismatch: {trial['id']}")
            arr = reviewed_signal(store, session["id"], trial["id"], trial)
            try:
                x = features(arr["iq"], arr["timestamps_ns"], session["profile"]["range_step_m"], spec)
            except ValueError as exc:
                rejected.append({"id": trial["id"], "reason": str(exc)})
                continue
            xs.append(x)
            labels.append(trial["label"])
            groups.append(session["id"])
            channel_shapes.add(tuple(arr["iq"].shape[1:]))
            rows.append({"session": session["id"], "trial": trial["id"], "label": trial["label"],
                         "sha256": digest, "articulation": trial.get("articulation", "silent"),
                         "utterance_start_s": trial.get("utterance_start_s"), "utterance_end_s": trial.get("utterance_end_s"),
                         "collection_protocol": trial.get("collection_protocol"),
                         "split": "test" if session["id"] in test_session_ids else "train"})
    if len(channel_shapes) != 1:
        raise ValueError("All trials must have the same range/antenna layout")
    x, y = np.asarray(xs, dtype=np.float64), np.asarray(labels)
    test_mask = np.array([s in test_session_ids for s in groups])
    if not len(y) or len(set(y[~test_mask])) < 2:
        raise ValueError("Need at least two labels in the training sessions")
    if set(y[test_mask]) != set(y[~test_mask]):
        raise ValueError("Every label must appear in both training and held-out sessions")
    if min(Counter(y[~test_mask]).values()) < 2 or min(Counter(y[test_mask]).values()) < 2:
        raise ValueError("Need at least two examples per label on each side of the split")
    model = make_pipeline(StandardScaler(), OneVsRestClassifier(
        LogisticRegression(C=0.1, max_iter=1500, solver="liblinear", random_state=17)))
    with threadpool_limits(limits=2):
        model.fit(x[~test_mask], y[~test_mask])
        prediction = model.classes_[np.argmax(model_scores(model, x[test_mask]), axis=1)]
    classes = model.classes_.tolist()
    mid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    folder = store.root / "models" / mid
    folder.mkdir()
    report = {"schema": 1, "id": mid, "created_ns": time.time_ns(), "algorithm": "scaled-logistic-baseline-v1",
              "synthetic": sessions[0]["synthetic"], "subject": sessions[0]["subject"],
              "source": sessions[0]["source"], "articulation": articulation, "profile_sha256": sessions[0]["profile"]["sha256"],
              "profile_range_step_m": sessions[0]["profile"]["range_step_m"],
              "signal_shape": list(next(iter(channel_shapes))), "feature_spec": spec.to_dict(),
              "session_ids": session_ids, "test_session_ids": test_session_ids,
              "train_examples": int((~test_mask).sum()), "test_examples": int(test_mask.sum()),
              "labels": classes, "accuracy": float(accuracy_score(y[test_mask], prediction)),
              "macro_f1": float(f1_score(y[test_mask], prediction, average="macro", zero_division=0)),
              "majority_baseline": max(Counter(y[test_mask]).values()) / int(test_mask.sum()),
              "confusion_matrix": confusion_matrix(y[test_mask], prediction, labels=classes).tolist(),
              "rejected_trials": rejected, "dataset": rows,
              "limitations": "Phrase classification only. Scores on synthetic data do not measure speech recognition. Probabilities are not calibrated confidence."}
    joblib.dump(model, folder / "model.joblib")
    report["model_sha256"] = hashlib.sha256((folder / "model.joblib").read_bytes()).hexdigest()
    atomic_json(folder / "report.json", report)
    return report


def predict(store, model_id, iq, timestamps_ns, session, threshold=0.65):
    folder = store.root / "models" / checked_id(model_id)
    report = json.loads((folder / "report.json").read_text())
    if (report["synthetic"] != session["synthetic"] or report["source"] != session["source"]
            or report["subject"] != session["subject"] or report["profile_sha256"] != session["profile"]["sha256"]
            or list(iq.shape[1:]) != report["signal_shape"]):
        raise ValueError("Model subject, source, profile or antenna layout does not match the active session")
    path = folder / "model.joblib"
    if hashlib.sha256(path.read_bytes()).hexdigest() != report["model_sha256"]:
        raise ValueError("Model checksum mismatch")
    # Only locally generated models are loadable; there is no pickle-upload endpoint.
    model = joblib.load(path)
    x = features(iq, timestamps_ns, session["profile"]["range_step_m"], FeatureSpec(**report["feature_spec"]))
    probabilities = model_scores(model, x[None])[0]
    index = int(np.argmax(probabilities))
    return {"label": str(model.classes_[index]) if probabilities[index] >= threshold else None,
            "candidate": str(model.classes_[index]), "score": float(probabilities[index]),
            "threshold": threshold, "synthetic": report["synthetic"], "rejected": bool(probabilities[index] < threshold)}


def predict_trial(store, model_id, session_id, trial_id, threshold=0.65):
    session = store.session(session_id)
    path = store.trial_dir(session_id, trial_id)
    trial = json.loads((path/"trial.json").read_text())
    problem = trial_quality_error(trial)
    if problem:
        raise ValueError(problem)
    digest = hashlib.sha256((path/"radar.npz").read_bytes()).hexdigest()
    if digest != trial["sha256"]:
        raise ValueError(f"Trial checksum mismatch: {trial_id}")
    arr = reviewed_signal(store, session_id, trial_id, trial)
    # Labels, prompts and reference media are never passed to the model.
    result = predict(store, model_id, arr["iq"], arr["timestamps_ns"], session, threshold)
    report = json.loads((store.root/"models"/checked_id(model_id)/"report.json").read_text())
    matches = [r for r in report["dataset"] if r["sha256"] == digest]
    use = "training" if any(r["split"] == "train" for r in matches) else "held_out" if matches else "new"
    result.update(session_id=session_id, trial_id=trial_id, source=session["source"],
                  expected_label=trial["label"], evaluation_use=use,
                  session_seen=session_id in report["session_ids"],
                  correct=result["label"] == trial["label"] if result["label"] is not None else None)
    return result
