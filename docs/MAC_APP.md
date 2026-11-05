# Gasp · Mac app

For the setup, collection and review flow, see [Collection guide](COLLECTIONS.md).

Gasp collects and reviews personal radar training data. The installed Mac app bundles its capture engine and stores recordings locally. Radar dictation and text insertion remain disabled.

## Capture

**Radar data** has two tabs: **Capture** and **Training**. Capture's collapsible left library contains saved takes. **Settings** is at the bottom left and contains hardware, optional reference audio, and the recording shortcut. Dictation has a separate empty history until a decoder is available.

1. Open `~/Applications/Gasp.app`. In **Settings**, connect the Simulator to practice, or select the physical USB/DCA source and its ports/profile. Simulator data is explicitly marked and cannot establish speech accuracy.
2. Follow the guided Capture cards: **Personal calibration → First speech → Return & repeat → Independent check**. Open a collection, start a session, confirm your setup, and enter the recorder. **New type** becomes available after the baseline is reviewed.
3. Settings stores the usual person, distance, location, enclosure, mount, yaw/pitch/roll and placement notes. Each session retains its own setup snapshot, exact radar configuration, source, ordered script and available firmware information. Start another session after changing setup or on another acquisition day.
4. Optionally enable **Record microphone with each take** in Settings. macOS requests microphone access. Audio is a reference for annotation; it is never an input to the radar model.
5. For words/phrases, **hold Space or the record button**, wait for Recording/the readiness sound, perform the prompt, then release. For movements, hold Space and release when finished; the timer counts up. For stillness/background samples, press Space once: a three-second preparation countdown precedes the timed capture, which stops automatically. Reader uses Space to start and finish a passage. Cancel or Escape cancels the take.
6. Saved takes remain **pending review**. Immediate capture checks pause on problems so you can retry before continuing. Open a take in the library, confirm the actual words, preserve fillers/repetitions, and choose **Verify & keep**. Actions are reviewed without transcripts or word annotations. Reject uncertain or corrupted takes; a rejected prompt becomes available again.

The baseline card distinguishes **recorded** prompts from **reviewed** prompts. Gray progress includes pending recordings; black progress indicates verified recordings. Repeated takes do not count twice, and rejected takes do not advance capture progress. Resuming returns to the next unrecorded prompt; completing review unlocks the next baseline collection.

The microphone preference survives restarts and updates independently of macOS permission. If access needs to be granted again, **Resume recording** requests it and explains any denial without resetting your preference or creating another session.

The optional global shortcut uses a double tap of Right Option (Right Control or Fn/Globe are alternatives) to begin and one tap to finish. Enable it in Settings and grant Input Monitoring if desired. Buttons and Space work without that permission. Modifier-plus-typing does not count as a tap.

The radar indicator distinguishes **USB detected** (attached but not streaming), **Radar connected** (fresh frames), and **Radar · no data** (stale stream). After a successful USB connection, Gasp reconnects that saved port pair and profile on launch or reattachment. Explicit **Disconnect** disables this behavior until you connect again. Simulator and DCA sources are never started automatically.

The recorder shows status and timing in the main window. The floating recording indicator appears only while Gasp is in the background or minimized, and disappears when you return.

## Reader: longer text and books

Reader preserves document order and divides text into resumable passages of at most 120 words. Each completed passage is saved separately. USB takes have a three-minute ceiling; DCA passages are shortened to fit its 25-second raw-capture limit. Finish before the limit, pause while saving, and start the next passage. This release does not record a whole book as one uninterrupted stream.

Choose paced highlighting at 50–300 words/minute, manual scrolling, or **Follow voice · on device**. Voice following requires the installed app, reference audio, macOS speech permission, and an available local language model. It follows approximate recognized progress through the displayed script; it does not confirm the transcript or create word boundaries. Silent reading uses paced/manual mode. Speech assistance has no network fallback. If recognition stops, finish manually and choose another scroll mode for the next take.

Open the named collection and choose **Resume session**, using the original source/profile. Pending captured passages count as captured; rejected passages can be retaken. Progress survives restarts. Imports are plain text, limited to 200,000 characters per session; import another chapter for larger books.

## Review: one player for radar, audio and text

The playhead drives the radar visualization, audio waveform and word track together. Click a word to select it without moving the playhead; double-click to jump to its start. Drag a word block to move it, or drag either edge to trim. Editing remains available during playback. Use these shortcuts when focus is outside a text field:

| Control | Action |
|---|---|
| Space | Play/pause |
| Left / Right | Step one original radar sample |
| Shift + Left / Right | Move 0.1 seconds |
| `[` / `]` | Set selected word's start/end at the playhead |
| Command-Z | Undo a word edit in the current review |
| + / − | Zoom the timeline |

**Use script** copies intended text only. Whole-passage verified text is valid supervision even without word timing. Drag an untimed word from the transcript into **Audio** or **Words**, then trim its edges. Alternatively, select it and draw its interval in either track, or set boundaries with `[` / `]`. Whole-word moves preserve duration and cannot cross neighboring words. Arrow keys on a focused block or edge adjust by 50 ms; Shift-arrow adjusts by 10 ms. Draft intervals and an unfinished start marker are shown directly on the timeline. **Loop audio** repeats the selected word or a 0.25 / 0.5 / 1-second region around the playhead, word start, or word end. A boundary loop follows the edge as you trim; the shaded loop region marks what is repeated.

Aloud review automatically places missing words from the recorded WAV and the supplied English transcript. Sentence timing uses a bundled Wav2Vec2 acoustic model and CTC forced alignment, entirely on this Mac; it does not require Siri, Dictation, or an account. The start cue is excluded before alignment. **Auto-place missing words** retries in place and preserves existing intervals and unfinished manual boundaries. Syllable exercises use sound bursts and within-group valleys instead of dictation. Ambiguous or missing audio stays unplaced with an explanation. All suggestions remain drafts until reviewed; verified takes are not changed automatically. References up to three minutes are processed in overlapping windows with audio and radar offsets retained. The pinned model and build instructions are described in [Local word timing](WORD_TIMING.md). Silent takes do not inherit aloud word boundaries.

For an external forced aligner, import JSON with `timebase: "audio"` or `"radar"` and a `words` array of `{ "text": "hello", "start": 1.2, "end": 1.6 }`. Montreal Forced Aligner's JSON `tiers.words.entries` format is also accepted. The aligner itself is not bundled. Imported word text must match existing reviewed text. Intervals must be ordered, non-overlapping and inside the radar take. Silent takes have intended/manual labels, not audio-established articulation boundaries.

**Timing & notes** contains utterance trim points and an adjustable audio start offset in radar time. Initial synchronization is a host-clock estimate; USB arrival latency and DCA command-to-frame offset remain unmeasured. Fine editing does not increase the sensor's temporal resolution. Edits invalidate prior approval, preserve raw signals and archive earlier annotations. Stale saves from another view are rejected.

A missing-frame warning reports skipped radar sequence numbers, not missing audio. After capture it gives the gap's location; open review and use **Show gap** to seek there. Red ruler markers remain visible with radar tracks hidden, and shaded radar bands bracket the adjacent received samples. At 20 fps one missing frame represents about 50 ms of missing data; the bracketing interval is longer because it includes the neighboring sample times. Raw samples and loss information are retained.

## Radar views and profiles

| View | Meaning / requirements |
|---|---|
| Range over time | Mean magnitude over channels, with original sample times retained for edits |
| Phase over time | Unwrapped phase at the selected range bin/channel; gaps remain visible |
| I/Q trajectory | Real and imaginary signal components, with **time as the third axis**; this is not physical XYZ motion |
| Range · selected frame | Magnitude across distance at the playhead |
| Range–Doppler | Full saved distance/velocity matrix; requires the Doppler USB profile or complete DCA bursts |
| 3D / range–azimuth detections | Firmware Cartesian detections; requires spatial USB output and actual detections |

**Phase · 10 fps** is the USB starting point; 20 fps is available. **Phase + range–Doppler · 10 fps** retains the full 64×16 Doppler matrix alongside all 12 complex channels. **Spatial diagnostics + Doppler · 2 fps** adds firmware detections at a lower rate to allow for variable UART traffic. The conservative budget includes a reserve for up to 1,024 points; actual sustained load still needs checking. Both extra profiles have streamed on the connected Rev G / SDK 03.06.02.00 board. The diagnostic scene produced zero points, so spatial calibration/accuracy is unverified.

Views are enabled from saved capabilities; changing the view cannot recover a TLV that was never captured. This release's azimuth view uses detected points, not an uncalibrated FFT of the AOP antenna geometry. DCA range–Doppler is computed from complete chirp bursts on replay. No spatial calibration or custom firmware is silently applied. See [hardware details](HARDWARE.md).

## Training

Training shows the current person's reviewed dataset, curriculum progress, training runs and results. The phrase model runs locally on CPU. Sentence jobs use a portable worker package, with explicit export/import until the rack adapter is configured. Both recipes keep training, development and final-test data separate.

Each prediction opens the original recording. Dataset snapshots preserve the transcript and trim used for the run; later review edits do not change old scores. Word boundaries are optional for whole-utterance CTC training. After the baseline, Training can create the next sentence collection directly in Capture.

See [Collect, train, evaluate](TRAINING.md) for the complete workflow, worker contract and current limits. Live radar dictation remains disabled.

## Local files and timing

Installed-app data is in `~/Library/Application Support/Gasp/Recordings`; the menu item **Show local recordings** opens it. Logs are in the neighboring `Logs` folder. The source workbench's `data/` directory is separate. Reinstalling the app preserves recordings.

USB stores the complex heatmaps and original UART packets, including enabled diagnostic TLVs. DCA stores original ADC data/manifests and derived range FFTs with burst timing and known loss indices. Native WAV metadata records first-sample host time, sample position/rate and discontinuities. Cue/hold events carry host-clock estimates and uncertainty. These are software timing anchors, not hardware synchronization.

The local server binds to loopback and requires a per-launch token. Reference audio, models, logs, recordings and app bundles are ignored by Git. Optional on-device speech assists annotation/scrolling only; it does not insert text or enable radar predictions.

## Build from source

On an Apple Silicon Mac with Command Line Tools for Xcode, Python 3.12 and uv:

```sh
uv sync --frozen --extra dev --extra macos-build
./scripts/build-macos.sh
./scripts/install-macos.sh
```

The build freezes the Python worker and compiles the AppKit/WebKit/SwiftUI shell with Apple's Speech framework. It outputs `dist/Gasp.app`, with dependency notices and an ad-hoc signature. Tested on Apple Silicon macOS 26. The declared minimum is macOS 13, but other OS/hardware combinations are unverified. Distribution needs Developer ID signing/notarization; this project does not disable Gatekeeper.

See [verification](VERIFICATION.md) for the distinction between physical USB checks, synthetic UI/bundle checks, emulated DCA behavior, and microphone/speech checks still needed.

## Recovery and collection interruptions

Completed microphone references in the native app are copied into local recovery storage before being attached to their radar take. If attachment fails, the app retains that copy and retries on launch. **Settings → Microphone → Recover audio** retries immediately. Originals already attached to a take cannot be replaced by a different upload. If even local recovery storage fails, recover the audio before starting another take or quitting. Browser-only capture retains its pending reference while the page stays open, without restart recovery.

Small radar gaps and uncertain acoustic checks stay visible in review but do not interrupt every prompt. More substantial failures request attention immediately. A stalled radar ends the affected capture and lets you reconnect; it does not save an incomplete sample as training data.

A partially marked word can be saved as a draft and resumed later. Before keeping the take, finish that interval or clear its timing. Untimed words are allowed: the reviewed transcript is sufficient for whole-utterance training. See the [reliability audit](design/RELIABILITY_AUDIT.md) for the tested failure cases and remaining physical acceptance checks.
