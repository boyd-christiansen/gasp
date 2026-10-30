# Local verification — 2026-10-30

The software is ready for a first physical-board bring-up. All evidence below uses synthetic signals, protocol fixtures or emulated serial devices; it does not establish real silent-speech recognition.

## Automated checks

`python -m pytest -q`: **23 passed** in 20.44 seconds after the saved-take prediction extension. One upstream Starlette/AnyIO deprecation warning remains.

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

The capture view is saved in [workbench-preview.jpg](workbench-preview.jpg).

## DCA workbench extension

The DCA1000 source is selectable in the browser. Its test-only peer uses actual loopback UDP sockets and a macOS pseudoterminal for radar CLI commands. Tests allocate isolated ports, so they can run independently of an open workbench. Production uses the documented DCA ports 4096/4098.

Automated checks cover arming/configuration acknowledgements, repeated captures with fresh byte offsets, original raw artifacts, automatic range-FFT import, loss-frame indices, review/download routes, background training, incompatible USB/DCA model inputs, cancellation, no-data errors, failed hardware stops, and switching back to a continuous source. The loopback fixture's ADC data is generated; classifier scores from those fixtures are not speech results.

Browser walkthrough: selected DCA source, chose the emulated CLI and local test addresses, armed the connection, created an explicitly EMULATED session, recorded a prompted take, and reviewed 992 decoded chirp-loop samples from 62 ADC frames. Raw ADC, manifest, radar configuration and NPZ links were visible. A second take was cancelled through the browser; the UI confirmed partial raw files were retained and no training trial was added. Fixtures are isolated under ignored `test-data/dca-browser/`, separate from user recordings.

The final review view is saved in [dca-workbench-preview.jpg](dca-workbench-preview.jpg). This is emulation evidence only. No physical DCA1000, FPGA, LVDS cable, RF signal, firmware image or Ethernet adapter was exercised. The preview was stopped after verification.

## Saved-take prediction and public project

Added prediction for saved takes of either source and a last-completed-DCA shortcut. Automated checks cover compatible-model filtering, checksum/quality rejection, training/held-out/new provenance, DCA ADC input, and invariance of the prediction when only the reference label changes.

Browser QA used a local model fitted to repeated emulated ADC fixtures, with intentionally uninformative labels. Clicking Predict saved take produced the expected DCA result, marked TRAINING TAKE / playback check and rejected at score 0.50. That is pipeline evidence only. See [dca-prediction-preview.jpg](dca-prediction-preview.jpg). QA recordings/models stay under ignored test-data and are not published.

The four CAD print meshes pass watertightness, consistent-winding and single-connected-surface checks. The existing 25-file CAD checksum manifest was checked before publication preparation. Public source excludes vendor archives/PDFs, vendor-document screenshots, local viewer logs, recordings and trained models. The public README credits Subvocal and distinguishes the standalone USB enclosure from the exposed DCA/carrier bench arrangement.

## Physical checks still required

- Confirm board revision, firmware and USB port roles.
- Validate acceptance and timing of the experimental radar profile, then facial signal quality and phase continuity.
- Exercise optional camera/microphone permissions and software media alignment.
- Validate DCA hardware/FPGA, Ethernet delivery and ADC lane ordering if raw capture is needed.
- Integrate and compile the optional ROI module with the exact TI SDK before using custom firmware. No firmware was flashed or TI firmware image produced here.

Follow [HARDWARE.md](HARDWARE.md) for the USB-first sequence and [EXPERIMENTS.md](EXPERIMENTS.md) for the data collection plan.
