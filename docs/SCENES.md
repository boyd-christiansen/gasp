# Plan, record, review

Historical design note from before Gasp 0.6. For the current guided baseline,
collection types, recording controls and review workflow, use
[Collecting with Gasp](COLLECTIONS.md).

Gasp separates **collection plans** from **recording collections**.

- A **plan** is a reusable script: prompts or reading material, speech mode, repetitions, and dataset assignment. Create plans without connecting a radar.
- A **setup** remembers the person and placement: location, distance, enclosure, mount, orientation, and notes.
- A **collection** is one run of a plan using a setup. It retains its ordered prompts, setup snapshot, actual radar source/profile, firmware information, and recorded takes.

The underlying setup/collection identifiers remain `scene_id` and `session_id` for compatibility. Changing a plan or setup does not rewrite an existing collection.

## Record a collection

1. **Capture** opens with the selected plan and its prompts. Start with **Personal calibration**: 12 rest, facial movement, sound, and sentence prompts. **Change plan** opens the separate plan library.
2. Choose **Set up recording**. Connect the radar, optionally enable a reference microphone, and enter or reuse the person and placement. The placement illustration is guidance; there is no confirmation checkbox. Additional enclosure/orientation details are optional.
3. Choose **Start session**. This prepares the recorder; it does not start a take. The persistent progress indicator reads **Set up → Record → Review → Done**.
4. Follow the visible session outline. Hold Space or the record button, wait for the recording cue, perform the prompt, and release. Each saved take advances to the next prompt. Quiet-rest prompts should run for the full interval. Reader plans use Space to start/finish a passage.
5. When recording finishes, choose **Review takes**. Check the reference text and radar/audio timeline. **Keep & next** or **Reject** advances through pending takes.
6. The completion screen reports verified prompts and recorded takes. If prompts remain unrecorded or rejected, it offers **Record remaining prompts** rather than claiming the dataset is complete.

The main content pane is the only page scroller, including expanded setup details, the recording library, and the session outline. Reader following scrolls that same pane. Modal settings have their own scroller while the underlying pane is locked.

## Design a collection plan

Choose **Collection plans → Create a plan**. Enter a name, choose a built-in script or your own text, select aloud/silent/paired mode, and preview the prompt list. Word lists use one prompt per line. Reader text is split into passages. Save the plan, then return to Capture to run it. **Make a copy** creates a new editable plan from an existing one; already recorded collections retain their original script.

Plans are saved locally in `plans/`. USB reader passages contain up to 120 words; DCA reader passages are shortened to fit the 25-second raw-capture ceiling. The preview and capture use the same splitting rules. Short-phrase plans are shuffled per collection; paired versions stay together. Large previews show the first 12 prompts and the total count. The recorder shows the current portion of a long queue.

## Pause and return

**Finish for now** saves no additional data: every completed take is already on disk. Return through **Your collections → Resume**, check the matching radar source/profile, and continue at the next unrecorded or rejected prompt. Review can be resumed separately. Individual takes remain available in the collapsible recording sidebar.

Collections remain separate acquisition groups for training and held-out evaluation. Rejected takes do not count as completed prompts; duplicate retakes do not inflate progress. A fully verified calibration can be linked to later collections with the same person, setup, source, and profile.

## Delete a collection

Open a collection’s **⋯ → Delete collection…** action. The warning names the collection, counts its recordings, and explains that deletion is permanent. **Cancel** keeps it. **Delete collection** removes the collection, original radar/ADC files, reference audio, annotations, and any earlier discard marker. The collection disappears from Capture and future training selections. Existing trained models and reusable plans/setups remain.

Deletion is blocked during the collection’s active recording or while a queued/running training job uses it. The API also requires an explicit confirmation flag. There is no trash or discarded-list section in Capture.

Earlier versions kept discarded collections on disk. Those remain available only through **Settings → Storage → Manage previously discarded collections**, with Restore and permanent Delete actions. Updating the app does not silently remove that older data.

The particle logo indicates app activity, not measured mouth movement. Reduced-motion preferences keep it still. Reference audio and word-timing estimates need human review; radar dictation remains disabled.
