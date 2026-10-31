# Local verification — 2026-10-30

The software is ready for a first physical-board bring-up. All evidence below uses synthetic signals, protocol fixtures or emulated serial devices; it does not establish real silent-speech recognition.

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
