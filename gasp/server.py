from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
from ipaddress import IPv4Address
import time
import uuid
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .engine import Engine
from .features import FeatureSpec
from .profile import bundled_profile, parse_profile
from .storage import Store, atomic_json, checked_id
from . import training
from .collection import DECKS, make_plan, capture_mode, capture_limit
from .transport import ports
from .replay import Replay
from . import __version__
from .journey import register_journey
from .learning_api import register_learning

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


class SceneInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(default="Boyd", min_length=1, max_length=80)
    distance_cm: float = Field(default=45, ge=10, le=200)
    location: str = Field(default="", max_length=120)
    enclosure: str = Field(default="", max_length=120)
    mount: str = Field(default="", max_length=120)
    yaw_deg: float | None = Field(default=None, ge=-180, le=180)
    pitch_deg: float | None = Field(default=None, ge=-180, le=180)
    roll_deg: float | None = Field(default=None, ge=-180, le=180)
    position_notes: str = Field(default="", max_length=2000)


class CollectionInput(BaseModel):
    scene_id: str | None = None
    deck_id: str
    mode: str = Field(default="silent", pattern="^(silent|voiced|paired)$")
    repetitions: int = Field(default=2, ge=1, le=10)
    visit_role: str = Field(default="train", pattern="^(train|validation|test|calibration)$")
    calibration_id: str | None = None
    distance_cm: float = Field(default=45, ge=10, le=200)
    position_notes: str = Field(default="", max_length=2000)
    location: str = Field(default="", max_length=120)
    enclosure: str = Field(default="", max_length=120)
    mount: str = Field(default="", max_length=120)
    yaw_deg: float | None = Field(default=None, ge=-180, le=180)
    pitch_deg: float | None = Field(default=None, ge=-180, le=180)
    roll_deg: float | None = Field(default=None, ge=-180, le=180)
    script_text: str | None = Field(default=None, max_length=200000)
    words_per_minute: int = Field(default=130, ge=50, le=300)


class CollectionRecord(BaseModel):
    reference_expected: bool = False
    step_id: str
    duration_s: float | None = Field(default=None, ge=.5, le=180)
    capture_method: str = Field(default="button", pattern="^(button|hold|reader|shortcut)$")
    reader_follow: str | None = Field(default=None, pattern="^(paced|manual|voice)$")
    reader_wpm: int | None = Field(default=None, ge=50, le=300)


class PlanInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    deck_id: str
    mode: str = Field(default="voiced", pattern="^(silent|voiced|paired)$")
    repetitions: int = Field(default=1, ge=1, le=10)
    visit_role: str = Field(default="train", pattern="^(train|validation|test|calibration)$")
    script_text: str | None = Field(default=None, max_length=200000)
    words_per_minute: int = Field(default=130, ge=50, le=300)


class DeleteCollection(BaseModel):
    confirm: bool = False


class CaptureEvent(BaseModel):
    name: str = Field(pattern="^(cue_shown|cue_finished|speech_start|speech_end|key_down|key_up|reader_marker)$")
    estimated_server_ns: int = Field(gt=0)
    uncertainty_ms: float = Field(ge=0, le=60000)
    word_index: int | None = Field(default=None, ge=0, le=100000)


class SessionInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject: str = Field(default="Boyd", min_length=1, max_length=80)
    notes: str = Field(default="", max_length=4000)
    collection: CollectionInput | None = None
    setup: SceneInput | None = None


class TrialInput(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    duration_s: float = Field(default=3, ge=0.5, le=30)
    articulation: str = Field(default="silent", pattern="^(silent|voiced|whisper|rest|negative)$")
    notes: str = Field(default="", max_length=4000)


class WordAnnotation(BaseModel):
    text: str = Field(min_length=1, max_length=200)
    start_s: float | None = Field(default=None, ge=0)
    end_s: float | None = Field(default=None, gt=0)
    source: str = Field(default="manual", pattern="^(manual|speech_estimate|acoustic_estimate|forced_alignment|alignment_import)$")


class TrialUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=200)
    accepted: bool | None = None
    notes: str | None = Field(default=None, max_length=4000)
    confirmed_text: str | None = Field(default=None, max_length=20000)
    utterance_start_s: float | None = Field(default=None, ge=0)
    utterance_end_s: float | None = Field(default=None, gt=0)
    words: list[WordAnnotation] | None = Field(default=None, max_length=3000)
    audio_offset_s: float | None = Field(default=None, ge=-600, le=600)
    base_revision: int | None = Field(default=None, ge=0)
    asr_raw_text: str | None = Field(default=None, max_length=20000)


class TrainInput(BaseModel):
    session_ids: list[str] = Field(min_length=2, max_length=50)
    test_session_ids: list[str] = Field(min_length=1, max_length=49)
    range_min_m: float = Field(default=0.2, ge=0, le=10)
    range_max_m: float = Field(default=0.85, gt=0, le=10)
    articulation: str | None = Field(default=None, pattern="^(silent|voiced|whisper)$")


class DecodeInput(BaseModel):
    model_id: str
    seconds: float = Field(default=3, ge=0.5, le=20)
    threshold: float = Field(default=0.65, ge=0, le=1)


class PredictTrialInput(BaseModel):
    model_id: str
    session_id: str
    trial_id: str
    threshold: float = Field(default=0.65, ge=0, le=1)


def create_app(data_root=None, research_enabled=False, app_token=None):
    store = Store(data_root or os.environ.get("GASP_DATA", "data"))
    engine = Engine(store)
    replay = Replay(store)
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="baseline-training")
    active_training = {}  # Job -> input IDs; guarded by engine.lock, including queued jobs.

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.close()
        learning.close()
        pool.shutdown(wait=True)

    app = FastAPI(title="Gasp", lifespan=lifespan)
    app.state.store, app.state.engine = store, engine
    app.state.research_enabled = research_enabled
    journey = register_journey(app, store, engine)
    learning = register_learning(app, store, engine, journey)

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "").split(":")[0]
        if host not in {"127.0.0.1", "localhost", "testserver"}:
            return JSONResponse({"detail": "Localhost access only"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin not in {f"http://{request.headers.get('host')}", "http://testserver"}:
            return JSONResponse({"detail": "Cross-origin access rejected"}, status_code=403)
        if app_token and request.url.path != "/desktop":
            supplied = request.cookies.get("gasp_app", "") or request.headers.get("authorization", "").removeprefix("Bearer ")
            if not hmac.compare_digest(supplied, app_token):
                return JSONResponse({"detail": "Open the installed Gasp app"}, status_code=403)
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

    @app.get("/training")
    def training_workspace():
        return FileResponse(STATIC / "training.html")

    @app.get("/desktop")
    def desktop(token: str = ""):
        if not app_token or not hmac.compare_digest(token, app_token):
            raise HTTPException(403, "Invalid app session")
        response = RedirectResponse("/training", status_code=303)
        response.set_cookie("gasp_app", app_token, httponly=True, samesite="strict")
        return response

    @app.get("/api/decks")
    def decks():
        return DECKS

    @app.get("/api/plans")
    def saved_plans():
        return store.plans()

    def plan_from_definition(body, raw=False):
        script = body.script_text
        if raw and body.deck_id == "reader":
            limit = max(10, int(body.words_per_minute * 18 / 60))
            words = (script or "").split()
            script = "\n\n".join(" ".join(words[i:i+limit]) for i in range(0, len(words), limit))
        plan = make_plan(body.deck_id, body.mode, body.repetitions,
                         script_text=script, words_per_minute=body.words_per_minute)
        if raw and body.deck_id == "reader":
            for step in plan["steps"]:
                step["duration_s"] = 25
        return plan

    @app.post("/api/plans/preview")
    def preview_plan(body: PlanInput, raw: bool = False):
        return plan_from_definition(body, raw)

    @app.post("/api/plans")
    def save_plan(body: PlanInput):
        if not body.name.strip():
            raise ValueError("Give the plan a name")
        plan = plan_from_definition(body)
        value = body.model_dump()
        value.update(name=body.name.strip(), repetitions=plan["repetitions"],
                     visit_role="calibration" if plan["calibration"] else body.visit_role)
        return store.save_plan(value)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__, "data_root": str(store.root),
                "hardware_verified": False, "transcription_enabled": False, "research_predictions_enabled": research_enabled, "server_monotonic_ns": time.monotonic_ns()}

    @app.get("/api/clock")
    def clock_sync():
        return {"monotonic_ns": time.monotonic_ns(), "wall_ns": time.time_ns()}

    @app.get("/api/ports")
    def list_ports():
        return ports()

    @app.get("/api/profiles")
    def profiles():
        return [dict(name=n, **bundled_profile(n).summary()) for n in ("usb-phase-20hz", "usb-phase-10hz", "usb-doppler-10hz", "usb-spatial-2hz", "dca-raw")]

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

    @app.get("/api/blocks")
    def blocks():
        # Reader documents can be large. The library needs summaries, not every script word.
        return collection_summaries(store.sessions())

    def collection_summaries(result):
        for session in result:
            if session.get("collection"):
                plan = session["collection"]["plan"]
                session["collection"] = {k:v for k,v in session["collection"].items() if k != "script_text"}
                session["collection"]["plan"] = {k:v for k,v in plan.items() if k not in {"script_text", "steps"}}
        return result

    @app.get("/api/discarded-collections")
    def discarded_collections():
        return sorted(collection_summaries(store.sessions(discarded=True)),
                      key=lambda s: s["discarded_ns"], reverse=True)

    @app.post("/api/sessions/{sid}/discard")
    def discard_collection(sid: str):
        with engine.lock:
            if engine.recording and engine.session and engine.session["id"] == sid:
                raise ValueError("Finish the active recording before discarding this collection")
            if any(sid in ids for ids in active_training.values()) or learning.active_for(sid):
                raise ValueError("Wait for training that uses this collection to finish before discarding it")
            store.set_discarded(sid, True)
            if engine.session and engine.session["id"] == sid:
                engine.session = None
            if engine.last_trial and engine.last_trial.get("session_id") == sid:
                engine.last_trial = None
        return {"id": sid, "discarded": True}

    @app.post("/api/sessions/{sid}/restore")
    def restore_collection(sid: str):
        with engine.lock:
            store.set_discarded(sid, False)
        return {"id": sid, "discarded": False}

    @app.delete("/api/sessions/{sid}")
    def delete_collection(sid: str, body: DeleteCollection):
        if not body.confirm:
            raise ValueError("Confirm permanent deletion of this collection and its recordings")
        with engine.lock:
            if engine.recording and engine.session and engine.session["id"] == sid:
                raise ValueError("Finish the active recording before deleting this collection")
            if any(sid in ids for ids in active_training.values()) or learning.active_for(sid):
                raise ValueError("Wait for training that uses this collection to finish before deleting it")
            store.delete_session(sid)
            learning.source_deleted(sid)
            replay.forget_session(sid)
            if engine.session and engine.session["id"] == sid:
                engine.session = None
            if engine.last_trial and engine.last_trial.get("session_id") == sid:
                engine.last_trial = None
        return {"id": sid, "deleted": True}

    @app.get("/api/scenes")
    def scenes():
        return store.scenes()

    @app.post("/api/scenes")
    def new_scene(body: SceneInput):
        setup = body.model_dump()
        setup.update(name=body.name.strip(), subject=body.subject.strip())
        if not setup["name"] or not setup["subject"]:
            raise ValueError("Give this scene a name and a person")
        return store.create_scene(setup)

    @app.post("/api/sessions")
    def new_session(body: SessionInput):
        # Keep source/profile validation and setup creation in one acquisition transaction.
        with engine.lock:
            return start_collection(body)

    def start_collection(body: SessionInput):
        if body.setup:
            if not body.collection or body.collection.scene_id:
                raise ValueError("Choose a saved setup or supply a new setup, not both")
            if not body.setup.name.strip() or body.setup.subject.strip() != body.subject:
                raise ValueError("The setup and collection must name the same person")
            if body.collection.calibration_id:
                raise ValueError("A new setup needs its own calibration")
        collection = None
        if body.collection:
            c = body.collection
            plan = plan_from_definition(c, bool(engine.profile and engine.profile.lvds_adc))
            if plan["calibration"] and c.visit_role != "calibration":
                raise ValueError("Calibration decks must use the calibration role")
            if c.calibration_id:
                previous = store.session(c.calibration_id)
                if not previous.get("collection", {}).get("plan", {}).get("calibration"):
                    raise ValueError("Choose a calibration session")
                if c.scene_id and previous["collection"].get("scene_id") != c.scene_id:
                    raise ValueError("Use a calibration recorded in this setup")
                if not engine.source or (previous["subject"], previous["source"], previous["profile"]["sha256"]) != (
                    body.subject, getattr(engine.source, "kind", "simulator" if engine.source.synthetic else "serial"), engine.profile.sha256):
                    raise ValueError("Calibration participant, source and profile must match this session")
                if not any(t.get("accepted") for t in store.trials(c.calibration_id)):
                    raise ValueError("Review calibration takes before linking this reference")
            collection = dict(c.model_dump(), plan=plan)
            if c.scene_id:
                scene = store.scene(c.scene_id)
                if scene["subject"] != body.subject:
                    raise ValueError("This setup belongs to a different person. Choose a different setup for them.")
                collection.update({k: v for k, v in scene.items() if k not in {"id", "created_ns", "name", "subject"}})
                collection.update(scene_name=scene["name"], scene_snapshot=scene)
        created_scene = None
        if body.setup:
            if engine.recording or not engine.source or engine.status != "connected":
                raise ValueError("Connect the radar and finish the current take before starting")
            setup = body.setup.model_dump()
            setup.update(name=body.setup.name.strip(), subject=body.setup.subject.strip())
            created_scene = store.create_scene(setup)
            collection.update({k: v for k, v in created_scene.items() if k not in {"id", "created_ns", "name", "subject"}})
            collection.update(scene_id=created_scene["id"], scene_name=created_scene["name"], scene_snapshot=created_scene)
        try:
            return engine.create_session(body.name, body.subject, body.notes, collection)
        except Exception:
            # A failed start must not leave a saved setup with no collection.
            if created_scene:
                (store.root / "scenes" / (created_scene["id"] + ".json")).unlink(missing_ok=True)
            raise

    @app.get("/api/sessions/{sid}")
    def get_session(sid: str):
        return store.session(sid)

    @app.post("/api/sessions/{sid}/resume")
    def resume_session(sid: str):
        with engine.lock:
            session = store.session(sid)
            if engine.recording or not engine.source or engine.status != "connected":
                raise ValueError("Connect the matching source and finish the current take first")
            kind = getattr(engine.source, "kind", "simulator" if engine.source.synthetic else "serial")
            if (session["source"], session["profile"]["sha256"]) != (kind, engine.profile.sha256):
                profile_label = next((p["name"] for p in profiles() if p["sha256"] == session["profile"]["sha256"]), "custom " + session["profile"]["sha256"][:8])
                raise ValueError(f"This collection used {session['source']} with profile {profile_label}. Choose those in Radar settings to resume, or start another collection with the current setup.")
            engine.session = session
            engine.last_trial = None
        return session

    @app.post("/api/collect")
    def collect(body: CollectionRecord):
        with engine.lock:
            if not engine.session:
                raise ValueError("Create a collection session first")
            step, extra = store.collection_record(engine.session["id"], body.step_id)
            if engine.session["collection"]["plan"].get("free_capture") and not body.reference_expected:
                raise ValueError("Enable the reference microphone for free capture")
            if engine.session["collection"].get("type_id") and not engine.session["synthetic"] and step["articulation"] == "voiced" and not body.reference_expected:
                raise ValueError("Enable the reference microphone in Settings for this aloud reference")
            extra["reference_expected"] = body.reference_expected
            extra.update(capture_method=body.capture_method, reader_follow=body.reader_follow, reader_wpm=body.reader_wpm)
            limit = capture_limit(step, engine.session["source"] == "dca1000")
            return engine.record(step["target_text"] or "[untranscribed speech]", body.duration_s or limit, step["articulation"], "", extra)

    @app.get("/api/sessions/{sid}/trials")
    def trials(sid: str):
        store.session(sid)
        return store.trials(sid)

    @app.get("/api/recordings")
    def recording_library():
        keys = {"id","session_id","prompt_text","label","articulation","review_status","created_ns",
                "synthetic","duration_s","frames","accepted","capture_conditions"}
        return sorted([dict({k:v for k,v in t.items() if k in keys}, session_name=s["name"], subject=s["subject"], profile_sha256=s["profile"]["sha256"])
                       for s in store.sessions() for t in store.trials(s["id"])], key=lambda t:t["created_ns"], reverse=True)

    @app.get("/api/sessions/{sid}/trials/{tid}")
    def get_trial(sid: str, tid: str):
        return json.loads((store.trial_dir(sid,tid)/"trial.json").read_text())

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

    @app.post("/api/record/{rid}/stop")
    def stop_record(rid: str):
        return engine.stop_record(rid)

    @app.post("/api/record/{rid}/events")
    def capture_event(rid: str, body: CaptureEvent):
        return engine.add_event(rid, body.model_dump())

    @app.post("/api/record/{rid}/cancel")
    def cancel_record(rid: str):
        checked_id(rid)
        return engine.cancel_record(rid)

    @app.patch("/api/sessions/{sid}/trials/{tid}")
    def update_trial(sid: str, tid: str, body: TrialUpdate):
        session = store.session(sid)
        collection = session.get("collection", {})
        if body.accepted and collection.get("definition", {}).get("template") == "baseline":
            take = json.loads((store.trial_dir(sid, tid) / "trial.json").read_text())
            step = next(s for s in collection["plan"]["steps"] if s["step_id"] == take["plan_step_id"])
            if not session["synthetic"] and step["articulation"] == "voiced" and not take.get("media"):
                raise ValueError("This aloud reference has no audio. Reject it and record again with the microphone enabled.")
            if capture_mode(step) == "timed" and take.get("capture_duration_s", take["duration_s"]) < .8 * step["duration_s"]:
                raise ValueError("This timed reference is too short. Reject it and record the full countdown again.")
            normalize = lambda text: re.sub(r"[^\w]+", " ", text.casefold()).strip()
            if step["articulation"] not in {"rest", "negative"} and normalize(body.confirmed_text or take.get("confirmed_text") or "") != normalize(step["target_text"]):
                raise ValueError("This baseline take needs the prompted text. Save a draft or reject the take, then record it again.")
        if body.accepted and collection.get("plan", {}).get("free_capture"):
            take = json.loads((store.trial_dir(sid, tid) / "trial.json").read_text())
            if not take.get("media") or (body.confirmed_text or take.get("confirmed_text")) in {None, "", "[untranscribed speech]", "Speak in your own words."}:
                raise ValueError("Free capture needs reference audio and a reviewed transcript")
        return store.update_trial(sid, tid, body.model_dump(exclude_none=True))

    @app.get("/api/sessions/{sid}/trials/{tid}/quality")
    def take_quality(sid: str, tid: str):
        from .audio_review import inspect_take
        return inspect_take(store, sid, tid)

    @app.post("/api/sessions/{sid}/trials/{tid}/suggest-timing")
    def suggest_timing(sid: str, tid: str, body: dict):
        from .audio_review import analyze_audio, acoustic_words, propose_words, is_control, is_syllable_exercise, processing_window
        path = store.trial_dir(sid, tid)
        take = json.loads((path/"trial.json").read_text())
        if is_control(take) or take.get("articulation") == "silent":
            return {"words":[], "placed":0, "recognition_allowed":False, "message":"This take does not use audio word alignment."}
        text = body.get("text") or take.get("confirmed_text") or take.get("target_text") or ""
        if not isinstance(text, str) or len(text) > 20000:
            raise ValueError("Invalid transcript")
        offset = float(body.get("audio_offset_s", 0))
        if not np.isfinite(offset) or abs(offset)>600:
            raise ValueError("Invalid audio offset")
        recognized = body.get("recognized", [])
        if not isinstance(recognized,list) or len(recognized)>3000 or any(not isinstance(w,dict) for w in recognized):
            raise ValueError("Invalid recognition result")
        start = processing_window(take)['start_s']
        recognized = [w for w in recognized if float(w.get('start_s', w.get('start', 0))) >= start]
        syllables = is_syllable_exercise(take)
        words = propose_words(text, [] if syllables else recognized, offset, take['duration_s'])
        message = "Matched words have draft timing. Unmatched words remain unplaced."
        if syllables and take.get('media',{}).get('file','').endswith('.wav'):
            acoustic = acoustic_words(text, analyze_audio(path/take['media']['file'], start), offset, take['duration_s'], take.get('prompt_text'))
            if acoustic:
                words = acoustic
                message = "Draft boundaries from sound bursts. Listen and adjust before keeping."
        return {"words":words,"message":message,"placed":sum(w.get('start_s') is not None for w in words),
                "kind":"syllables" if syllables else "speech", "recognition_allowed":not syllables}

    @app.get("/api/sessions/{sid}/trials/{tid}/signal")
    def trial_signal(sid: str, tid: str):
        arr = store.load_signal(sid, tid)
        z, t = arr["iq"], arr["timestamps_ns"]
        selected = min(8, z.shape[1]-1)
        phase = np.unwrap(np.angle(z[:, selected, 0]))
        return {"time_s": ((t-t[0])/1e9).tolist(), "phase": (phase-phase[0]).tolist(),
                "range_magnitude": np.abs(z).mean(axis=(0, 2)).tolist(), "shape": list(z.shape)}

    @app.get("/api/sessions/{sid}/trials/{tid}/replay")
    def trial_replay(sid: str, tid: str, range_bin: int = 8, antenna: int = 0):
        return replay.preview(sid,tid,range_bin,antenna)

    @app.get("/api/sessions/{sid}/trials/{tid}/frame")
    def trial_frame(sid: str, tid: str, index: int = 0):
        return replay.frame(sid,tid,index)

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
        if request.headers.get("content-type", "").split(";")[0] not in ("video/webm", "audio/webm", "video/mp4", "audio/wav"):
            raise ValueError("Expected a browser WebM/MP4 recording")
        suffix = ".wav" if request.headers.get("content-type", "").startswith("audio/wav") else ".mp4" if request.headers.get("content-type", "").startswith("video/mp4") else ".webm"
        target = path / ("reference" + suffix)
        # Validate metadata before creating a file. Retries must be safe even if
        # the prior request committed the WAV but its response/manifest failed.
        audio_timing = None
        if request.headers.get("x-audio-timing"):
            try:
                audio_timing = json.loads(request.headers["x-audio-timing"],
                                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
                if not isinstance(audio_timing, dict):
                    raise ValueError("Expected an object")
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid audio timing metadata") from exc
        tmp = path / (uuid.uuid4().hex + ".upload")
        count, digest = 0, hashlib.sha256()
        try:
            with tmp.open("xb") as f:
                async for chunk in request.stream():
                    count += len(chunk)
                    if count > 256*1024*1024:
                        raise ValueError("Reference media exceeds 256 MiB")
                    f.write(chunk)
                    digest.update(chunk)
                f.flush()
                os.fsync(f.fileno())
            if not count:
                raise ValueError("Reference recording is empty")
            media_fields = {"file": target.name, "bytes": count, "sha256": digest.hexdigest(),
                "browser_start_server_ns": request.headers.get("x-media-start-server-ns"),
                "clock_uncertainty_ms": request.headers.get("x-clock-uncertainty-ms"),
                "native_audio_timing": audio_timing,
                "synchronization": "AVAudioEngine host/sample timestamps; software radar anchor, not hardware synchronized"
                    if audio_timing else "Browser/software timestamps only; not hardware synchronized"}
            with store.lock:
                meta = json.loads(meta_path.read_text())
                existing = meta.get("media")
                if existing and existing != media_fields:
                    raise ValueError("A different reference recording already exists; the original is preserved")
                if target.exists():
                    with target.open("rb") as original:
                        if hashlib.file_digest(original, "sha256").hexdigest() != digest.hexdigest():
                            raise ValueError("A different reference recording already exists; the original is preserved")
                else:
                    os.replace(tmp, target)
                if not existing:
                    store.add_trial_fields(sid, tid, {"media": media_fields})
            return media_fields
        finally:
            tmp.unlink(missing_ok=True)

    @app.get("/api/sessions/{sid}/trials/{tid}/media")
    def get_media(sid: str, tid: str, processing: bool = False):
        path = store.trial_dir(sid, tid)
        meta = json.loads((path/"trial.json").read_text())
        if not meta.get("media"):
            raise HTTPException(404, "No reference media")
        if processing and meta['media']['file'].endswith('.wav'):
            import io
            import warnings
            from scipy.io import wavfile
            from .audio_review import processing_window
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', wavfile.WavFileWarning)
                rate, samples = wavfile.read(path / meta['media']['file'])
            first = min(len(samples), int(np.ceil(processing_window(meta)['start_s']*rate)))
            if first == len(samples):
                raise ValueError('No audio remains after the start cue. Record a longer take.')
            buffer = io.BytesIO()
            wavfile.write(buffer, rate, samples[first:])
            return Response(buffer.getvalue(), media_type='audio/wav',
                headers={'X-Audio-Processing-Start-S':str(first/rate)})
        return FileResponse(path / meta["media"]["file"])

    @app.post("/api/train")
    def launch_train(body: TrainInput):
        jid = uuid.uuid4().hex
        job_path = store.root / "jobs" / (jid + ".json")
        with engine.lock:
            for sid in body.session_ids:
                store.session(sid)  # Reject discarded inputs before enqueueing a job.
            atomic_json(job_path, {"id": jid, "status": "queued"})
            active_training[jid] = set(body.session_ids)
        def work():
            try:
                atomic_json(job_path, {"id": jid, "status": "running"})
                report = training.train(store, body.session_ids, body.test_session_ids,
                    FeatureSpec(range_min_m=body.range_min_m, range_max_m=body.range_max_m), articulation=body.articulation)
                atomic_json(job_path, {"id": jid, "status": "complete", "report": report})
            except Exception as exc:
                atomic_json(job_path, {"id": jid, "status": "failed", "error": str(exc)})
            finally:
                with engine.lock:
                    active_training.pop(jid, None)
        try:
            pool.submit(work)
        except Exception:
            with engine.lock:
                active_training.pop(jid, None)
            raise
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
        if not research_enabled:
            raise HTTPException(403, "Predictions are disabled in this training-first release")
        return training.predict_trial(store, body.model_id, body.session_id, body.trial_id, body.threshold)

    @app.post("/api/decode")
    def decode(body: DecodeInput):
        if not research_enabled:
            raise HTTPException(403, "Transcription is disabled; collect and review training data first")
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
