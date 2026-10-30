from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import hashlib
import json
import os
from pathlib import Path
from ipaddress import IPv4Address
import time
import uuid
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .engine import Engine
from .features import FeatureSpec
from .profile import bundled_profile, parse_profile
from .storage import Store, atomic_json, checked_id
from . import training
from .transport import ports

STATIC = Path(__file__).parent / "static"


class Connect(BaseModel):
    source: str = "simulator"
    profile: str = "usb-phase-20hz"
    config_text: str | None = Field(default=None, max_length=30000)
    cli_port: str | None = None
    data_port: str | None = None
    data_baud: int = Field(default=921600, ge=115200, le=3000000)
    host_ip: IPv4Address = IPv4Address("192.168.33.30")
    board_ip: IPv4Address = IPv4Address("192.168.33.180")
    confirm_layout: bool = False


class SessionInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(default="Boyd", min_length=1, max_length=80)
    notes: str = Field(default="", max_length=4000)


class TrialInput(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    duration_s: float = Field(default=3, ge=0.5, le=30)
    articulation: str = Field(default="silent", pattern="^(silent|voiced|whisper|rest|negative)$")
    notes: str = Field(default="", max_length=4000)


class TrialUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    accepted: bool | None = None
    notes: str | None = Field(default=None, max_length=4000)


class TrainInput(BaseModel):
    session_ids: list[str] = Field(min_length=2, max_length=50)
    test_session_ids: list[str] = Field(min_length=1, max_length=49)
    range_min_m: float = Field(default=0.2, ge=0, le=10)
    range_max_m: float = Field(default=0.85, gt=0, le=10)


class DecodeInput(BaseModel):
    model_id: str
    seconds: float = Field(default=3, ge=0.5, le=20)
    threshold: float = Field(default=0.65, ge=0, le=1)


class PredictTrialInput(BaseModel):
    model_id: str
    session_id: str
    trial_id: str
    threshold: float = Field(default=0.65, ge=0, le=1)


def create_app(data_root=None):
    store = Store(data_root or os.environ.get("SUBVOCAL_DATA", "data"))
    engine = Engine(store)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="baseline-training")

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.close()
        pool.shutdown(wait=True)

    app = FastAPI(title="Desktop Subvocal", lifespan=lifespan)
    app.state.store, app.state.engine = store, engine

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "Localhost access only"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin not in {f"http://{request.headers.get('host')}", "http://testserver"}:
            return JSONResponse({"detail": "Cross-origin access rejected"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=(self)"
        return response

    @app.exception_handler(ValueError)
    async def bad_input(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def not_found(request, exc):
        return JSONResponse({"detail": "Record not found"}, status_code=404)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": "0.1.0", "data_root": str(store.root),
                "hardware_verified": False, "server_monotonic_ns": time.monotonic_ns()}

    @app.get("/api/clock")
    def clock_sync():
        return {"monotonic_ns": time.monotonic_ns(), "wall_ns": time.time_ns()}

    @app.get("/api/ports")
    def list_ports():
        return ports()

    @app.get("/api/profiles")
    def profiles():
        return [dict(name=n, **bundled_profile(n).summary()) for n in ("usb-phase-20hz", "usb-phase-10hz", "dca-raw")]

    @app.post("/api/connect")
    def connect(body: Connect):
        p = parse_profile(body.config_text) if body.config_text else bundled_profile(body.profile)
        if body.source == "serial" and (not body.cli_port or not body.data_port):
            raise ValueError("Select both USB serial ports explicitly")
        try:
            engine.connect(body.source, p, body.cli_port, body.data_port, body.data_baud,
                           str(body.host_ip), str(body.board_ip), body.confirm_layout)
        except (OSError, RuntimeError, TimeoutError) as exc:
            raise HTTPException(400, str(exc)) from exc
        return engine.snapshot()

    @app.post("/api/disconnect")
    def disconnect():
        engine.disconnect()
        return {"ok": True}

    @app.get("/api/live")
    def live(selected_bin: int = 8, antenna: int = 0):
        return engine.snapshot(selected_bin, antenna)

    @app.get("/api/sessions")
    def sessions():
        return store.sessions()

    @app.post("/api/sessions")
    def new_session(body: SessionInput):
        return engine.create_session(body.name, body.subject, body.notes)

    @app.get("/api/sessions/{sid}/trials")
    def trials(sid: str):
        store.session(sid)
        return store.trials(sid)

    @app.post("/api/record")
    def record(body: TrialInput):
        return engine.record(body.label, body.duration_s, body.articulation, body.notes)

    @app.get("/api/record/{rid}")
    def recording(rid: str):
        checked_id(rid)
        if rid not in engine.record_results:
            raise HTTPException(404, "Recording not found in this app run")
        with engine.lock:
            return engine.record_results[rid].copy()

    @app.post("/api/record/{rid}/cancel")
    def cancel_record(rid: str):
        checked_id(rid)
        return engine.cancel_record(rid)

    @app.patch("/api/sessions/{sid}/trials/{tid}")
    def update_trial(sid: str, tid: str, body: TrialUpdate):
        return store.update_trial(sid, tid, body.model_dump(exclude_none=True))

    @app.get("/api/sessions/{sid}/trials/{tid}/signal")
    def trial_signal(sid: str, tid: str):
        arr = store.load_signal(sid, tid)
        z, t = arr["iq"], arr["timestamps_ns"]
        selected = min(8, z.shape[1]-1)
        phase = np.unwrap(np.angle(z[:, selected, 0]))
        return {"time_s": ((t-t[0])/1e9).tolist(), "phase": (phase-phase[0]).tolist(),
                "range_magnitude": np.abs(z).mean(axis=(0, 2)).tolist(), "shape": list(z.shape)}

    @app.get("/api/sessions/{sid}/trials/{tid}/download")
    def download(sid: str, tid: str):
        return FileResponse(store.trial_dir(sid, tid)/"radar.npz", filename=f"{tid}-radar.npz")

    @app.get("/api/sessions/{sid}/trials/{tid}/raw/{name}")
    def raw_capture_file(sid: str, tid: str, name: str):
        if name not in {"manifest.json", "adc.bin", "radar.cfg"}:
            raise HTTPException(404, "Unknown raw capture file")
        meta = json.loads((store.trial_dir(sid, tid)/"trial.json").read_text())
        folder = meta.get("raw_capture_dir")
        if meta.get("source") != "dca1000" or not folder:
            raise HTTPException(404, "No raw DCA capture")
        path = (Path(folder)/name).resolve()
        if not path.is_relative_to((store.root/"raw").resolve()) or not path.is_file():
            raise HTTPException(404, "Raw file is outside this workbench's capture directory")
        return FileResponse(path, filename=f"{tid}-{name}")

    @app.put("/api/sessions/{sid}/trials/{tid}/media")
    async def media(sid: str, tid: str, request: Request):
        path = store.trial_dir(sid, tid)
        meta_path = path / "trial.json"
        meta = json.loads(meta_path.read_text())
        if request.headers.get("content-type", "").split(";")[0] not in ("video/webm", "audio/webm", "video/mp4"):
            raise ValueError("Expected a browser WebM/MP4 recording")
        suffix = ".mp4" if request.headers.get("content-type", "").startswith("video/mp4") else ".webm"
        target = path / ("reference" + suffix)
        if target.exists():
            raise ValueError("Reference recording already exists")
        tmp = path / (uuid.uuid4().hex + ".upload")
        count, digest = 0, hashlib.sha256()
        try:
            with tmp.open("xb") as f:
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > 64*1024*1024:
                        raise ValueError("Reference media exceeds 64 MiB")
                    f.write(chunk)
                    digest.update(chunk)
            os.replace(tmp, target)
        finally:
            tmp.unlink(missing_ok=True)
        meta["media"] = {"file": target.name, "bytes": count, "sha256": digest.hexdigest(),
                         "browser_start_server_ns": request.headers.get("x-media-start-server-ns"),
                         "clock_uncertainty_ms": request.headers.get("x-clock-uncertainty-ms"),
                         "synchronization": "Browser/software timestamps only; not hardware synchronized"}
        atomic_json(meta_path, meta)
        return meta["media"]

    @app.get("/api/sessions/{sid}/trials/{tid}/media")
    def get_media(sid: str, tid: str):
        path = store.trial_dir(sid, tid)
        meta = json.loads((path/"trial.json").read_text())
        if not meta.get("media"):
            raise HTTPException(404, "No reference media")
        return FileResponse(path / meta["media"]["file"])

    @app.post("/api/train")
    def launch_train(body: TrainInput):
        jid = uuid.uuid4().hex
        job_path = store.root / "jobs" / (jid + ".json")
        atomic_json(job_path, {"id": jid, "status": "queued"})
        def work():
            atomic_json(job_path, {"id": jid, "status": "running"})
            try:
                report = training.train(store, body.session_ids, body.test_session_ids,
                    FeatureSpec(range_min_m=body.range_min_m, range_max_m=body.range_max_m))
                atomic_json(job_path, {"id": jid, "status": "complete", "report": report})
            except Exception as exc:
                atomic_json(job_path, {"id": jid, "status": "failed", "error": str(exc)})
        pool.submit(work)
        return {"id": jid, "status": "queued"}

    @app.get("/api/jobs/{jid}")
    def job(jid: str):
        return json.loads((store.root / "jobs" / (checked_id(jid) + ".json")).read_text())

    @app.get("/api/models")
    def models(session_id: str | None = None):
        reports = [json.loads(f.read_text()) for f in sorted((store.root/"models").glob("*/report.json"), reverse=True)]
        if session_id:
            session = store.session(session_id)
            reports = [r for r in reports if (r["source"],r["subject"],r["synthetic"],r["profile_sha256"]) ==
                       (session["source"],session["subject"],session["synthetic"],session["profile"]["sha256"])]
        return reports

    @app.post("/api/predict-trial")
    def predict_trial(body: PredictTrialInput):
        return training.predict_trial(store, body.model_id, body.session_id, body.trial_id, body.threshold)

    @app.post("/api/decode")
    def decode(body: DecodeInput):
        with engine.lock:
            if getattr(engine.source, "kind", None) == "dca1000":
                raise ValueError("DCA is prompted capture; use saved trials for evaluation. Live decoding requires a continuous USB source")
            if engine.status != "connected" or not engine.session or not engine.ring:
                raise ValueError("Connect and create a session first")
            if time.monotonic_ns() - engine.ring[-1]["t"] > 2e9:
                raise ValueError("Radar stream is stale")
            end = engine.ring[-1]["t"]
            items = [x for x in engine.ring if x["t"] >= end-body.seconds*1e9]
            session = engine.session.copy()
        return training.predict(store, body.model_id, np.array([x["iq"] for x in items]),
                                np.array([x["t"] for x in items]), session, body.threshold)

    return app
