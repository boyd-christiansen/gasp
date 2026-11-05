# Local word timing

Gasp 0.7.9 bundles a local English acoustic model for automatic sentence timing.
Opening an unverified aloud take fills missing word intervals. A visible
**Auto-place missing words** button retries without replacing existing intervals.
Word placement does not change the transcript or mark a take verified.

The model is [Wav2Vec2 base, trained on 960 hours of LibriSpeech](https://huggingface.co/facebook/wav2vec2-base-960h),
using the [pinned ONNX conversion](https://huggingface.co/onnx-community/wav2vec2-base-960h-ONNX/tree/729c1a6730fb549c20a1c73a3d3f96f11020225e).
It is distributed under Apache 2.0. The uint8 artifact and vocabulary occupy
approximately 95 MB. Runtime inference uses ONNX Runtime on the CPU, with at
most four threads. No account, speech-recognition permission, or network
connection is required in the installed app.

The input is the original WAV, excluding the recorded start-cue interval. Gasp
resamples a working copy to 16 kHz, obtains acoustic character probabilities,
then finds a CTC path through the known transcript. Repeated letters require
separate CTC states. Long references use 20-second cores with context at their
edges. Word spans retain the original audio clock and the reviewer's audio/radar
offset. The original audio and radar files remain unchanged.

The current scope is English WAV references up to three minutes. Syllable drills
retain the separate acoustic-burst method. Actions and silent takes do not get
audio-based word timing. A coarse transcript/audio mismatch check rejects large
disagreements; it does not prove every word was spoken. Names, numbers, accents,
quiet speech, and precise phonetic boundaries still need review. These are draft
word intervals, not phoneme ground truth. Boundaries conflicting with existing
manual edits remain unplaced. Editing or switching takes during inference
invalidates the pending result.

## Development and packaging

Run `uv sync --extra dev --extra macos-build`, then
`.venv/bin/python scripts/fetch-alignment-model.py`. This downloads only public
model artifacts into the ignored `.cache/alignment-en` directory. Every file is
pinned by revision, length, and SHA-256 in `gasp/alignment_model.json`.

`scripts/build-macos.sh` verifies the artifacts and copies only the manifest's
files into the app. Runtime checks verify them again before loading. Weights,
recordings, and generated alignment data are never committed to Git.
`GASP_ALIGNMENT_MODEL` can point to a separately provisioned model directory
containing these exact artifacts; it cannot silently select another model.

Unit tests use controlled emissions to exercise repeated characters, missing
audio, mismatch rejection, cue exclusion, clock offsets, long-window stitching,
and read-only suggestion endpoints. UI tests cover partial annotations, retry,
late responses, navigation, and preserving manual edits. Real recording checks
are kept local and reported separately from synthetic regression tests.
