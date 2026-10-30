# Research roadmap

## Working software

- Mac-first USB complex heatmap and native DCA1000 raw ADC acquisition.
- Prompted takes, raw artifacts, quality/loss records, reference media and label review.
- Whole-session baseline training with source/profile/participant checks.
- Prediction on saved takes, including DCA, with training/held-out/new provenance. Live-window inference on continuous USB.
- Rev G standalone enclosure CAD with solid/open fronts, printable exports and renders.

Software fixtures and emulators validate these paths. Physical radar, enclosure and silent-speech accuracy remain unvalidated.

## First hardware session

1. Identify the exact board revision/firmware and validate CLI/LVDS settings against it.
2. Check a known reflector and repeatable jaw/lip motion. Compare the USB summary with full DCA input before collecting a large speech corpus.
3. Verify ADC lane order, antenna mapping, actual chirp/frame timing, packet loss and phase continuity. The bundled DCA profile has 50 frames/s and 16 loops in short bursts; it is not uniform 800 Hz sampling or mSilent's 240 Hz schedule.
4. Check recorded reference-media offsets and uncertainty using visible, radar-observable calibration motion. Host-clock estimates are not hardware synchronization.

## Data collection and models

- Add pre/post-roll, separate prompt and confirmed transcript fields, and reviewed utterance boundaries.
- Prevent unintended pooling of silent, whispered, voiced and exaggerated articulation. Keep rest and natural movement negatives separate from spoken text labels.
- Start with a small randomized phrase vocabulary across real acquisition visits. Reserve validation and final test visits before tuning.
- Measure false activations during normal desk use, not just closed-set accuracy on prompted takes. Add duration/energy baselines and learning curves.
- Compare the current baseline with a temporal encoder using selected or beamformed channels. The collector retains all channels; the current feature baseline uses a fixed subset.
- Collect varied sentence combinations before training a character/subword sequence model with CTC. Whole-utterance transcripts are the initial supervision; manual word timestamps are optional.

## Continuous DCA prediction

The current DCA path starts/stops per take and predicts a completed recording. Continuous operation needs a bounded reorder/ring buffer, measured device-to-host timing, streaming range/channel extraction, segmentation and rejection, and latency/false-activation measurements. Validate the raw acquisition schedule and signal before presenting continuous predictions as a reliable interface. No continuous GPU service is started by this project.

## Enclosure

Print and verify fit, thermal behavior, RF performance and arm strength. Compare the solid radome and open aperture. A carrier/DCA access arrangement needs its own mechanical design; the current closed enclosure is for standalone USB.
