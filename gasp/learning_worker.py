"""Portable training worker. Use inside the rack's approved Slurm/container contract.

python -m gasp.learning_worker job.zip --output /project/runs/run-id
The same command resumes an interrupted sentence run from its epoch checkpoint.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import tempfile
import time
import zipfile

from . import learning_data as data
from . import learning_models as models
from .learning_runs import source_identity
from .storage import atomic_json


def execute(package, output, smoke=False):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    job_hash_path = output / "job-identity.json"
    stop = False

    def interrupted(*args):
        nonlocal stop
        stop = True

    old = {s: signal.signal(s, interrupted) for s in (signal.SIGTERM, signal.SIGINT)}

    def check():
        if stop:
            raise models.Cancelled("Worker was interrupted; run the same package again to resume")

    def notify(status, **progress):
        check()
        atomic_json(output/"progress.json", dict(status=status, updated_ns=time.time_ns(), **progress))
        if progress.get("checkpoint"):
            with (output/"metrics.jsonl").open("a") as f:
                f.write(json.dumps(dict(at_ns=time.time_ns(), **progress))+"\n")

    try:
        with zipfile.ZipFile(package) as archive:
            if archive.getinfo("job.json").file_size > 100*1024**2:
                raise ValueError("Job manifest is too large")
            job = json.loads(archive.read("job.json"))
            if job["sha256"] != data.digest({k: v for k, v in job.items() if k != "sha256"}):
                raise ValueError("Job manifest checksum mismatch")
            if job["source"]["source_sha256"] != source_identity()["source_sha256"]:
                raise ValueError("Use the matching Gasp source revision for this job")
            snapshot = job["snapshot"]
            if snapshot["sha256"] != data.digest({k: v for k, v in snapshot.items() if k != "sha256"}):
                raise ValueError("Dataset checksum mismatch")
            allowed_splits = {"test"} if job["kind"] == "final" else {"train", "validation"}
            if any(r["split"] not in allowed_splits for r in snapshot["rows"]):
                raise ValueError("Job contains forbidden dataset roles")
            if not os.environ.get("SLURM_JOB_ID") and not smoke:
                raise ValueError("Run this worker inside a Slurm allocation. --smoke is a bounded CPU-only check.")
            if smoke:
                if len(snapshot["rows"]) > 64:
                    raise ValueError("Use at most 64 takes for a CPU smoke check")
                os.environ["CUDA_VISIBLE_DEVICES"] = ""
                snapshot = {**snapshot, "recipe": {**snapshot["recipe"], "epochs": 2}}
            identity = dict(job_sha256=job["sha256"], smoke=smoke)
            if job_hash_path.exists() and json.loads(job_hash_path.read_text()) != identity:
                raise ValueError("Output directory belongs to another job")
            atomic_json(job_hash_path, identity)
            required = {"job.json"} | {r["path"] for r in snapshot["rows"]}
            if job["kind"] == "final":
                required |= {"model.npz", "model.json"}
            if set(archive.namelist()) != required or len(archive.namelist()) != len(required):
                raise ValueError("Unexpected or duplicate package files")
            size = sum(i.file_size for i in archive.infolist())
            if size > shutil.disk_usage(output).free:
                raise ValueError("Insufficient scratch space")
            with tempfile.TemporaryDirectory(prefix="inputs-", dir=output) as scratch:
                root = Path(scratch)
                for name in sorted(required - {"job.json"}):
                    check(); destination = root/name
                    if Path(name).is_absolute() or ".." in Path(name).parts or destination.resolve() != destination:
                        raise ValueError("Unsafe package path")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(name) as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target, length=1024*1024)
                for row in snapshot["rows"]:
                    data.checked_signal(root, row)
                if job["kind"] == "final":
                    for name in ("model.json", "model.npz"):
                        shutil.copyfile(root/name, output/name)
                    if data.file_hash(output/"model.npz") != job["candidate_model_sha256"]:
                        raise ValueError("Final candidate checksum mismatch")
                    if data.file_hash(output/"model.json") != job["candidate_model_config_sha256"]:
                        raise ValueError("Final candidate configuration checksum mismatch")
                    evaluation = models.evaluate(snapshot, root, output, "test", notify, check)
                else:
                    result = models.fit(snapshot, root, output, notify, check)
                    evaluation = result["development"]
                check()
                receipt = dict(run_id=job["run_id"], job_sha256=job["sha256"], smoke_only=smoke,
                    model_sha256=data.file_hash(output/"model.npz"), predictions=evaluation["predictions"],
                    worker=dict(source=source_identity(), slurm_job_id=os.environ.get("SLURM_JOB_ID"),
                                container_digest=os.environ.get("GASP_CONTAINER_DIGEST"), finished_ns=time.time_ns()))
                atomic_json(output/"result.json", receipt)
                with zipfile.ZipFile(output/"result.part", "w", compression=zipfile.ZIP_STORED) as result_zip:
                    for name in ("result.json", "model.json", "model.npz"):
                        result_zip.write(output/name, name)
                (output/"result.part").replace(output/"result.zip")
                notify("complete")
                return output/"result.zip"
    except models.Cancelled:
        atomic_json(output/"progress.json", dict(status="interrupted", updated_ns=time.time_ns()))
        raise
    except Exception as exc:
        atomic_json(output/"progress.json", dict(status="failed", error=str(exc), updated_ns=time.time_ns()))
        raise
    finally:
        for sig, handler in old.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke", action="store_true", help="CPU-only, <=64 takes, two epochs; cannot be imported as a trained model")
    args = parser.parse_args()
    try:
        print(execute(args.package, args.output, args.smoke))
    except (ValueError, OSError, models.Cancelled, zipfile.BadZipFile) as exc:
        parser.exit(1, str(exc)+"\n")


if __name__ == "__main__":
    main()
