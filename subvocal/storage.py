import hashlib
import json
import threading
import os
from pathlib import Path
import re
import time
import uuid
import numpy as np

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
        for folder in ("sessions", "models", "jobs"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)

    def session_dir(self, sid):
        return self.root / "sessions" / checked_id(sid)

    def create_session(self, name, subject, source, profile, notes="", collection=None):
        sid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        path = self.session_dir(sid)
        path.mkdir()
        manifest = {"schema": 1, "id": sid, "name": name, "subject": subject, "source": source,
                    "synthetic": source == "simulator", "created_ns": time.time_ns(),
                    "profile": profile.summary(), "notes": notes}
        if collection:
            manifest.update(schema=2, collection=collection)
        atomic_json(path / "session.json", manifest)
        (path / "radar.cfg").write_text(profile.text)
        (path / "trials").mkdir()
        return manifest

    def session(self, sid):
        return json.loads((self.session_dir(sid) / "session.json").read_text())

    def sessions(self):
        result = []
        for f in sorted((self.root / "sessions").glob("*/session.json"), reverse=True):
            item = json.loads(f.read_text())
            trials = self.trials(item["id"])
            item["trial_count"] = len(trials)
            item["accepted_count"] = sum(t.get("accepted", True) for t in trials)
            item["pending_count"] = sum(t.get("review_status") == "pending" for t in trials)
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
            for key in ("label", "accepted", "notes", "confirmed_text", "utterance_start_s", "utterance_end_s"):
                if key in updates:
                    meta[key] = updates[key]
            if meta.get("collection_protocol"):
                if "label" in updates:
                    raise ValueError("Review the confirmed transcript; the original prompt is immutable")
                start, end = meta.get("utterance_start_s", 0), meta.get("utterance_end_s", meta["duration_s"])
                if not 0 <= start < end <= meta["duration_s"] + .001:
                    raise ValueError("Utterance boundaries must lie inside the saved radar recording")
                if updates.get("accepted"):
                    if not (meta.get("confirmed_text") or "").strip():
                        raise ValueError("Confirm the actual text or movement label before accepting this take")
                    meta.update(label=meta["confirmed_text"].strip(), review_status="verified",
                                transcript_source="human_confirmed", reviewed_ns=time.time_ns())
                elif "accepted" in updates:
                    meta.update(review_status="rejected", reviewed_ns=time.time_ns())
                elif any(k in updates for k in ("confirmed_text", "utterance_start_s", "utterance_end_s")):
                    meta.update(accepted=False, review_status="pending")
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
            review_status="pending", accepted=False, calibration_id=collection.get("calibration_id"))

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
