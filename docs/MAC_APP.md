# Gasp · Mac app

This release collects and reviews personal radar training data. It is an installed macOS application with a menu bar, a small non-activating recording overlay, and a bundled local capture engine. It needs no Terminal window, cloud account, Python installation, API key, or transcription model to run.

**Transcription, text insertion, and radar predictions are disabled.** The separate source workbench can explicitly enable experimental classifier evaluation with `serve --research`; the installed app never enables it.

## Start collecting

1. Open **Gasp** in your user Applications folder (`~/Applications/Gasp.app`).
2. In **Radar data → Setup**, connect the **Simulator** to practice. Its waveforms and all derived results are clearly marked synthetic and cannot establish speech-recognition accuracy.
3. Create a **Personal calibration** visit with your participant name, distance, posture and room notes. Choose paired voiced/silent collection or a single mode. Movement and rest checks have their own labels.
4. Optionally enable reference audio. macOS asks for microphone access at that point. Audio is saved locally with each take; it is never transcribed.
5. Record a take with the on-screen button. In **Dictation → Settings** in the installed app, enable the recording shortcut and grant macOS **Input Monitoring** to use a double tap of Right Option. Right Control and Fn/Globe are alternatives; OS shortcuts can conflict with them. Press the same key once to finish or Escape to cancel. Modifier-plus-typing does not count as a tap. Input Monitoring is optional; buttons and menu controls work without it. The listener observes events without blocking their normal delivery.
6. **Wait for the readiness sound and Recording indicator before performing the prompt.** DCA first arms and waits for data. There is no claim of zero-latency start. Takes end automatically at their short duration limit or can be finished early after half a second.
7. Open the saved take in **Review takes**. Listen to reference audio if present, inspect the trace and loss figures, and confirm what you actually said or silently mouthed. Use **Use prompt** only if you followed the prompt. Keep fillers and repetitions; do not polish the transcript. Reject uncertain or corrupted takes.
8. **Verify & keep** makes the take eligible for training and advances the script. Rejected takes stay in the archive and leave the script step available for a retake. A cancelled USB recording adds no trial. Cancelled DCA recordings retain partial raw diagnostics but add no training trial. Once DCA decoding has started, wait and reject the resulting take instead.

Visits and script order survive app restarts. Select a visit in the sidebar to load it, connect its matching source/profile, and resume. Restarts do not automatically open hardware or begin recording. No always-on microphone or radar recording is enabled.

## Workspaces

**Radar data** contains **Capture**, **Recordings**, **Training**, and **Setup**. Visits stay in its sidebar. Source configuration, reference audio, and new-visit settings are under Setup. The interface and native recording overlay use a monochrome palette.

**Dictation** contains **History** and **Settings**. History is an empty shell until a dictation engine is implemented; radar takes and reviewed training labels are not presented as dictation results. The shortcut setting is shared with radar capture. Selecting Dictation does not enable speech recognition or start radar collection through the recording shortcut. An already-running radar take can still be finished.

## Collection plan

The versioned decks are **Personal calibration**, **First phrase experiment**, and **Natural sentences**. Calibration checks stillness, jaw/lip movement, varied syllables and vowels, short sentences, head turns and swallowing. It stores a personal reference and training material; it does **not** automatically fit a speech decoder, calibrate a beamformer, or prove phonetic separability. The starter sentences are not a validated phonetically balanced corpus.

Paired mode records each speech prompt aloud, then silently. The two takes share a pair ID but have independent timing. Negative/rest prompts are recorded once per repetition, with their actual movement mode. Each visit stores its full ordered plan and shuffle seed. A future sequence dataset will need much more varied text and additional visits.

Create separate **training**, **reserved validation**, and **reserved final test** visits. A new day or sensor repositioning is a useful visit boundary. Calibration visits are not held-out evaluation data. Reserved validation/test visits cannot be fitted by the baseline trainer. Do not repeatedly tune against the final test visit.

The **Train baseline** screen trains the existing CPU phrase classifier on approved recordings with a whole-visit holdout. Use at least two matching examples of every label on each side. Choose one speech mode; voiced and silent takes are not pooled. Rest/movement negatives may be included. Calibration references are not offered as phrase-classification visits. Models stay restricted to the same participant, source, profile and antenna layout. Reports show counts, accuracy, macro F1, majority baseline, source and synthetic provenance. This is a closed-vocabulary experiment, not open dictation.

## Radar sources and timing

- **USB:** compatible SDK 3.x OOB AOP firmware and both selected serial ports. Collection includes up to 350 ms of available pre-roll and 250 ms after finishing. USB data is a processed complex heatmap, not raw ADC.
- **DCA:** IWR6843AOPEVM + MMWAVEICBOOST + DCA1000EVM, radar command USB, and Ethernet. The app uses the existing native UDP capture and two-lane decoder. Takes remain bounded to 25 seconds. Raw capture includes arming and stop/drain margins; it is not a continuous dictation stream. See [hardware setup](HARDWARE.md).
- **Native audio:** AVAudioEngine records a WAV reference. Metadata includes first audio sample host time, sample position/rate, channel count, frame count and detected sample-position discontinuities. Audio starts before radar arming and stops when capture ends, before importing the radar sample.
- **Alignment:** cue-display events include a software clock estimate and round-trip uncertainty. Audio uses the Mac host clock; USB has packet-arrival timing and DCA has a command-anchored ADC schedule. Device/transport delays remain unmeasured. This is not hardware synchronization or word-level ground truth. Validate offsets on hardware before using fine temporal labels.

Whole-utterance confirmed text is the initial supervision. Optional reviewed start/end boundaries are seconds from the first saved radar sample and affect baseline feature extraction without altering raw artifacts. No automatic speech boundaries, phoneme labels or ASR word timestamps are fabricated.

## Local files and schema

Installed-app data is under `~/Library/Application Support/Gasp/Recordings`. The menu item **Show local recordings** opens it. Logs are in the neighboring `Logs` folder. The source workbench's existing `data/` directory remains separate; data is not copied or uploaded automatically. Source files and recordings are independent of the installed app, so rebuilding it preserves visits.

Schema 2 adds an immutable original prompt and target, confirmed verbatim text, review status/provenance, articulation, plan step/pair IDs, calibration reference, placement, dataset role, capture events and optional trim boundaries. ASR and output-text fields remain null. New takes are pending and excluded until human approval. Editing text or trim points without re-approving invalidates approval. Legacy schema 1 records still load and retain their historical acceptance; new review gates cannot retroactively establish their labels.

The installed engine binds only to loopback on an available port and requires a fresh per-launch token. The native bridge accepts only the app's main local page. No code inserts text into other apps, sends messages, or opens external sites. Recordings, reference audio, trained models, logs and app bundles are ignored by Git.

## Build from source

On an Apple Silicon Mac with the Command Line Tools for Xcode, Python 3.12 and uv:

```sh
uv sync --frozen --extra dev --extra macos-build
./scripts/build-macos.sh
./scripts/install-macos.sh
```

The build freezes the capture engine, compiles the AppKit/WebKit/SwiftUI shell with `swiftc`, includes dependency license notices, and applies an ad-hoc signature. It outputs `dist/Gasp.app`. The app has been built and exercised on Apple Silicon macOS 26; other OS/hardware combinations are unverified. The native shell declares macOS 13 as its minimum, but that is not an end-to-end compatibility guarantee for every bundled library.

This development build is **not Developer ID signed or notarized**. Distribution to other Macs needs the normal signing/notarization work. This repository does not disable Gatekeeper or security settings.

Validation includes simulated capture/review/resume, native launch and clean shutdown, recorded shortcut gesture sequences, and serial/UDP DCA emulators. Physical radar behavior, speech accuracy, real microphone timing and a permission-granted global shortcut still need hardware/interactive validation.
