# Local verification

USB acquisition on physical hardware is now verified; see [the latest bring-up](#physical-usb-bring-up--2026-10-31). Earlier sections retain the synthetic and emulated evidence from 2026-10-30. No check here establishes real silent-speech recognition.

## Capture navigation — 0.7.2, 2026-11-02

The Capture tab now returns to the overview through the existing draft-saving path. The library toggle is one labeled Recordings control; the inactive Capture label on the overview is removed. Radar controls remain right-aligned when Dictation hides the radar tabs.

Synthetic browser checks verified collection detail → Capture, review with an edited note → Capture → reopened review with the note retained, library open/close, and the radar dropdown in Dictation. Radar controls had identical coordinates and dimensions across both workspaces at 1280 px; the 900 × 650 Capture layout had no horizontal overflow. JavaScript syntax and packaged capture/review/training checks passed. Installed **0.7.2 / build 14** has the updated assets; all 34 existing recording files retained their checksums. Physical radar and microphone capture were not retested for this navigation change.

## Workspace refinement — 0.7.1, 2026-11-02

The existing software suite passed all **73 tests**, with the loopback-dependent capture tests run with local networking enabled. JavaScript syntax and whitespace checks passed. The isolated browser continuity fixture passed nine assertions covering focused input and selection, expanded details, a selected upload, filters, child workspace identity, updated progress, focused prediction actions and replacement of a genuinely different view.

Browser checks used synthetic data only: baseline navigation; setup/resume; timed rest with its countdown; self-paced movement and speech with release-to-save; inline saved-take review; Keep & continue back to the recorder; movement review without transcript controls; keyboard word-boundary marking and undo; expandable radar inspection; model selection; prepared and completed run states; and return from a recording to the same result with its prediction filter retained. Layout checks at 900 × 650, 1280 × 800 and 1600 × 1000, including the open recording library and radar inspector, found no horizontal overflow and one vertical scroll surface.

The standalone Mac bundle passed synthetic capture, review, reserved-holdout training, final evaluation, collection authoring, deletion and parent-exit checks. Native recording-gesture fixtures also passed. Installed version **0.7.1 / build 13** launched successfully with its interface assets matching source. The open review draft was saved before closing the old app; all 34 recording files then retained their checksums through installation. Capture and Training were checked in the installed app with the radar disconnected.

These checks do not establish real speech accuracy or revalidate the physical radar or microphone. Real recordings were not used by the fixtures. The design guidance in [Product design](design/PRODUCT_DESIGN.md) includes further failure and accessibility scenarios to retain in subsequent changes.

## Collect / train / evaluate — 0.7.0, 2026-11-01

The final software suite passed **73 tests**. The optional PyTorch checks include a deliberately simple two-pattern CTC overfit, checkpoint reload/resume, impossible target lengths and short-take invariance to batch padding. New integration checks cover immutable reviewed labels, split leakage, local cancellation, restart recovery, deletion dependencies, separate final evaluation, scheduled-worker package/result roundtrips and tampered candidate rejection. The allocation ID in worker tests is a test fixture, not a live Slurm job.

The standalone Mac bundle passed launch, assets, simulated capture/review, local phrase fitting, the new dataset/run API, explicit final evaluation, deletion and parent-exit checks without a checkout or virtual environment. Browser QA on isolated synthetic data verified the overview, curriculum, dataset view, training launch, results, recording links and sentence-package preparation. The packaged app excludes PyTorch; only the optional training worker needs it.

No real speech model was trained for this verification. The rack was unreachable from the selected work Tailscale profile; no live scheduler contract, GPU runtime, submission, throughput or remote cancellation was verified. Gasp labels exported jobs as prepared, with no claim that a rack job has been submitted. See [the training guide](TRAINING.md) for implemented capabilities and remaining integration.

## Automated checks

`python -m pytest -q`: **23 passed** in 19.85 seconds after the saved-take prediction and serial-shutdown fixes. One upstream Starlette/AnyIO deprecation warning remains.

Coverage includes fragmented UART decoding and malformed packets, signed complex IQ, the host-compiled C ROI encoder, RF/profile bounds, actual pyserial reads and writes through macOS pseudoterminals, trial storage/review/media, whole-session training and provenance checks, local-origin restrictions, DCA commands and reordered/lost UDP data, and synthetic ADC reconstruction.

JavaScript and launcher syntax checks passed. The installed dependency graph passed `uv pip check`. Saved UART replay returned 60 complex frames, no malformed packets and no trailing bytes.

## Browser walkthrough

Using the local app in the in-app browser:

1. Connected the explicit simulator, observed 20 frames/second and zero frame gaps.
2. Created a session and recorded a three-second, 60-frame prompted trial.
3. Reviewed its saved signal and label.
4. Trained on two seeded synthetic visits with a third visit held out: 24 training examples and 12 test examples. The deliberately learnable fixture scored 100%; the UI and report mark it synthetic.
5. Created a matching live simulator session, classified the last three seconds and verified the accepted `rest` prediction appeared in the editable annotation scratchpad.
6. Disconnected the simulator. The preview server was stopped after verification.

Historical screenshots were retired when the project adopted its independent name.

## DCA workbench extension

The DCA1000 source is selectable in the browser. Its test-only peer uses actual loopback UDP sockets and a macOS pseudoterminal for radar CLI commands. Tests allocate isolated ports, so they can run independently of an open workbench. Production uses the documented DCA ports 4096/4098.

Automated checks cover arming/configuration acknowledgements, repeated captures with fresh byte offsets, original raw artifacts, automatic range-FFT import, loss-frame indices, review/download routes, background training, incompatible USB/DCA model inputs, cancellation, no-data errors, failed hardware stops, and switching back to a continuous source. The loopback fixture's ADC data is generated; classifier scores from those fixtures are not speech results.

Browser walkthrough: selected DCA source, chose the emulated CLI and local test addresses, armed the connection, created an explicitly EMULATED session, recorded a prompted take, and reviewed 992 decoded chirp-loop samples from 62 ADC frames. Raw ADC, manifest, radar configuration and NPZ links were visible. A second take was cancelled through the browser; the UI confirmed partial raw files were retained and no training trial was added. Fixtures are isolated under ignored `test-data/dca-browser/`, separate from user recordings.

This is emulation evidence only. No physical DCA1000, FPGA, LVDS cable, RF signal, firmware image or Ethernet adapter was exercised. The preview was stopped after verification.

## Saved-take prediction and public project

Added prediction for saved takes of either source and a last-completed-DCA shortcut. Automated checks cover compatible-model filtering, checksum/quality rejection, training/held-out/new provenance, DCA ADC input, and invariance of the prediction when only the reference label changes.

Browser QA used a local model fitted to repeated emulated ADC fixtures, with intentionally uninformative labels. Clicking Predict saved take produced the expected DCA result, marked TRAINING TAKE / playback check and rejected at score 0.50. That is pipeline evidence only. QA recordings/models stay under ignored test-data and are not published.

The four CAD print meshes pass watertightness, consistent-winding and single-connected-surface checks. The existing 25-file CAD checksum manifest was checked before publication preparation. Public source excludes vendor archives/PDFs, vendor-document screenshots, local viewer logs, recordings and trained models. The public README credits the project’s inspiration and distinguishes the standalone USB enclosure from the exposed DCA/carrier bench arrangement.

Initial hosted macOS CI exposed a serial shutdown deadlock under output backpressure. The binary reader now remains active until the sensorStop command completes, and CLI delivery relies on bounded writes plus acknowledgement rather than unbounded tcdrain/flush. The serial emulator regression sends sustained output and verifies timely, acknowledged shutdown. CI emits verbose test progress and stack dumps for stalled tests.

## Physical checks still required

- Confirm board revision, firmware and USB port roles.
- Validate acceptance and timing of the experimental radar profile, then facial signal quality and phase continuity.
- Exercise optional camera/microphone permissions and software media alignment.
- Validate DCA hardware/FPGA, Ethernet delivery and ADC lane ordering if raw capture is needed.
- Integrate and compile the optional ROI module with the exact TI SDK before using custom firmware. No firmware was flashed or TI firmware image produced here.

Follow [HARDWARE.md](HARDWARE.md) for the USB-first sequence and [EXPERIMENTS.md](EXPERIMENTS.md) for the data collection plan.

## Installed training app · 0.2.0

Local regression result: **29 tests passed**, plus the compiled gesture checks and standalone bundle capture-to-training check.

- Built the AppKit/WebKit/SwiftUI shell and frozen Python capture engine on Apple Silicon macOS 26; verified the complete ad-hoc signature.
- Installed at `~/Applications/Gasp.app`. Opened it and used the actual interface to connect the simulator, create a paired calibration visit, record, finish early, inspect the take, explicitly confirm the rest label, and verify/keep it. The verified count increased and the script advanced. Clean quit removed the worker's ready file and stopped capture.
- The first desktop take was a clearly labelled **SIMULATOR / software-verification** fixture, not a human radar recording. No microphone or Input Monitoring permission was granted during this check.
- Added automated tests for pending/verified/rejected labels, immutable prompts, mode pairing/filtering, reviewed trim boundaries, reserved dataset roles, resume/cancel, optional WAV timing metadata, launch-token access, and DCA manual finish. Existing serial, raw ADC and training checks remain in the suite.
- Compiled/executed the modifier-gesture checks: double-tap start, single-tap finish, long-hold exclusion, and modifier-plus-typing exclusion.
- `tests/smoke_bundle.py` runs the frozen worker from an isolated temporary directory, creates two synthetic collection visits, records and verifies four takes in each, then trains a CPU phrase baseline with an entire reserved test visit held out. It checks that transcription and prediction remain disabled and verifies shutdown cleanup.
- CI runs Python tests on Linux and Mac. Mac additionally compiles the gesture checks, builds/signs the complete app, and runs the standalone worker check.

Still unverified: physical radar acquisition and speech accuracy, microphone-to-radar timing, actual microphone capture on this Mac, and the global shortcut after macOS permission is granted. The app exposes these as optional setup steps; on-screen collection works without microphone or Input Monitoring permission. The bundle is not notarized or Developer ID signed.

## Independent project identity · 0.2.1

Gasp now has its own app, bundle identifier, package, commands, data directory and repository identity. The only project-comparison credit is a brief README note; it is not bundled into the app. The installed Gasp interface was checked after migration and showed the existing verified visit. Saved recording artifacts matched their pre-migration checksums. The former development app was moved to Trash for recovery, and obsolete branded screenshots were removed from the current public tree.

All 29 regression tests and the renamed standalone bundle's synthetic capture/review/training check passed. Runtime source and the built app bundle were searched for the previous project name; none remained. These checks do not change the earlier physical-hardware validation limits.

## Desktop dock publication · 2026-10-31

The single-board v1.2 enclosure and its drop-in desktop dock are now included alongside the three-board capture case. The dock's two STL files passed closed-edge, consistent-winding, connected-surface and positive-volume checks. The six v1.2 STL exports were also checked against their recorded mesh results, including the two separate closed washers in the combined print file. The dock source matches its manifest hash, and both published checksum lists verify their files.

The initial README now leads with hardware renders, the application screenshot and a short first-training flow; setup, capture details and model guidance are linked through the documentation index. Local documentation links and image paths were checked. No radar acquisition, physical printing, cable-bend test, strength/stability test or RF measurement was performed for this publication.

## Monochrome app workspaces · 2026-10-31

The installed app now has Radar data (Capture, Recordings, Training, Setup) and Dictation (History, Settings). Promotional copy, coaching cards and repeated status disclaimers were removed. Controls, plots, native window and recording overlay use a monochrome palette. Dictation remains an unconfigured UI shell with no fabricated history; a recording action there cannot start a new radar take. An active radar take can still be finished.

All 29 regression tests passed. An isolated browser walkthrough connected the simulator, created a calibration visit, recorded and finished a take, opened Recordings, confirmed its label, verified it, and observed the script advance. Training and both Dictation tabs were exercised. The rebuilt standalone worker passed capture/review/reserved-holdout/CPU-training checks on synthetic data, and the complete Mac bundle passed signature verification.

The final app was installed and opened, and its executable and frontend assets matched the final build. Native navigation, shortcut settings, and the dictation recording guard were checked. The five existing recording files matched their pre-install hashes; no user recordings were added or changed. Reference microphone capture, permission-granted global shortcuts, and physical radar/speech behavior remain unverified. The documentation screenshot uses an isolated simulator fixture.

## Physical USB bring-up · 2026-10-31

Tested a physical **IWR6843AOPEVM Rev G**, ES2 AOP, with **mmWave SDK 03.06.02.00** and RF firmware **06.03.02.06.20.08.11**. The onboard CP2105 bridge exposes separate CLI and data ports on the Mac. CLI `version` identified `xWR68xx_AOP`; binary frames identified platform `0xA6843` and version `0x03060200`. No firmware was flashed.

The initial cable was in auxiliary-power connector J5. Moving the data-capable cable to J1 exposed both serial ports. Underside S3 was 0/OFF for functional boot. The CLI accepted the original profile's commands but rejected `sensorStart`. Using the 43 µs idle time from TI's AOP reference timing resolved startup; the original RF parameters with only that idle change also streamed successfully. The profiles now use an 83 µs chirp period, Doppler limits of ±4.8 m/s, and explicit `calibData 0 0 0` (no flash save/restore).

| Profile | Capture window | Frames | Observed host rate | Missing frames | Malformed packets |
| --- | --- | --- | --- | --- | --- |
| USB phase 20 Hz | 20 seconds | 402 | 20.004 fps | 0 | 0 |
| USB phase 10 Hz, after stop/restart | 5 seconds | 51 | 9.955 fps | 0 | 0 |

Both captures had zero discarded bytes and no reader errors. Every frame contained AOP complex TLV 8 (**64 range bins × 12 virtual channels**), range-profile TLV 2, statistics TLV 6 and temperature TLV 9. Complex samples were finite and nonzero. Captures and diagnostic logs remain local under ignored `test-data/hardware-bringup-2026-10-31/`; they are not labelled speech examples or approved training takes.

All **30 regression tests** passed, including the revised raw-ADC timestamp fixture (249 µs between TDM loops). The rebuilt standalone bundle passed isolated synthetic capture, review and reserved-holdout CPU training. Its signature verified, and the installed profiles matched both the source and the configurations exercised above. The five existing recording files retained their checksums.

The installed app was connected through its own Setup controls to the physical board. At 20 Hz its live view showed one missing frame during initial observation. It was then stopped and reconnected at **10 Hz**, where the live view showed **173 frames, zero missing, and 10.0 samples/s**. The app was left connected with no active recording or selected simulator visit. A new real calibration visit requires the participant's measured placement and performed prompts.

The DCA profile shares the corrected RF timing, so its recorded burst duration is now **3.984 ms**. Physical DCA/FPGA/Ethernet operation and lane ordering remain untested. Face targeting, inter-frame phase quality, reproducible articulation signals, microphone synchronization and speech-model accuracy require separate experiments.

## Collection workspace · 0.3.0 · 2026-10-31

- Full regression suite at the checkpoint: **36 passed** (25.31 s), including complete-versus-incomplete DCA Doppler burst checks. One upstream Starlette/AnyIO deprecation warning remains. JavaScript syntax, frozen dependency lock, native Swift compilation and recording-gesture checks passed.
- Rebuilt the standalone Mac bundle with the Speech framework and verified its ad-hoc signature. The frozen worker passed isolated simulator launch, scripts, capture, review, reserved holdout and CPU baseline training. Installed version 0.3.0 / build 3. All five pre-existing recording files were byte-identical after reinstall.
- Browser interaction checks exercised the real collection UI: created a two-passage Reader block, started/finished its first passage, saw pending review and the next passage; held Space for a custom word, released and saw the next prompt; opened saved audio/radar data, dragged a word edge from 2.20 to 1.95 s, clicked the next word to seek, and verified the annotation revision. Fixtures and synthetic reference tones stayed in ignored `test-data/collection-studio-qa`, outside the installed user dataset.
- Physically streamed the new `usb-doppler-10hz` profile for 61 packets with no gaps or parser errors and `usb-spatial-2hz` for 13 packets with no gaps/errors. Both included a complete 64×16 range–Doppler TLV. A separate saved-take check retained 30 Doppler frames and 10 spatial frames with zero gaps, then replayed their matrices through the API and UI. Firmware identity was retained as SDK 03.06.02.00 / xWR68xx_AOP. The spatial scene returned zero detections; the UI reported zero rather than synthesizing a point cloud.
- Opened the installed app, confirmed Capture/Training and the historical recording library, selected the actual CLI/data ports and new phase + range–Doppler profile, and observed Radar connected. Microphone and Input Monitoring remained disabled.
- Native on-device speech following and annotation suggestions compile and are bundled. Real microphone permission, voice-follow accuracy, ASR word timing, and audio/radar offset validation remain interactive checks. Recognition requires an available local language model; no network fallback is enabled. Forced-alignment JSON import is implemented, but no aligner/model is bundled. Physical DCA capture remains unverified; Doppler reconstruction is covered by synthetic complete/incomplete burst tests.

The collection UI supports resumable bounded passages, not uninterrupted whole-book recording. No human speech dataset or speech-accuracy result was produced by these checks.
