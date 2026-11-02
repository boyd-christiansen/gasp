# Gasp product design

Design review · 2 November 2026 · against Gasp 0.7.0.

**Implementation update — 0.7.1:** The first refinement pass implements the focused baseline, compact recording/review layout, inline capture outcomes, return paths from review, state-based Training overview, model selector, and control-preserving progress updates. Companion capture remains a future feature. The principles and acceptance criteria below continue to guide subsequent work. It complements the [collection journey](COLLECTION_JOURNEY.md) and [training journey](TRAINING_JOURNEY.md).

## Direction

The [0.7.3 interaction audit](INTERACTION_AUDIT.md) records the subsequent review of navigation, settings, capture, draft persistence, replay, and training, with a repeatable regression workflow.

Keep the monochrome identity, Capture / Training structure, curated baseline, collection library, and shared recording timeline. Improve hierarchy, continuity, and precision within that structure.

[Benji Taylor's Stageshow](https://benji.org/stageshow) is a useful reference for deliberate composition, selective emphasis, and motion with a visible cause. It makes promotional UI demonstrations. Apply those principles to Gasp's real interactions; keep real data readable and controls accessible. Decorative crops, placeholder content, scripted success, and artificial waiting are inappropriate in the working app.

The product should make three things clear at any moment: what I am working on, what happened, and what I can do next. Quiet visual design still needs strong affordances and enough information to make a decision.

## What the current app reveals

- Capture's baseline has a sensible sequence, but the current step and three unavailable steps occupy almost equal space. Progress and the next useful action can be much closer together.
- Training repeats its purpose through an eyebrow, large title, collect/train/evaluate strip, large milestone card, and three prominent zero metrics. The actual dataset and run history follow below. A new user needs a concrete next task; a returning user needs their result or running job.
- Review has the right underlying tools. Its large title and upper content area push the shared timeline and decision controls down. The I/Q preview receives substantial space even when its small signal trace conveys little at the current scale.
- A control labeled “Phrase check ▾” directly switches recipes rather than opening a menu. Its appearance promises a different interaction.
- Training refreshes can replace the entire view. Preserve focus, expanded details, selection, and scroll during updates; verify those intermediate states, not just the settled screenshot.

These observations come from the installed app and source inspection. This review did not validate recording hardware, retrain models, or modify recordings.

## Next implementation pass

### 1. Finish the record → save → review sequence

Make this one coherent interaction before adding another capture source.

- Keep the prompt, take number, timer, and primary control in stable positions. A speech take or self-paced movement uses hold/release; a baseline duration uses the appropriate timed interaction. Do not add a countdown to every action.
- A press receives immediate visual feedback. Distinguish preparing from actual acquisition; a recording indicator must follow confirmed capture. Animation must never delay input, capture, or saving.
- On release, show saving at the same location, then a saved take and the next action. Advance only when the recording is safely persisted. Explain a failure beside the affected take and retain a retry path.
- Carry the take's identity and task into review. Replace the generic oversized review heading with compact take context. Give transcript, timeline, and acceptance controls the primary space.
- Keep one ruler and playhead across audio, words, and radar. Clicking a word seeks; dragging its edge adjusts it with an immediate boundary/time indication. Undo remains available. Automatic or uncertain timing is distinguishable from reviewed timing.
- Show an action reference for movement/background takes, without transcript work. Show cue exclusions, missing data, and timing uncertainty at the affected interval with a short legend or accessible explanation.
- Keep the primary review action reachable at ordinary window sizes. Reserve layout space for any persistent footer so it never covers tracks. Use a compact optional inspector for alternate plots and technical details; retain the available visualizations.

### 2. Make each overview reflect its actual state

| State | Main content | Primary action |
|---|---|---|
| Baseline underway | Current collection, meaningful progress, next task; remaining steps as compact rows | Resume capture or review the relevant pending block |
| Insufficient training data | Specific unmet requirement and the collection that supplies it | Continue that collection |
| Ready to train | Dataset summary and intended evaluation | Train / prepare the appropriate model |
| Prepared, not submitted | Package status and required next setup step | Open prepared job |
| Training running | Real phase, latest update, and available measured progress | View run |
| Result available | Measured result, comparable previous result if available, and useful next action | Inspect errors or collect recommended data |

Use one primary action per task area. Show detailed dataset metrics when they help explain readiness or performance; collapse empty metrics into a short state explanation. Replace the decorative step strip with meaningful progress or remove it. Preserve the curated baseline and later custom collections; do not expose every collection template at first launch.

### 3. Consolidate the small elements

Use shared spacing, type, border, radius, icon, and control-size tokens across Capture and Training. Align labels and values; reduce redundant borders and nested cards. Keep fine metadata legible. Reserve semantic color for states, accompanied by text or an icon.

An arrow opens a real menu. A status communicates state. A settings affordance opens settings. Keep the radar split control consistent with microphone controls. Provide visible keyboard focus and names for icon buttons. Use one main vertical scroll surface; the editor's synchronized horizontal timeline is a separate, intentional interaction.

## Principles to carry forward

1. **Space follows the task.** Onboarding can be spacious; recording needs focus; review needs an efficient workspace; results need evidence. Do not force all four into the same large-card template.
2. **Continuity precedes animation.** Preserve the selected collection, take, word, playhead, filter, and return location. Opening a recording from a training result should have a clear return to that result, with its filters retained.
3. **Motion explains change.** A sidebar opens from its edge; a menu comes from its trigger; saving resolves into the saved state. Use short, interruptible transitions and reduced-motion alternatives. Keep the particle logo subordinate to recording feedback; do not run it continuously over review or results.
4. **Details appear at the decision.** Setup metadata belongs in settings and a short confirmation. Quality evidence belongs beside the affected take. Model provenance belongs with the run. Avoid paragraphs that compensate for unclear controls.
5. **Labels describe evidence honestly.** Captured, saved, reviewed, and training-eligible are different states. Aloud and silent data are different. A prepared job is not running. Estimated alignment is not measured truth. Keep these distinctions concise and inspectable.
6. **Design the whole sequence.** Include empty, preparing, running, saving, failure, interrupted, and returning states before implementation. A beautiful final screenshot does not establish a usable flow.

## Carrying this into companion dictation capture

If Wispr companion capture proceeds, use the existing collection, take, review, and training records. Put its opt-in setup and status in Dictation; put the resulting recordings in Capture. Avoid a second library or review editor.

The everyday interaction should be a small truthful capture indicator, brief save feedback, and a review queue available later. Review can prioritize uncertain or damaged takes without interrupting every utterance. Preserve reference audio, draft recognition, Flow's edited output, and the reviewed transcript as distinct evidence. Companion recordings must not inflate silent-training progress.

A reliable start/stop integration and synchronized acquisition remain feasibility work. Do not imply active recording merely because a shortcut was pressed.

## Acceptance before shipping the next pass

Inspect complete interaction sequences with synthetic fixtures, including their intermediate states:

- Baseline → setup → timed reference → self-paced movement → speech → saved take → review → next take.
- Take opened from a result → inspect or edit → return to the same result and filter.
- Disconnect while preparing or recording; failed save; interrupted training; prepared job with no worker; zero data; long transcripts; many sessions.
- Keyboard-only operation, visible focus, reduced motion, and refreshed progress without lost context.
- Representative 900 × 650 and 1280 × 800 windows plus a wide desktop: no clipped controls, accidental second vertical scroll, footer overlap, or primary action stranded below unnecessary framing.

Capture before/during/after screenshots or short recordings of these flows. Judge whether the action and its outcome are clear without narration. Timing, hardware capture, and audio correctness require separate validation; visual polish cannot stand in for them.
