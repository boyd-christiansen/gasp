# Data and baseline training

[Documentation](README.md) · [Collection workflow](MAC_APP.md#collection-plan) · [Experiment plan](EXPERIMENTS.md)

## Local files

The installed app uses `~/Library/Application Support/Gasp/Recordings`; the source workbench defaults to ignored `data/`. The app menu can open the recordings folder. Logs live in the neighboring `Logs` folder. Source and installed-app datasets are separate and are not copied automatically.

Raw UART or ADC files, the exact radar configuration, timing/loss metadata, reviewed labels, and artifact hashes are retained. Reference audio is optional and is never an input to the radar classifier. Recordings and models stay local, with no telemetry or automatic upload.

## Labels and timing

The first supervision is **confirmed text for the whole utterance**. Original prompts are immutable and preserved separately from reviewed verbatim text. New takes remain pending until explicitly approved; editing text, word intervals, audio offset or trim boundaries requires approval again. Silent-take text records the intended words, not an independently measured transcript.

Audio/cue/radar alignment is software-based, with recorded uncertainty. USB timestamps describe packet arrival; DCA preserves its burst schedule and known missing frames. Device and transport delays remain unmeasured. Word intervals are optional, versioned annotations with manual, speech-estimate or imported-alignment provenance. Untimed words stay untimed. Optional local ASR estimates require review; imported forced alignment must match reviewed text. There are no fabricated phoneme timestamps. Validate offsets on hardware before using fine temporal labels. See [timing and schema details](MAC_APP.md#radar-sources-and-timing).

Reader stores document order, script hashes, capture conditions and progress in bounded passages. Reader recordings are excluded from the phrase classifier and retained for future sequence training. CTC training can use passage transcripts without word boundaries; forced alignment is useful for inspection and segment-level experiments. Voiced alignment cannot establish silent-articulation timing.

## Baseline model

The CPU baseline uses log-amplitude and complex phase-change features within a configurable distance gate, resamples takes to a fixed representation, and fits a scaled logistic phrase classifier. Reports include accuracy, macro F1, a majority baseline, a confusion matrix, held-out visits, and trial hashes. High-loss or rejected takes are excluded.

Use a whole-visit holdout with at least two approved examples of every label on each side. Models require the same participant, source, profile, and antenna layout. Voiced, whispered, and silent takes are separate conditions. Include rest and realistic movement negatives. New session IDs alone do not make recordings independent acquisition visits.

Reserved validation/final-test visits cannot be used for fitting. Calibration references are not phrase-evaluation visits. The software can enforce session identities and provenance, but it cannot determine whether two visits were actually recorded independently. See [the collection plan](MAC_APP.md#collection-plan) and [experiment design](EXPERIMENTS.md).

## Scope

This is closed-vocabulary phrase classification. Raw data is preserved for later sequence-model experiments; continuous dictation requires a much larger dataset and further research. Synthetic signals are deliberately learnable and provide no evidence of speech accuracy.

Transcription, text insertion, and radar predictions remain disabled in the installed app. The older source workbench can explicitly enable experimental classifier evaluation with `serve --research`. Its scores are uncalibrated; replaying training data is not an accuracy measurement. See [the research roadmap](ROADMAP.md) and [verification record](VERIFICATION.md).
