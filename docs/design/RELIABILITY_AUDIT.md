# Collection reliability audit · 0.7.8

5 November 2026. This pass follows the [product principles](PRODUCT_DESIGN.md): protect the work, keep context stable, put state at the affected control, and make recovery part of the workflow. It extends the [earlier interaction audit](INTERACTION_AUDIT.md) and the 0.7.7 timeline fixes.

## Findings fixed

| Area | Failure or friction | Change |
|---|---|---|
| Collection entry | The main Resume button selected an older incomplete session even when the newest session had finished capture and needed review. | The primary action follows the newest session in the current setup/profile. It says **Review N takes** when review is next; older sessions remain explicit history actions. |
| Microphone attachment | An upload failure discarded the only microphone reference after radar had saved. A retry could then be rejected because the WAV already existed. | Native completed references enter a durable local recovery queue before upload. Only a successful backend acknowledgement removes them. Startup retries the queue; the affected take and microphone settings offer **Recover audio**. Identical uploads are idempotent; different recordings cannot replace the original. A WAV committed before a failed manifest update can be attached on retry. |
| Failed recovery storage | Starting another take could replace the in-memory reference when local recovery storage itself failed. | The recorder blocks another take until the unsaved reference is recovered. Native quit and browser unload protect this state. Browser-only capture retains a failed attachment for retry while its page remains open; it does not have native restart recovery. |
| Capture preparation | Clock failure could race microphone startup: cleanup ran before audio finished starting. | Preparation waits for both outcomes before cleaning up; browser audio waits for its software clock estimate before stamping its start. No take is created when either preparation fails. |
| Sensor interruption | A disconnected or stalled sensor could leave a long capture waiting until its full limit. An errored source could still own its ports but could not be disconnected in the UI. | Reported errors wake the recorder immediately. Missing complex frames for two seconds terminate the take with an actionable error. Reconnect releases the errored source; Disconnect stays available. Incomplete failed USB captures are not added as training examples. |
| Countdown | Losing the radar during a countdown could leave “Get ready” on screen without recording. | The countdown restores the recorder and reports that the source needs reconnection. No take or progress is added. |
| Partial word edits | Marking just a start prevented draft save, navigation and quit. Keyboard marks could create reversed or overlapping intervals. | Partial boundaries are durable pending drafts. Keep requires either a complete interval or cleared timing. Boundary shortcuts reject invalid intervals; adjacent edits respect unfinished boundaries. |
| Review navigation | A late Keep response could open the next recording after the user chose Training. Edits made while Keep was saving could be skipped. | Keep advances only in the original review context. Newer edits stay open and pending for review. A delayed quality result no longer moves an active playhead to the start-cue cutoff. |
| Optional word timing | Disabled Apple recognition was retried automatically for each sentence; uncertain timing appeared to block collection. | Fatal recognition-unavailability is remembered for the app session. Explicit Retry remains available. The transcript editor states that word timing is optional. Whole-utterance verified text remains valid supervision; failed recognition does not invent word boundaries. |
| Quality interruption | One missing radar frame or an uncertain syllable-peak estimate stopped the collection sequence. | Minor gaps and heuristic warnings remain on the saved take for review without blocking the next prompt. Missing/unreadable audio, interrupted audio, clipping, short timed references, and radar loss above 5% still request attention. Warnings never automatically verify a take or bypass training exclusions. |
| Training readiness | A take could count toward readiness even when trimming left fewer than eight radar frames. Corrupt timing data failed later during training. | Readiness checks the measured frame window and excludes unusable trims, unreadable timing and transcripts longer than the sentence model's measured-frame budget. Small timing arrays are cached by file version and trim; original I/Q is still checksum-verified when freezing the dataset. |
| Microphone warmup | An engine reporting “running” could stop delivering buffers and remain stuck at warming. | Stale input requests a restart between captures, with a warmup grace period. |

## Verification

All fixtures are isolated under ignored `test-data/` or temporary directories. They are explicitly synthetic and are never merged into user collections.

- Python suite: **94 passed**. acquisition, storage, annotation revisions, interrupted USB/simulator capture, DCA emulation, media retries, collection progress, deletion safeguards, dataset splits, local phrase fitting/evaluation, sequence fitting and worker artifact validation.
- `/ui-check`: 33 interaction checks, 20 timeline checks, 9 timing fallback checks, 9 continuity checks, plus microphone permission-denial/retry and resume checks. The interaction run captures three synthetic calibration takes, trains a local CPU phrase model, evaluates its reserved test data and follows predictions back to review.
- `/failure-preview`: **23 checks** covering partial drafts, boundary restrictions, delayed Keep navigation, edits during Keep, microphone/clock startup races, audio retry retention, radar loss during countdown and reconnect after an error.
- `tests/reference_recovery.swift`: reopen the native recovery queue after a simulated restart; verify original preservation, duplicate retry, invalid identifiers and acknowledgement cleanup.
- Native build and bundle smoke test; installed app playback, settings, progress and physical USB status checked separately. No test silently records a real microphone session.

Repeat the isolated UI checks with:

```sh
PYTHONPATH=. .venv/bin/python tests/preview_learning.py --data test-data/reliability-audit --port 8894
```

Open `/ui-check` and `/failure-preview`. The latter deliberately exercises failure paths and changes only synthetic fixtures. Do not point the preview runner at the installed recordings directory.

## Design decisions to carry forward

1. **Recording and detailed annotation are separate tasks.** Capture a coherent block, then listen and confirm its text. Fine word boundaries are optional refinement, not an onboarding requirement.
2. **An advisory is not a failed take.** Preserve uncertainty and its evidence without forcing needless retakes. Show immediate intervention only when the user can prevent unusable subsequent captures.
3. **A save includes recovery.** A successful radar write is not the same as a successful paired sample. Retain each original until the paired attachment is acknowledged; never silently replace it during retry.
4. **Editing must not move playback.** Word selection, movement and trimming preserve the playhead. Seeking is a separate action. Loading results must also respect user activity that happened while they were pending.
5. **Readiness must explain exclusions before starting a job.** A count alone is insufficient. Trimming, review state, measured frames, source/profile compatibility and dataset role all affect usable data.

## Limits and next acceptance session

These checks establish software behavior, not radar speech-recognition accuracy. No new real speech dataset or GPU experiment was run. Physical DCA capture remains unverified in this pass. Apple on-device sentence timing still depends on the user's system service being available; the app neither enables Siri nor adds a cloud fallback. Automatic syllable drafts remain acoustic estimates, not forced alignment.

Before a long collection session, do a short physical acceptance run: one timed background reference, one self-paced movement, and one spoken phrase. Confirm full audio playback, fresh radar, saved progress after reopening, and an uninterrupted path through review. There is no need to manually place every word before continuing. This is the remaining human/hardware check, not a claim that the application is bug-free.
