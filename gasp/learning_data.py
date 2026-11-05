"""Reviewed data inventories and immutable training snapshots.

Snapshots pin annotations; original radar stays in its existing location. Reading
one never consults the current transcript, and deleting a take invalidates reuse.
"""
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import time
import uuid
from zipfile import BadZipFile

import numpy as np

from .storage import atomic_json, checked_id
from .training import trial_quality_error


ROLES = ("train", "validation", "test")
RECIPES = {
    "phrase-v2": dict(id="phrase-v2", name="Phrase check", task="phrases",
        algorithm="scaled-logistic-v2", runner="local", range_min_m=.2,
        range_max_m=.85, seed=17, normalization="phrase-features-v1"),
    "radar-ctc-v1": dict(id="radar-ctc-v1", name="Sentence model", task="sentences",
        algorithm="conv-gru-ctc-v1", runner="package", range_min_m=.2,
        range_max_m=.85, seed=17, normalization="english-text-v1",
        feature_version="complex-sequence-v1", epochs=40, batch_size=4,
        hidden_size=128, learning_rate=.001),
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_text(text):
    # Keep numbers as written, with a versioned, explicit scoring policy.
    return " ".join(re.sub(r"[^a-z0-9' ]", " ", text.lower().replace("’", "'")).split())


def cohort_key(subject, source, profile):
    return digest([subject, source, profile])[:24]


def is_sentence(session, trial):
    collection = session.get("collection", {})
    return (trial.get("training_task") == "sentence"
            or collection.get("definition", {}).get("template") in {"reader", "sentences", "free"}
            or collection.get("plan", {}).get("task") == "reading")


def summary(rows):
    return {role: dict(takes=len(part := [r for r in rows if r["split"] == role]),
        seconds=round(sum(r["duration_s"] for r in part), 2),
        silent_seconds=round(sum(r["duration_s"] for r in part if r["articulation"] == "silent"), 2),
        voiced_seconds=round(sum(r["duration_s"] for r in part if r["articulation"] == "voiced"), 2),
        control_seconds=round(sum(r["duration_s"] for r in part if r["control"]), 2),
        utterances=len({r["text"] for r in part if not r["control"]}),
        sittings=len({r["acquisition_id"] for r in part})) for role in ROLES}


def leakage_errors(rows, task):
    """Task-specific content rules; repeated diagnostic phrase labels are allowed."""
    seen, problems = {}, []
    for row in rows:
        keys = [("recording", row["signal_sha256"]), ("sitting", row["acquisition_id"])]
        if row.get("pair_id"):
            keys.append(("paired takes", row["pair_id"]))
        if task == "sentences":
            keys.append(("sentence", normalize_text(row["text"])))
            if row.get("document_id"):
                keys.append(("source document", row["document_id"]))
        for kind, key in keys:
            previous = seen.setdefault((kind, key), row["split"])
            if previous != row["split"]:
                problems.append(f"The same {kind} appears in {previous} and {row['split']}. Keep it in one split.")
    # Shared long passages catch overlapping windows without penalizing common words.
    if task == "sentences":
        windows = {}
        for row in rows:
            tokens = normalize_text(row["text"]).split()
            for index in range(max(0, len(tokens) - 7)):
                key = tuple(tokens[index:index + 8])
                previous = windows.setdefault(key, row["split"])
                if previous != row["split"]:
                    problems.append("Overlapping text passages appear in different splits. Keep the source material together.")
                    break
    return list(dict.fromkeys(problems))


@lru_cache(maxsize=1024)
def window_frames(path, mtime_ns, size, start, end):
    # Read only the small timing array. Cache by file identity and trim so the
    # continuously refreshed readiness view does not decompress radar cubes.
    with np.load(path, allow_pickle=False) as data:
        t = data["timestamps_ns"]
        if not len(t) or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
            raise ValueError("Invalid radar timestamps")
        relative = (t-t[0])/1e9
        return int(np.count_nonzero((relative >= start) & (relative <= end)))


def inventory(store, subject, source, profile, task="phrases", include_voiced=False, exclude_sessions=()):
    if task not in {"phrases", "sentences"}:
        raise ValueError("Unknown training task")
    rows, excluded, blocks = [], [], []
    with store.lock:
        for session in store.sessions():
            if (session["subject"], session["source"], session["profile"]["sha256"]) != (subject, source, profile):
                continue
            collection = session.get("collection", {})
            role = collection.get("visit_role")
            trials = store.trials(session["id"])
            latest = {t["plan_step_id"]: t["id"] for t in trials
                      if t.get("plan_step_id") and t.get("accepted") and t.get("review_status") == "verified"}
            block = dict(id=session["id"], name=session["name"], role=role or "unassigned",
                         collection_id=collection.get("type_id"), included=0, pending=0,
                         relevant=0, excluded=session["id"] in exclude_sessions)
            blocks.append(block)
            for trial in trials:
                control = trial.get("articulation") in {"rest", "negative"}
                if role == "calibration" or collection.get("plan", {}).get("calibration"):
                    continue
                if task == "sentences" and (control or not is_sentence(session, trial)):
                    continue
                if task == "phrases" and is_sentence(session, trial):
                    continue
                block["relevant"] += 1
                articulation = trial.get("articulation", "silent")
                if not control and articulation not in ({"silent", "voiced"} if include_voiced and task == "sentences" else {"silent"}):
                    continue
                reason = None
                if session["id"] in exclude_sessions:
                    reason = "Excluded from this dataset"
                elif role not in ROLES:
                    reason = "No dataset role; legacy recordings are not assigned automatically"
                elif trial.get("review_status") != "verified" or not trial.get("accepted"):
                    reason = "Needs review" if trial.get("review_status") != "rejected" else "Rejected"
                elif trial.get("plan_step_id") and latest[trial["plan_step_id"]] != trial["id"]:
                    reason = "Earlier take of this step"
                elif (problem := trial_quality_error(trial)):
                    reason = problem
                text = trial["label"] if control else (trial.get("confirmed_text") or "").strip()
                if not reason and not text:
                    reason = "No reviewed transcript"
                if not reason and not (store.trial_dir(session["id"], trial["id"]) / "radar.npz").is_file():
                    reason = "Radar file is missing"
                if not reason:
                    path = store.trial_dir(session["id"], trial["id"]) / "radar.npz"
                    start, end = trial.get("utterance_start_s", 0), trial.get("utterance_end_s", trial["duration_s"])
                    try:
                        stat = path.stat()
                        measured = window_frames(path, stat.st_mtime_ns, stat.st_size, start, end)
                        if measured < 8:
                            reason = "Fewer than eight radar frames remain after trimming"
                        elif task == "sentences":
                            from .sequence_model import minimum_ctc_frames, targets
                            if measured < minimum_ctc_frames(targets(normalize_text(text))):
                                reason = "Transcript is too long for the measured radar window"
                    except (OSError, ValueError, KeyError, EOFError, BadZipFile):
                        reason = "Radar timing data cannot be read"
                if reason:
                    excluded.append(dict(session_id=session["id"], trial_id=trial["id"], reason=reason,
                                         text=trial.get("prompt_text") or trial["label"]))
                    block["pending"] += reason == "Needs review"
                    continue
                start, end = trial.get("utterance_start_s", 0), trial.get("utterance_end_s", trial["duration_s"])
                rows.append(dict(session_id=session["id"], trial_id=trial["id"], text=text,
                    control=control, articulation=articulation, split=role,
                    annotation_revision=trial.get("annotation_revision", 0),
                    signal_sha256=trial["sha256"], duration_s=end-start, start_s=start, end_s=end,
                    frames=trial["frames"], shape=trial["shape"], measured_hz=trial["measured_hz"],
                    acquisition_id=collection.get("acquisition_id") or session["id"],
                    pair_id=trial.get("pair_id"), collection_id=collection.get("type_id"),
                    collection_version=collection.get("definition_version"),
                    collection_sha256=collection.get("definition", {}).get("definition_sha256"),
                    document_id=(trial.get("script_sha256") if collection.get("plan", {}).get("task") == "reading" else None),
                    profile=session["profile"], setup=collection.get("scene_snapshot", {}),
                    capture_conditions=trial.get("capture_conditions", {}),
                    device_info=session.get("device_info", {}),
                    capture_events=trial.get("capture_events", []),
                    annotation=dict(words=trial.get("words", []), audio_offset_s=trial.get("audio_offset_s")),
                    path=f"sessions/{session['id']}/trials/{trial['id']}/radar.npz"))
                block["included"] += 1
    blockers = leakage_errors(rows, task)
    fitting = [r for r in rows if r["split"] == "train"]
    if task == "phrases":
        counts = Counter(r["text"] for r in fitting)
        if len(counts) < 2 or min(counts.values(), default=0) < 2:
            blockers.append("Review at least two examples of each phrase in First speech.")
    elif len(fitting) < 8:
        blockers.append("Review at least eight training sentences to prepare a pipeline check.")
    if len({tuple(r["shape"][1:]) for r in rows}) > 1:
        blockers.append("Recordings have different radar layouts. Use one compatible layout.")
    return dict(cohort=dict(subject=subject, source=source, profile=profile,
                           id=cohort_key(subject, source, profile), synthetic=source == "simulator"),
                task=task, include_voiced=include_voiced, rows=rows, excluded=excluded,
                sessions=[b for b in blocks if b["relevant"]], counts=summary(rows), blockers=blockers, ready=not blockers,
                warnings=[] if any(r["split"] == "validation" for r in rows) else
                ["No development recordings yet. This run can check fitting, but cannot measure generalization."])


def freeze(store, data, recipe_id):
    recipe = RECIPES.get(recipe_id)
    if not recipe or recipe["task"] != data["task"]:
        raise ValueError("Recipe does not match the dataset task")
    if data["blockers"]:
        raise ValueError(data["blockers"][0])
    with store.lock:
        for row in data["rows"]:
            # Reject a concurrent review rather than silently snapshotting stale state.
            trial = json.loads((store.trial_dir(row["session_id"], row["trial_id"]) / "trial.json").read_text())
            if trial.get("annotation_revision", 0) != row["annotation_revision"] or not trial.get("accepted"):
                raise ValueError("A recording changed. Refresh the dataset before training.")
            checked_signal(store.root, row)
            if recipe["task"] == "sentences" and row["split"] == "train":
                from .sequence_model import minimum_ctc_frames, targets
                _, timestamps = signal(store.root, row)
                if len(timestamps) < minimum_ctc_frames(targets(row["text"])):
                    raise ValueError("Too few measured radar frames for the transcript in take " + row["trial_id"]
                                     + ". Inspect its trim and acquisition rate before training.")
        snapshot = dict(schema=1, id=uuid.uuid4().hex, created_ns=time.time_ns(),
                        cohort=data["cohort"], task=data["task"], recipe=recipe,
                        include_voiced=data["include_voiced"], rows=data["rows"], counts=data["counts"],
                        exclusions=data["excluded"], text_normalization="english-text-v1")
        snapshot["sha256"] = digest(snapshot)
        atomic_json(store.root / "datasets" / (snapshot["id"] + ".json"), snapshot)
        return snapshot


def load_snapshot(store, sid):
    value = json.loads((store.root / "datasets" / (checked_id(sid) + ".json")).read_text())
    if value["sha256"] != digest({k: v for k, v in value.items() if k != "sha256"}):
        raise ValueError("Dataset manifest checksum mismatch")
    return value


def checked_signal(root, row):
    root = Path(root).resolve()
    path = root / row["path"]
    if path.resolve() != path or not path.is_relative_to(root):
        raise ValueError("Redirected radar file")
    if not path.is_file():
        raise ValueError("A source recording was deleted. Create a new dataset from the remaining takes.")
    if file_hash(path) != row["signal_sha256"]:
        raise ValueError("Radar checksum mismatch: " + row["trial_id"])
    return path


def signal(root, row):
    with np.load(checked_signal(root, row), allow_pickle=False) as data:
        t, z = data["timestamps_ns"], data["iq"]
        relative = (t - t[0]) / 1e9
        mask = (relative >= row["start_s"]) & (relative <= row["end_s"])
        if mask.sum() < 8:
            raise ValueError("Fewer than eight radar frames remain after trimming: " + row["trial_id"])
        return z[mask], t[mask]


def availability(store, snapshot):
    missing = [r["trial_id"] for r in snapshot["rows"] if not (store.root / r["path"]).is_file()]
    return dict(available=not missing, missing_takes=missing)
