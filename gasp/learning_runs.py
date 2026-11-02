"""Durable training runs with local and portable scheduled-worker destinations."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid
import zipfile

from . import __version__
from . import learning_data as datasets
from . import learning_models as models
from .storage import atomic_json, checked_id


ACTIVE = {"queued", "preparing", "training", "evaluating", "cancelling"}


def source_identity():
    packaged = Path(__file__).with_name("build-info.json")
    if getattr(sys, "frozen", False) and packaged.exists():
        return json.loads(packaged.read_text())
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).parent, text=True, stderr=subprocess.DEVNULL, timeout=2).strip()
    except (OSError, subprocess.SubprocessError):
        commit = "unknown"
    files = {p.name: datasets.file_hash(p) for p in Path(__file__).parent.glob("*.py")}
    return dict(version=__version__, commit=commit, source_sha256=datasets.digest(files))


class Runs:
    def __init__(self, store):
        self.store = store
        self.root = store.root / "training-runs"
        self.root.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gasp-learning")
        self.cancelled = {}
        for path in self.root.glob("*/run.json"):
            run = json.loads(path.read_text())
            if run["status"] in ACTIVE:
                run.update(status="interrupted", message="Gasp closed before this run finished. Retry uses the same frozen dataset.")
                atomic_json(path, run)

    def close(self):
        with self.lock:
            for event in self.cancelled.values():
                event.set()
        self.pool.shutdown(wait=True)

    def folder(self, rid):
        return self.root / checked_id(rid)

    def get(self, rid):
        run = json.loads((self.folder(rid) / "run.json").read_text())
        snapshot = datasets.load_snapshot(self.store, run["dataset_id"])
        run["availability"] = datasets.availability(self.store, snapshot)
        return run

    def list(self, cohort=None):
        result = [self.get(p.parent.name) for p in self.root.glob("*/run.json")]
        if cohort:
            result = [r for r in result if r["cohort"]["id"] == cohort]
        return sorted(result, key=lambda r: r["created_ns"], reverse=True)

    def update(self, rid, **fields):
        with self.lock:
            path = self.folder(rid) / "run.json"
            run = json.loads(path.read_text())
            checkpoint = fields.pop("checkpoint", False)
            if fields.get("status") != run["status"] or checkpoint:
                run.setdefault("events", []).append(dict(at_ns=time.time_ns(), **fields))
            run.update(fields, updated_ns=time.time_ns())
            atomic_json(path, run)
            return run

    def active_for(self, sid):
        for run in self.list():
            if run["status"] in ACTIVE:
                snapshot = datasets.load_snapshot(self.store, run["dataset_id"])
                if any(r["session_id"] == sid for r in snapshot["rows"]):
                    return True
        return False

    def dependencies(self, sid):
        return [dict(id=r["id"], name=r["name"], status=r["status"])
                for r in self.list() if any(row["session_id"] == sid for row in
                datasets.load_snapshot(self.store, r["dataset_id"])["rows"])]

    def source_deleted(self, sid):
        for dependency in self.dependencies(sid):
            rid = dependency["id"]
            (self.folder(rid) / "package.zip").unlink(missing_ok=True)
            if dependency["status"] == "prepared":
                self.update(rid, status="invalidated", message="A source recording was deleted. Create a new dataset.")

    def start(self, snapshot, parent=None, retry_of=None):
        rid = uuid.uuid4().hex
        folder = self.folder(rid); folder.mkdir()
        run = dict(schema=1, id=rid, name=snapshot["recipe"]["name"], kind="final" if parent else "fit",
            status="queued", created_ns=time.time_ns(), dataset_id=snapshot["id"],
            dataset_sha256=snapshot["sha256"], cohort=snapshot["cohort"], counts=snapshot["counts"],
            recipe=snapshot["recipe"], destination=snapshot["recipe"]["runner"],
            source=source_identity(), parent_id=parent, retry_of=retry_of, events=[])
        run["evaluation_key"] = datasets.digest([{k: r[k] for k in
            ("session_id", "trial_id", "signal_sha256", "annotation_revision", "text", "start_s", "end_s")}
            for r in snapshot["rows"] if r["split"] == ("test" if parent else "validation")])
        if parent:
            source = self.folder(parent)
            parent_run = self.get(parent)
            if parent_run["status"] != "complete" or parent_run["kind"] != "fit":
                raise ValueError("Finish a model before checking the final test")
            for name, field in [("model.npz", "model_sha256"), ("model.json", "model_config_sha256")]:
                if datasets.file_hash(source/name) != parent_run["result"][field]:
                    raise ValueError("The trained model artifact changed")
                shutil.copyfile(source/name, folder/name)
            run["candidate_model_sha256"] = parent_run["result"]["model_sha256"]
            run["candidate_model_config_sha256"] = parent_run["result"]["model_config_sha256"]
        atomic_json(folder / "run.json", run)
        event = self.cancelled[rid] = threading.Event()
        self.pool.submit(self._work, rid, snapshot, event)
        return run

    def _work(self, rid, snapshot, event):
        def check():
            if event.is_set():
                raise models.Cancelled()

        def notify(status, **progress):
            check(); self.update(rid, status=status, progress=progress, checkpoint=progress.get("checkpoint", False))

        try:
            check()
            run = self.get(rid); out = self.folder(rid)
            if run["destination"] == "package":
                self.package(rid, snapshot, notify, check)
                check(); self.update(rid, status="prepared", message="Ready for a scheduled training worker. No rack job has been submitted.")
            elif run["kind"] == "fit":
                result = models.fit(snapshot, self.store.root, out, notify, check)
                check(); self.update(rid, status="complete", result=result)
            else:
                result = models.evaluate(snapshot, self.store.root, out, "test", notify, check)
                check(); self.update(rid, status="complete", result=dict(final_test=result,
                    model_sha256=datasets.file_hash(out / "model.npz")))
        except models.Cancelled:
            (self.folder(rid)/"package.zip").unlink(missing_ok=True)
            (self.folder(rid)/"package.part").unlink(missing_ok=True)
            self.update(rid, status="cancelled", message="Cancelled. The dataset and completed checkpoints are retained.")
        except Exception as exc:
            (self.folder(rid)/"package.part").unlink(missing_ok=True)
            self.update(rid, status="failed", message=str(exc))
        finally:
            with self.lock:
                self.cancelled.pop(rid, None)

    def cancel(self, rid):
        with self.lock:
            run = self.get(rid)
            if run["status"] not in ACTIVE | {"prepared"}:
                raise ValueError("This run is not active")
            if rid in self.cancelled:
                self.cancelled[rid].set()
                return self.update(rid, status="cancelling")
            (self.folder(rid)/"package.zip").unlink(missing_ok=True)
            return self.update(rid, status="cancelled", message="Prepared package cancelled. No remote job was submitted by Gasp.")

    def retry(self, rid):
        previous = self.get(rid)
        if previous["status"] not in {"failed", "cancelled", "interrupted"}:
            raise ValueError("Only failed, cancelled or interrupted runs can be retried")
        snapshot = datasets.load_snapshot(self.store, previous["dataset_id"])
        for row in snapshot["rows"]:
            datasets.checked_signal(self.store.root, row)
        return self.start(snapshot, parent=previous.get("parent_id"), retry_of=rid)

    def package(self, rid, snapshot, notify, check):
        run = self.get(rid)
        allowed = {"test"} if run["kind"] == "final" else {"train", "validation"}
        # Do not include test transcripts even in excluded-row explanations.
        subset = {**snapshot, "rows": [r for r in snapshot["rows"] if r["split"] in allowed], "exclusions": []}
        subset.pop("sha256")
        subset["source_snapshot_sha256"] = snapshot["sha256"]
        subset["sha256"] = datasets.digest(subset)
        job = dict(schema=1, run_id=rid, kind=run["kind"], source=run["source"], snapshot=subset,
                   candidate_model_sha256=run.get("candidate_model_sha256"),
                   candidate_model_config_sha256=run.get("candidate_model_config_sha256"))
        job["sha256"] = datasets.digest(job)
        total = sum(datasets.checked_signal(self.store.root, row).stat().st_size for row in subset["rows"])
        if shutil.disk_usage(self.root).free < total + 100*1024**2:
            raise ValueError("Not enough disk space to prepare the training package")
        out = self.folder(rid)
        with zipfile.ZipFile(out / "package.part", "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("job.json", json.dumps(job))
            for i, row in enumerate(subset["rows"]):
                check()
                archive.write(datasets.checked_signal(self.store.root, row), row["path"])
                notify("preparing", completed=i+1, total=len(subset["rows"]))
            if run["kind"] == "final":
                for name in ("model.json", "model.npz"):
                    archive.write(out/name, name)
        (out/"package.part").replace(out/"package.zip")
        self.update(rid, package_sha256=datasets.file_hash(out/"package.zip"), package_bytes=(out/"package.zip").stat().st_size,
                    worker_job_sha256=job["sha256"])

    def import_result(self, rid, path):
        with self.lock:
            run = self.get(rid)
            if run["status"] != "prepared":
                raise ValueError("This run is not awaiting a worker result")
            snapshot = datasets.load_snapshot(self.store, run["dataset_id"])
            out = self.folder(rid)
            with zipfile.ZipFile(path) as archive:
                names = archive.namelist()
                allowed = {"result.json", "model.json", "model.npz"}
                if len(names) != len(set(names)) or set(names) != allowed:
                    raise ValueError("Expected only the worker result and its model artifacts")
                if (any(i.file_size > 512*1024**2 for i in archive.infolist())
                        or archive.getinfo("result.json").file_size > 20*1024**2
                        or archive.getinfo("model.json").file_size > 1024**2):
                    raise ValueError("Worker result is too large")
                result = json.loads(archive.read("result.json"))
                if result.get("run_id") != rid or result.get("job_sha256") != run["worker_job_sha256"] or result.get("smoke_only"):
                    raise ValueError("Result belongs to a different run or is only a smoke test")
                model_json, weights = archive.read("model.json"), archive.read("model.npz")
                config = json.loads(model_json)
                if config.get("recipe") != snapshot["recipe"] or config.get("task") != snapshot["task"]:
                    raise ValueError("Worker model recipe does not match")
                if result.get("worker", {}).get("source", {}).get("source_sha256") != run["source"]["source_sha256"]:
                    raise ValueError("Worker source differs from this run. Use the matching Gasp source revision.")
                models.validate_weights(config, weights, snapshot["rows"])
                import hashlib
                if hashlib.sha256(weights).hexdigest() != result.get("model_sha256"):
                    raise ValueError("Worker model checksum mismatch")
                if run["kind"] == "final" and result["model_sha256"] != run["candidate_model_sha256"]:
                    raise ValueError("Final evaluation changed the selected model")
                if run["kind"] == "final" and hashlib.sha256(model_json).hexdigest() != run["candidate_model_config_sha256"]:
                    raise ValueError("Final evaluation changed the model configuration")
                split = "test" if run["kind"] == "final" else "validation"
                expected = [r for r in snapshot["rows"] if r["split"] == split]
                supplied = result.get("predictions", [])
                lookup = {(p["session_id"], p["trial_id"]): p["predicted"] for p in supplied}
                if len(lookup) != len(supplied) or set(lookup) != {(r["session_id"], r["trial_id"]) for r in expected}:
                    raise ValueError("Worker predictions do not cover the frozen evaluation set")
                hypotheses = [lookup[r["session_id"], r["trial_id"]] for r in expected]
                if any(not isinstance(h, str) or len(h) > 20000 for h in hypotheses):
                    raise ValueError("Invalid worker prediction")
                measured = models.report(snapshot["task"], expected, hypotheses, split, config.get("classes", []))
                # Metrics are recomputed here against the frozen labels, never trusted from an uploaded score.
                (out/"model.npz").write_bytes(weights); (out/"model.json").write_bytes(model_json)
                value = dict(model_sha256=result["model_sha256"], model_config_sha256=datasets.file_hash(out/"model.json"),
                    **{"final_test" if run["kind"] == "final" else "development": measured})
                return self.update(rid, status="complete", result=value, worker=result.get("worker", {}))
