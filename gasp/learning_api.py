"""The collect / train / evaluate workspace API."""
import json
from pathlib import Path
import time
import uuid
import zipfile

from fastapi import Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import learning_data as data
from .learning_runs import Runs, ACTIVE
from .storage import atomic_json, checked_id


class Scope(BaseModel):
    subject: str = Field(min_length=1, max_length=80)
    source: str = Field(pattern="^(serial|simulator|dca1000)$")
    profile: str = Field(min_length=1, max_length=100)
    recipe_id: str = Field(default="phrase-v2", pattern="^(phrase-v2|radar-ctc-v1)$")
    include_voiced: bool = False
    exclude_sessions: list[str] = Field(default_factory=list, max_length=2000)


class FinalCheck(BaseModel):
    confirm: bool = False


class Assignment(Scope):
    content: str = Field(default="", max_length=200000)
    name: str = Field(default="Sentence practice", min_length=1, max_length=120)
    purpose: str = Field(default="train", pattern="^(train|validation|test)$")


MILESTONES = [dict(id="pilot", name="Sentence pilot", seconds=1800),
    dict(id="curve", name="First learning curve", seconds=7200),
    dict(id="personal", name="Personal corpus", seconds=18000),
    dict(id="expand", name="Expanded corpus", seconds=36000)]


def headline(result):
    """Silent recognition is the target; do not pool in easier voiced examples."""
    modes = result.get("by_mode", {})
    if (result.get("metrics") or {}).get("wer") is not None:
        return modes.get("silent")
    return result.get("metrics")


def register_learning(app, store, engine, journey):
    runs = Runs(store)
    app.state.learning_runs = runs

    def inspect(scope):
        recipe = data.RECIPES[scope.recipe_id]
        return data.inventory(store, scope.subject, scope.source, scope.profile, recipe["task"],
                              scope.include_voiced, scope.exclude_sessions)

    @app.get("/api/learning")
    def overview(subject: str = "Boyd", source: str = "serial", profile: str = ""):
        phrase = data.inventory(store, subject, source, profile)
        sentence = data.inventory(store, subject, source, profile, "sentences")
        progress = journey["progress"](subject, source, profile)
        history = runs.list(data.cohort_key(subject, source, profile))
        pending = [r for r in phrase["excluded"] + sentence["excluded"] if r["reason"] == "Needs review"]
        next_step = next((s for s in progress["steps"] if s["unlocked"] and not s["complete"]), None)
        if pending:
            recommendation = dict(kind="review", title="Review your recordings", description=f"{len(pending)} takes need a check before they can be used.",
                                  session_id=pending[0]["session_id"], trial_id=pending[0]["trial_id"])
        elif next_step:
            definition = next(d for d in journey["definitions"]() if d["id"] == next_step["id"])
            recommendation = dict(kind="collection", title=definition["name"], description=definition["description"], collection_id=definition["id"])
        else:
            recommendation = dict(kind="practice", title="Add a sentence session", description="New text, the same comfortable setup. About 10–15 minutes.")
        seconds = sentence["counts"]["train"]["silent_seconds"]
        milestone = next((m for m in MILESTONES if seconds < m["seconds"]), MILESTONES[-1])
        return dict(cohort=phrase["cohort"], baseline=progress, recommendation=recommendation,
            phrase={k: v for k, v in phrase.items() if k != "rows"},
            sentence={k: v for k, v in sentence.items() if k != "rows"},
            milestones=MILESTONES, milestone=milestone, runs=[{k: v for k, v in r.items() if k not in {"result", "events"}} |
                {"development": headline(r.get("result", {}).get("development", {})),
                 "final_test": headline(r.get("result", {}).get("final_test", {}))} for r in history],
            destinations=[dict(id="local", name="This Mac", available=True, description="Phrase checks · CPU"),
                dict(id="package", name="Personal rack", available=False,
                    description="Prepare a portable job. Live scheduler connection has not been configured.")])

    @app.post("/api/learning/inspect")
    def inspect_dataset(body: Scope):
        return inspect(body)

    @app.post("/api/learning/runs")
    def launch(body: Scope):
        with engine.lock, store.lock:
            if engine.recording:
                raise ValueError("Finish the current take before preparing training")
            if any(r["status"] in ACTIVE for r in runs.list()):
                raise ValueError("A run is already active. Wait for it or cancel it first.")
            snapshot = data.freeze(store, inspect(body), body.recipe_id)
            return runs.start(snapshot)

    @app.get("/api/learning/runs/{rid}")
    def run(rid: str):
        return runs.get(rid)

    @app.get("/api/learning/datasets/{sid}")
    def snapshot(sid: str):
        value = data.load_snapshot(store, sid)
        return {**value, "availability": data.availability(store, value)}

    @app.post("/api/learning/runs/{rid}/cancel")
    def cancel(rid: str):
        return runs.cancel(rid)

    @app.post("/api/learning/runs/{rid}/retry")
    def retry(rid: str):
        with engine.lock:
            if engine.recording or any(r["status"] in ACTIVE for r in runs.list()):
                raise ValueError("Finish the active recording or training run first")
            return runs.retry(rid)

    @app.post("/api/learning/runs/{rid}/final-check")
    def final_check(rid: str, body: FinalCheck):
        if not body.confirm:
            raise ValueError("Freeze this candidate and confirm the final check")
        with engine.lock, store.lock:
            previous = runs.get(rid)
            if previous["status"] != "complete" or previous["kind"] != "fit":
                raise ValueError("Select a completed training run")
            if engine.recording or any(r["status"] in ACTIVE for r in runs.list()):
                raise ValueError("Finish the active recording or training run first")
            before = data.load_snapshot(store, previous["dataset_id"])
            scope = Scope(**{k: before["cohort"][k] for k in ("subject", "source", "profile")},
                          recipe_id=previous["recipe"]["id"], include_voiced=before["include_voiced"])
            current = inspect(scope)
            tests = [r for r in current["rows"] if r["split"] == "test"]
            if not tests:
                raise ValueError("Review the Independent check recordings first")
            # Check new test material against the actual fitted/selected data, not just today's inventory.
            errors = data.leakage_errors([r for r in before["rows"] if r["split"] != "test"] + tests, before["task"])
            if errors:
                raise ValueError(errors[0])
            if any(r["parent_id"] == rid and r["kind"] == "final" and r["status"] not in {"failed", "cancelled", "interrupted"}
                   for r in runs.list()):
                raise ValueError("This candidate already has a final check. Open that result.")
            # A fixed model can be evaluated even if its training sources were deleted.
            # Freeze only the test inputs, after checking against its original training history.
            current.update(rows=tests, counts=data.summary(tests), blockers=[], excluded=[])
            snapshot = data.freeze(store, current, previous["recipe"]["id"])
            return runs.start(snapshot, parent=rid)

    @app.get("/api/learning/runs/{rid}/package")
    def package(rid: str):
        value = runs.get(rid)
        if value["status"] != "prepared" or not value["availability"]["available"]:
            raise ValueError("This training package is not available")
        path = runs.folder(rid)/"package.zip"
        if data.file_hash(path) != value["package_sha256"]:
            raise ValueError("Training package checksum mismatch")
        return FileResponse(path, filename=f"gasp-training-{rid[:8]}.zip", media_type="application/zip")

    @app.post("/api/learning/runs/{rid}/result")
    async def import_result(rid: str, request: Request):
        checked_id(rid)
        # Stream to an ignored temporary file; never extract user paths or execute imported code.
        path = runs.folder(rid)/f"upload-{uuid.uuid4().hex}.zip"
        runs.get(rid)
        try:
            total = 0
            with path.open("wb") as f:
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > 600*1024**2:
                        raise ValueError("Worker result is too large")
                    f.write(chunk)
            try:
                return runs.import_result(rid, path)
            except (zipfile.BadZipFile, KeyError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError("Invalid training result package") from exc
        finally:
            path.unlink(missing_ok=True)

    @app.get("/api/learning/dependencies/{sid}")
    def dependencies(sid: str):
        return runs.dependencies(checked_id(sid))

    @app.post("/api/learning/assignments")
    def assignment(body: Assignment):
        if not journey["progress"](body.subject, body.source, body.profile)["complete"]:
            raise ValueError("Finish the guided baseline before adding a sentence session")
        content = body.content.strip()
        if not content:
            pool = Path(__file__).with_name("practice_sentences.txt").read_text().splitlines()
            # This pool is training-only; evaluation requests always supply distinct text explicitly.
            if body.purpose != "train":
                raise ValueError("Supply new text for an independent evaluation collection")
            used = {data.normalize_text(t.get("target_text") or t["label"]) for s in store.sessions()
                    if (s["subject"], s["source"], s["profile"]["sha256"]) == (body.subject, body.source, body.profile)
                    for t in store.trials(s["id"])}
            existing = [d for d in journey["definitions"]() if d.get("assignment", {}).get("cohort_id") == data.cohort_key(body.subject, body.source, body.profile)]
            for definition in existing:
                used.update(data.normalize_text(t) for t in definition.get("content", "").splitlines())
            selected = [p for p in pool if p.strip() and data.normalize_text(p) not in used][:20]
            if not selected:
                raise ValueError("You've used the starter sentences. Add new text or create a book collection.")
            content = "\n".join(selected)
        definition = dict(id=uuid.uuid4().hex, name=body.name.strip(), version=1, template="sentences",
            content=content, source_text="Gasp original practice sentences" if not body.content.strip() else "User supplied",
            distances=[45], created_ns=time.time_ns(), role=body.purpose,
            description="Read each sentence aloud, then silently. Review in small batches.",
            assignment=dict(cohort_id=data.cohort_key(body.subject, body.source, body.profile),
                target="sentence-pilot", role=body.purpose, source="training-workspace-v1"))
        if not definition["name"]:
            raise ValueError("Enter a collection name")
        # Validate using the same recording primitives as the collection builder.
        from .journey import custom_plan
        custom_plan(definition, body.source == "dca1000")
        definition["definition_sha256"] = data.digest(definition)
        atomic_json(store.root/"collections"/(definition["id"]+".json"), definition)
        return definition

    return runs
