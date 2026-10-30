# First experiments

## Gate 1: a trustworthy instrument

Use a fixed mount and range gate. Verify a stationary reflector, then rest versus large mouth/jaw movements. Track frame numbers and phase over time. Check whether a board restart, background motion, or position change destroys continuity. Do not collect hours of speech before this passes.

Compare 10 Hz and 20 Hz USB streams. The zero-Doppler output is integrated over chirps; integration may attenuate fast articulation. If the signal is weak or temporally aliased, test raw DCA data or the optional narrower custom UART stream. A higher model capacity cannot repair missing measurements.

## Gate 2: repeatable personal phrases

Start with 3–5 distinct phrases plus `rest`, then expand to 10. Capture 20–30 repetitions across three visits. Randomize order. Keep natural silent mouthing as a distinct condition from voiced speech, whispering and exaggerated movements. Include yawns, swallowing, head motion and typing as negative examples.

Define visits using actual acquisition blocks: returning another day or repositioning the device. At least one entire visit is held out. Keep all repeated/derived versions of an utterance in the same split. For hyperparameter selection, use a third validation visit; do not repeatedly tune on the test visit.

The baseline should beat chance and the majority-class baseline on the held-out visit. A proposed eventual target is over 90% for ten phrases, but that is a goal, not an expected result. Track rejection, confusion between phrases, delay and false activations during natural idle periods. The current offline report measures closed-set accuracy/F1; idle false activations and end-to-end latency require a separate timed experiment.

## Gate 3: robustness before vocabulary

Change one factor per session: 10 cm distance change, a slight yaw, posture, board remounting, a different room. A model that recognizes a scripted sequence in one sitting is not yet a reliable desktop input device.

Record precise conditions in session notes and keep original binary packets, profiles and media. Only labels/acceptance change in review; model reports retain the original label/split/checksum snapshot used for that fit.

## Continuous language later

Phrase classification cannot establish open-vocabulary dictation. That needs varied utterances, unseen sentence combinations, a sequence decoder (for example temporal encoder + CTC), appropriate segmentation, and word/character error rates. Radar-only inference should be scored before optional language-model correction. Keep prompt text and audio/video outside the inference inputs. Model uncertainty should produce a rejection or correction opportunity, rather than fluent invented text.

The existing NPZ records preserve complex inputs and timestamps for that stage. Raw DCA and frame-averaged USB data are different distributions: models are not interchangeable between them. No GPU training or cluster service is started by this project. The small included CPU baseline is for bring-up and instrumentation.
