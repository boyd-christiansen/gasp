"""Immutable collection recipes and an evidence-based personal onboarding journey.

Completion is computed from reviewed recordings, never from a client-side checkbox.
The baseline is an engineering starting point, not a claim of dictation readiness.
"""
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

from pydantic import BaseModel, Field
from .collection import make_plan, capture_mode
from .storage import atomic_json, checked_id
from .profile import bundled_profile

VERSION = "personal-baseline-1"
SENTENCES = Path(__file__).with_name("baseline_sentences.txt").read_text().splitlines()
PHRASES = ["add a note", "save this note", "new paragraph", "undo that",
           "next item", "cancel that", "open the document", "close the window"]
BASELINE = [
    dict(id="calibration", name="Personal calibration", description="Find a clear signal and a comfortable position.", total=12, minutes="About 5 minutes", role="calibration", template="baseline"),
    dict(id="first-speech", name="First speech", description="Short phrases, then everyday sentences.", total=220, minutes="About 25–35 minutes", role="train", template="baseline"),
    dict(id="return-repeat", name="Return & repeat", description="A fresh sitting, with new sentences.", total=120, minutes="About 15–25 minutes", role="validation", template="baseline"),
    dict(id="independent-check", name="Independent check", description="Set aside a fresh sample to measure progress.", total=120, minutes="About 15–25 minutes", role="test", template="baseline"),
]


class Setup(BaseModel):
    subject: str = Field(default="Boyd", min_length=1, max_length=80)
    location: str = Field(default="", max_length=120)
    distance_cm: float = Field(default=45, ge=10, le=200)
    enclosure: str = Field(default="", max_length=120)
    mount: str = Field(default="", max_length=120)
    yaw_deg: float | None = Field(default=None, ge=-180, le=180)
    pitch_deg: float | None = Field(default=None, ge=-180, le=180)
    roll_deg: float | None = Field(default=None, ge=-180, le=180)
    position_notes: str = Field(default="", max_length=2000)


class Preferences(BaseModel):
    setup: Setup = Field(default_factory=Setup)
    connection: dict[str, str] = Field(default_factory=dict)
    reference_audio: bool = False


class Recipe(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    template: str = Field(pattern="^(reader|phrases|sentences|pose|free)$")
    content: str = Field(default="", max_length=200000)
    source_text: str = Field(default="", max_length=500)
    distances: list[float] = Field(default_factory=lambda: [35, 45, 55], min_length=1, max_length=10)


class Start(BaseModel):
    setup: Setup
    reseated: bool = False


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def baseline_plan(key):
    index = next(i for i, b in enumerate(BASELINE) if b["id"] == key)
    if index == 0:
        plan = make_plan("calibration-v1", mode="voiced", repetitions=1, seed=VERSION)
    else:
        steps = []

        def add(text, mode, group, pair=None, duration=8, instruction=""):
            n = len(steps)
            steps.append(dict(step_id=f"{key}-{n:03d}", prompt_id=f"{group}-{digest(text)[:12]}",
                              prompt_text=text, target_text=text, duration_s=duration,
                              articulation=mode, instruction=instruction, repetition=1,
                              pair_id=pair, training_task=group))

        # A voiced reference immediately precedes silent repeats of each phrase.
        for i, text in enumerate(PHRASES):
            pair = f"{key}-phrase-{i}"
            add(text, "voiced", "benchmark", pair, 6)
            for _ in range(10 if index == 1 else 5):
                add(text, "silent", "benchmark", pair, 6)
        start, end = [(0, 0), (0, 60), (60, 90), (90, 120)][index]
        for i, text in enumerate(SENTENCES[start:end], start):
            for mode in ("voiced", "silent"):
                add(text, mode, "sentence", f"{key}-sentence-{i}", 12)
        for mode, text, target in [
            ("rest", "Sit comfortably and stay still.", "[rest]"),
            ("negative", "Look left, look right, then return to the screen.", "[head turn]"),
            ("negative", "Swallow once, then sit still.", "[swallow]"),
            ("negative", "Type naturally for a few seconds without speaking.", "[typing]"),
        ]:
            for _ in range(3):
                add(text, mode, "control", duration=8, instruction="Do not speak.")
                steps[-1]["target_text"] = target
        plan = dict(protocol=VERSION, deck_id=key, deck_name=BASELINE[index]["name"], calibration=False,
                    mode="paired", repetitions=1, seed=VERSION, steps=steps, task="baseline",
                    words_per_minute=130, script_text=None, script_sha256=None)
    plan["protocol"] = VERSION
    for i, step in enumerate(plan["steps"]):
        step["step_id"] = f"{key}-{i:03d}"
        step["capture_mode"] = capture_mode(step)
    assert len(plan["steps"]) == BASELINE[index]["total"]
    return plan


def custom_plan(recipe, raw=False):
    template, text = recipe["template"], recipe.get("content", "")
    if template == "free":
        plan = make_plan("custom-words", "voiced", 1, script_text="Speak in your own words.")
        plan.update(task="reading", free_capture=True)
        plan["steps"][0].update(duration_s=25 if raw else 180, target_text="", instruction="Record aloud, then confirm the words you said in review.")
        return plan
    if template == "reader" and raw:
        tokens = text.split()
        text = "\n\n".join(" ".join(tokens[i:i+35]) for i in range(0, len(tokens), 35))
    plan = make_plan("reader" if template == "reader" else "custom-words", "paired", 1, script_text=text)
    if raw:
        for step in plan["steps"]:
            step["duration_s"] = min(25, step["duration_s"])
    if template == "pose":
        steps = []
        for distance in recipe["distances"]:
            pairs = {}
            for original in plan["steps"]:
                step = dict(original, step_id=uuid.uuid4().hex, distance_cm=distance)
                step["pair_id"] = pairs.setdefault(original["pair_id"], uuid.uuid4().hex)
                step["instruction"] = f"Set your face {distance:g} cm from the radar before recording."
                steps.append(step)
        plan["steps"] = steps
    return plan


def register_journey(app, store, engine):
    recipes = store.root / "collections"
    recipes.mkdir(exist_ok=True)
    prefs_path = store.root / "preferences.json"

    def preferences():
        return Preferences.model_validate(json.loads(prefs_path.read_text()) if prefs_path.exists() else {}).model_dump()

    def definitions():
        fixed = [dict(b, version=VERSION, definition_sha256=digest(baseline_plan(b["id"]))) for b in BASELINE]
        return fixed + sorted([json.loads(p.read_text()) for p in recipes.glob("*.json")], key=lambda x:x["created_ns"])

    def cohort(subject, source, profile):
        return digest([subject.strip(), source, profile, VERSION])[:24]

    def progress(subject, source, profile):
        key = cohort(subject, source, profile)
        records = [s for s in store.sessions() if s.get("collection", {}).get("cohort_id") == key]
        result = []
        preceding = True
        for b in BASELINE:
            matching = [s for s in records if s["collection"].get("type_id") == b["id"]]
            expected = {s["step_id"]: s for s in baseline_plan(b["id"])["steps"]}
            recorded, verified = set(), set()
            norm = lambda value: re.sub(r"[^\w]+", " ", value.casefold()).strip()
            for session in matching:
                for t in store.trials(session["id"]):
                    step = expected.get(t.get("plan_step_id"))
                    if step and t.get("review_status") != "rejected":
                        recorded.add(t["plan_step_id"])
                    if not step or not t.get("accepted") or t.get("review_status") != "verified":
                        continue
                    if step["articulation"] not in {"rest", "negative"} and norm(t.get("confirmed_text") or "") != norm(step["target_text"]):
                        continue
                    if capture_mode(step) == "timed" and t.get("capture_duration_s", t["duration_s"]) < step["duration_s"] * .8:
                        continue
                    verified.add(t["plan_step_id"])
            complete = len(verified) == b["total"]
            result.append(dict(id=b["id"], recorded=len(recorded), verified=len(verified), total=b["total"], complete=complete,
                               unlocked=preceding, sessions=[s["id"] for s in matching]))
            preceding = preceding and complete
        return dict(cohort_id=key, steps=result, complete=preceding, synthetic=source == "simulator")

    @app.get("/api/preferences")
    def get_preferences():
        return preferences()

    @app.put("/api/preferences")
    def put_preferences(body: Preferences):
        if not body.setup.subject.strip():
            raise ValueError("Enter a person’s name")
        value = body.model_dump()
        value["setup"]["subject"] = body.setup.subject.strip()
        # Persist only connection preferences, never credentials or arbitrary state.
        value["connection"] = {k:v[:200] for k,v in value["connection"].items()
                               if k in {"source", "profile", "cliPort", "dataPort", "hostIp", "boardIp"}}
        atomic_json(prefs_path, value)
        return value

    @app.get("/api/journey")
    def journey(subject: str = "Boyd", source: str = "serial", profile: str = ""):
        return dict(collections=definitions(), progress=progress(subject, source, profile))

    @app.get("/api/collections/{cid}")
    def definition(cid: str):
        checked_id(cid)
        recipe = next((d for d in definitions() if d["id"] == cid), None)
        if not recipe:
            raise ValueError("Unknown collection")
        plan = baseline_plan(cid) if recipe["template"] == "baseline" else custom_plan(recipe)
        return dict(recipe, plan=plan)

    @app.post("/api/collections")
    def create_recipe(body: Recipe):
        pref = preferences()
        connection = engine.snapshot()
        if connection["status"] != "connected":
            saved = pref["connection"]
            connection = dict(source=saved.get("source", "serial"),
                              profile=bundled_profile(saved.get("profile", "usb-phase-20hz")).summary())
        # New recipes are unlocked by this person's reviewed baseline in this cohort.
        if not progress(pref["setup"]["subject"], connection["source"], (connection["profile"] or {}).get("sha256", ""))["complete"]:
            raise ValueError("Finish your guided baseline before creating a collection type")
        if not body.name.strip() or (body.template != "free" and not body.content.strip()):
            raise ValueError("Add a name and collection text")
        if any(not 10 <= d <= 200 for d in body.distances):
            raise ValueError("Use distances between 10 and 200 cm")
        value = dict(body.model_dump(), name=body.name.strip(), version=1, id=uuid.uuid4().hex, created_ns=time.time_ns())
        custom_plan(value)  # Validate before saving an immutable definition.
        value["definition_sha256"] = digest(value)
        atomic_json(recipes / (value["id"] + ".json"), value)
        return value

    @app.post("/api/collections/{cid}/sessions")
    def start_session(cid: str, body: Start):
        with engine.lock:
            live = engine.snapshot()
            if live["status"] != "connected" or engine.recording:
                raise ValueError("Connect your radar and finish the current take first")
            recipe = definition(cid)
            setup = body.setup.model_dump()
            setup["subject"] = setup["subject"].strip()
            if not setup["subject"]:
                raise ValueError("Enter a person’s name")
            journey = progress(setup["subject"], live["source"], live["profile"]["sha256"])
            baseline = recipe["template"] == "baseline"
            if baseline:
                step = next(s for s in journey["steps"] if s["id"] == cid)
                if not step["unlocked"]:
                    raise ValueError("Record and review the previous baseline step first")
                if cid in {"return-repeat", "independent-check"} and not body.reseated:
                    raise ValueError("For this independent sitting, step away and reseat before you begin")
                plan = recipe.pop("plan")
            else:
                if not journey["complete"]:
                    raise ValueError("Finish your guided baseline in this radar profile first")
                if recipe.get("role") in {"validation", "test"} and not body.reseated:
                    raise ValueError("Step away and reseat before an independent evaluation sitting")
                recipe.pop("plan")
                plan = custom_plan(recipe, live["source"] == "dca1000")
            # Pair identity includes the acquisition cohort and role; repeat takes stay together.
            for s in plan["steps"]:
                if s.get("pair_id"):
                    s["pair_id"] = journey["cohort_id"] + "-" + s["pair_id"]
            collection = dict(setup, type_id=cid, definition=recipe, definition_version=recipe["version"],
                              cohort_id=journey["cohort_id"], plan=plan, visit_role=recipe.get("role", "train"),
                              reseated=body.reseated, acquisition_id=uuid.uuid4().hex,
                              scene_snapshot=setup, scene_name=setup["location"] or "Usual setup")
            return engine.create_session(recipe["name"], setup["subject"], "", collection)

    return dict(progress=progress, definitions=definitions)
