import hashlib
import json
import threading
import os
from pathlib import Path
import re
import time
import uuid
import math
import shutil
import numpy as np
from .collection import capture_mode

ID = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def checked_id(value):
    if not ID.fullmatch(value):
        raise ValueError("Invalid record ID")
    return value


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    os.replace(tmp, path)


class Store:
    def __init__(self, root):
        self.lock = threading.RLock()
        self.root = Path(root).expanduser().resolve()
        for folder in ("sessions", "models", "jobs", "scenes", "discarded", "plans"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def create_scene(self, setup):
        # A scene describes placement. Sessions retain their own immutable snapshot.
        scene = dict(setup, id=uuid.uuid4().hex, created_ns=time.time_ns())
        atomic_json(self.root / "scenes" / (scene["id"] + ".json"), scene)
        return scene

    def scene(self, scene_id):
        return json.loads((self.root / "scenes" / (checked_id(scene_id) + ".json")).read_text())

    def save_plan(self, definition):
        plan = dict(definition, id=uuid.uuid4().hex, created_ns=time.time_ns())
        atomic_json(self.root / "plans" / (plan["id"] + ".json"), plan)
        return plan

    def plans(self):
        return sorted((json.loads(f.read_text()) for f in (self.root / "plans").glob("*.json")),
                      key=lambda p: p["created_ns"], reverse=True)

    def delete_session(self, sid):
        with self.lock:
            self.session(sid, include_discarded=True)
            paths = [self.session_dir(sid), self.root / "raw" / checked_id(sid)]
            # Never follow a collection-directory symlink outside the dataset.
            for path in paths:
                if path.is_symlink() or path.resolve() != path:
                    raise ValueError("Collection storage contains a redirected directory")
            for path in reversed(paths):
                if path.exists():
                    shutil.rmtree(path)
            self.discard_marker(sid).unlink(missing_ok=True)

    def scenes(self):
        return sorted((json.loads(f.read_text()) for f in (self.root / "scenes").glob("*.json")),
                      key=lambda s: s["created_ns"], reverse=True)

    def session_dir(self, sid):
        return self.root / "sessions" / checked_id(sid)

    def create_session(self, name, subject, source, profile, notes="", collection=None, device_info=None):
        sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        path = self.session_dir(sid)
        path.mkdir()
        manifest = {"schema": 1, "id": sid, "name": name, "subject": subject, "source": source,
                    "synthetic": source == "simulator", "created_ns": time.time_ns(),
                    "profile": profile.summary(), "notes": notes, "device_info": device_info or {}}
        if collection:
            manifest.update(schema=2, collection=collection)
        atomic_json(path / "session.json", manifest)
        (path / "radar.cfg").write_text(profile.text)
        (path / "trials").mkdir()
        return manifest

    def discard_marker(self, sid):
        return self.root / "discarded" / (checked_id(sid) + ".json")

    def set_discarded(self, sid, discarded):
        # Keep original manifests, raw ADC files and annotation history in place.
        # A separate tombstone makes discard/restore atomic and lossless.
        with self.lock:
            self.session(sid, include_discarded=True)
            marker = self.discard_marker(sid)
            if discarded:
                if not marker.exists():
                    atomic_json(marker, {"session_id": sid, "discarded_ns": time.time_ns()})
            else:
                marker.unlink(missing_ok=True)

    def session(self, sid, include_discarded=False):
        if not include_discarded and self.discard_marker(sid).exists():
            raise ValueError("This collection is discarded. Restore it before using it.")
        return json.loads((self.session_dir(sid) / "session.json").read_text())

    def sessions(self, discarded=False):
        with self.lock:
            return self._session_summaries(discarded)

    def _session_summaries(self, discarded):
        result = []
        for f in sorted((self.root / "sessions").glob("*/session.json"), reverse=True):
            item = json.loads(f.read_text())
            marker = self.discard_marker(item["id"])
            if marker.exists() != discarded:
                continue
            if discarded:
                item["discarded_ns"] = json.loads(marker.read_text())["discarded_ns"]
            trials = self.trials(item["id"])
            item["trial_count"] = len(trials)
            item["accepted_count"] = sum(t.get("accepted", True) for t in trials)
            item["pending_count"] = sum(t.get("review_status") == "pending" for t in trials)
            steps = item.get("collection", {}).get("plan", {}).get("steps", [])
            captured = {t.get("plan_step_id") for t in trials if t.get("review_status") != "rejected"}
            verified = {t.get("plan_step_id") for t in trials if t.get("review_status") == "verified"}
            item["verified_steps"] = sum(s["step_id"] in verified for s in steps)
            item["step_count"] = len(steps)
            item["completed_steps"] = sum(s["step_id"] in captured for s in steps)
            result.append(item)
        return sorted(result, key=lambda s: s["created_ns"], reverse=True)

    def trials(self, sid):
        return sorted((json.loads(f.read_text()) for f in (self.session_dir(sid) / "trials").glob("*/trial.json")),
                      key=lambda t: t["created_ns"])

    def trial_dir(self, sid, tid):
        return self.session_dir(sid) / "trials" / checked_id(tid)

    def save_trial(self, sid, label, timestamps, signals, frame_numbers, raw_packets=(), extra=None):
        tid = uuid.uuid4().hex
        path = self.trial_dir(sid, tid)
        path.mkdir()
        t = np.asarray(timestamps, dtype=np.int64)
        z = np.asarray(signals, dtype=np.complex64)
        n = np.asarray(frame_numbers, dtype=np.uint32)
        if len(t) < 3 or z.ndim != 3 or len(z) != len(t) or len(n) != len(t):
            raise ValueError("A trial needs at least 3 consistent complex radar frames")
        if np.any(np.diff(t) <= 0) or not np.isfinite(z).all():
            raise ValueError("Non-monotonic timestamps or invalid radar values")
        np.savez_compressed(path / "radar.npz", iq=z, timestamps_ns=t, frame_numbers=n)
        if raw_packets:
            with (path / "uart.bin").open("wb") as f:
                for packet in raw_packets:
                    f.write(packet)
        gaps = sum(max(0, ((int(b) - int(a)) & 0xffffffff) - 1) for a, b in zip(n[:-1], n[1:]))
        duration = (int(t[-1]) - int(t[0])) / 1e9
        meta = {"schema": 1, "id": tid, "session_id": sid, "label": label,
                "accepted": True, "created_ns": time.time_ns(), "frames": len(t),
                "duration_s": duration, "measured_hz": (len(t)-1) / duration,
                "shape": list(z.shape), "frame_gaps": gaps,
                "sha256": hashlib.sha256((path / "radar.npz").read_bytes()).hexdigest(),
                **(extra or {})}
        atomic_json(path / "trial.json", meta)
        return meta

    def update_trial(self, sid, tid, updates):
        with self.lock:
            path = self.trial_dir(sid, tid) / "trial.json"
            meta = json.loads(path.read_text())
            revision = meta.get("annotation_revision", 0)
            if "base_revision" in updates and updates["base_revision"] != revision:
                raise ValueError("This recording was edited elsewhere; reload before saving")
            for key in ("label", "accepted", "notes", "confirmed_text", "utterance_start_s", "utterance_end_s", "words", "audio_offset_s", "asr_raw_text"):
                if key in updates:
                    meta[key] = updates[key]
            if "confirmed_text" in updates and "words" not in updates and updates["confirmed_text"] != json.loads(path.read_text()).get("confirmed_text"):
                meta["words"] = []
            control = meta.get("articulation") in {"rest", "negative"}
            if control:
                meta.update(sample_kind="control", words=[], confirmed_text="",
                            transcript_source="not_applicable")
                updates = {k:v for k,v in updates.items() if k not in {"words", "confirmed_text"}}
            if "words" in updates or updates.get("accepted"):
                previous_end = 0
                for word in meta.get("words", []):
                    if not word.get("text", "").strip():
                        raise ValueError("Word text cannot be empty")
                    a, b = word.get("start_s"), word.get("end_s")
                    if a is None and b is None:
                        continue
                    bounds = [x for x in (a,b) if x is not None]
                    if (a is None or b is None) and updates.get("accepted"):
                        raise ValueError("Finish or clear the unfinished word boundary before keeping this take. Drafts can be saved at any time.")
                    if not all(math.isfinite(x) and 0 <= x <= meta["duration_s"]+.001 for x in bounds) or bounds[0] < previous_end or a is not None and b is not None and a >= b:
                        raise ValueError("Word intervals must be ordered, non-overlapping and inside the recording")
                    previous_end = bounds[-1]
                from .audio_review import speech_tokens
                if meta.get("words") and speech_tokens(" ".join(w["text"] for w in meta["words"])) != speech_tokens(meta.get("confirmed_text") or ""):
                    raise ValueError("Word annotations must match the confirmed transcript")
            if meta.get("collection_protocol"):
                if "label" in updates:
                    raise ValueError("Review the confirmed transcript; the original prompt is immutable")
                if updates.get("accepted") and not control:
                    if not (meta.get("confirmed_text") or "").strip():
                        raise ValueError("Confirm the actual text or movement label before accepting this take")
                    meta.update(label=meta["confirmed_text"].strip(), transcript_source="human_confirmed")
            start, end = meta.get("utterance_start_s", 0), meta.get("utterance_end_s", meta["duration_s"])
            if not all(math.isfinite(x) for x in (start, end)) or not 0 <= start < end <= meta["duration_s"] + .001:
                raise ValueError("Utterance boundaries must lie inside the saved radar recording")
            if "accepted" in updates:
                meta.update(review_status="verified" if updates["accepted"] else "rejected", reviewed_ns=time.time_ns())
            if any(k in updates for k in ("confirmed_text", "utterance_start_s", "utterance_end_s", "words", "audio_offset_s", "accepted")):
                if "accepted" not in updates:
                    meta.update(accepted=False, review_status="pending")
                history = path.parent / "annotations"
                atomic_json(history / f"{revision:06d}.json", json.loads(path.read_text()))
                meta["annotation_revision"] = revision + 1
            atomic_json(path, meta)
            return meta

    def collection_record(self, sid, step_id):
        session = self.session(sid)
        collection = session.get("collection")
        if not collection:
            raise ValueError("Create a collection session first")
        step = next((s for s in collection["plan"]["steps"] if s["step_id"] == step_id), None)
        if not step:
            raise ValueError("Unknown script step for this session")
        return step, dict(collection_protocol=collection["plan"]["protocol"],
            plan_step_id=step_id, prompt_id=step["prompt_id"], prompt_text=step["prompt_text"],
            target_text=step["target_text"], pair_id=step["pair_id"], confirmed_text=None,
            asr_raw_text=None, output_text=None, transcript_source="unverified_prompt",
            review_status="pending", accepted=False, calibration_id=collection.get("calibration_id"),
            collection_type_id=collection.get("type_id"), collection_version=collection.get("definition_version"),
            cohort_id=collection.get("cohort_id"), acquisition_id=collection.get("acquisition_id"),
            training_task=step.get("training_task"),
            sample_kind="control" if step["articulation"] in {"rest", "negative"} else "speech",
            capture_mode=capture_mode(step),
            required_duration_s=step["duration_s"] if capture_mode(step) == "timed" else None,
            capture_conditions={k: step.get(k, collection.get(k)) for k in ("scene_id", "scene_name", "distance_cm", "position_notes", "location", "enclosure", "mount", "yaw_deg", "pitch_deg", "roll_deg")},
            script_sha256=collection["plan"].get("script_sha256"), task=collection["plan"].get("task", "phrases"))

    def add_trial_fields(self, sid, tid, fields):
        with self.lock:
            path = self.trial_dir(sid, tid) / "trial.json"
            meta = json.loads(path.read_text())
            meta.update(fields)
            atomic_json(path, meta)
            return meta

    def load_signal(self, sid, tid):
        with np.load(self.trial_dir(sid, tid) / "radar.npz", allow_pickle=False) as arr:
            return {key: arr[key] for key in arr.files}
