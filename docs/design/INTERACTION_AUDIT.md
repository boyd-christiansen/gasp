# Interaction audit · Gasp 0.7.3

For the current failure-path audit, see [Collection reliability · 0.7.8](RELIABILITY_AUDIT.md).

2 November 2026. This pass follows the [product design principles](PRODUCT_DESIGN.md): preserve context, explain state at the affected control, and verify the whole sequence.

## Findings and changes

| Area | Failure found | Resulting behavior |
|---|---|---|
| Navigation | Late collection, recording, or dataset responses could replace a newer destination. | Navigation requests are invalidated when another destination is selected. Radar data restores its selected tab; Capture returns to the baseline overview. |
| Review saves | Editing during a pending save could incorrectly mark newer edits as saved. | Saves use a snapshot and revision; newer edits remain dirty and are saved before navigation. |
| Quit | Native quit bypassed the review draft save. | Quit awaits the draft save, stays open on failure, and asks the user to finish an active capture or resolve unsaved setup changes. |
| Settings | Errors could appear behind the modal; switching tabs reset unsaved setup fields. | Errors appear inside the active dialog. Setup drafts persist across tab changes and reopening, with explicit Save and Discard actions. |
| Radar | Reconnect attempted a second connection; the displayed recorder could outlive its backend session. | Apply & reconnect disconnects first. The next capture resumes the same session, only with its original source and profile and fresh radar data. |
| Connection status | Lost backend access could leave a connected indicator visible. | The control reports Engine unavailable and recovers when communication returns. Controls are disabled during connection changes and restored on failure. |
| Recording | Global shortcuts could begin a timed countdown outside the recorder or through a modal. | New captures require the active recorder, compatible radar, and no modal. Active capture can still be finished or cancelled. Enter supports self-paced hold/release on the focused recording button. |
| Timeline | Keyboard word activation and boundary editing could fail or lose focus. | Boundary edits retain focus. As of 0.7.7, selecting a word preserves the playhead; double-clicking seeks. Missing audio gets relevant instructions; decoding errors replace the loading state. |
| Replay | A missing radar visualization fell back to a nonexistent option; stale take details could linger. | Replay selects an available complex-signal view and clears previous audio, frame requests, quality, and details while loading another take. |
| Training | Filtered inventory could disagree with run setup; final tests were compared against development scores. | Readiness reflects the chosen subset. A run uses the exact options confirmed. Final-test results are reported separately from development comparisons. |

## Repeatable checks

Start an isolated workspace, never the installed user's recording folder:

```sh
.venv/bin/python tests/preview_learning.py --data test-data/interface-audit --port 8892
```

Open `/ui-check` on that server. **Audit interactions** exercises the actual frontend against synthetic recordings and simulator acquisition, including deliberate delayed and failed requests. It records three synthetic calibration takes, trains a CPU phrase model, evaluates the reserved final set, and cancels a deletion warning. It does not connect to physical radar or request microphone access. **Verify update continuity** checks focus, caret, pending file selection, expanded details, filters, and child views. **Check layout** reports overflow and visible scroll surfaces at the selected window size.

The interaction audit includes rapid navigation, edits while saving, draft save before quit, modal errors, unsaved setup, keyboard timing, failed connection recovery, backend loss, global shortcut guards, timed cancellation, timed rest, self-paced movement, profile incompatibility, reconnection, result-to-recording return, separate final-test reporting, and deletion cancellation.

## Scope and remaining limits

The checks establish software behavior on generated fixtures. They do not establish speech accuracy, physical radar signal quality, real microphone timing, or DCA hardware operation. Native microphone and global shortcut behavior still require a brief hardware acceptance session. The sentence training worker/export/import path is covered by the Python suite; this audit's interactive training run uses the local CPU phrase baseline, not a new GPU training experiment.

For subsequent changes, check the affected sequence at 900 × 650 as well as a larger window. Include loading, failure, retry, cancellation, and leaving/returning—not only the finished screenshot. Keep regression checks for demonstrated failures, and preserve the distinction between synthetic verification and actual collection evidence.
