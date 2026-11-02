# Collect, train, evaluate

Gasp 0.7 adds a persistent Training workspace. Capture remains the place to record and review; Training shows which reviewed data is usable, runs a phrase check, prepares sentence-learning jobs, and brings results back to the recordings. Offline evaluation does not enable live dictation or text insertion.

## Your first loop

1. Work through the existing baseline in **Capture**. Progress and recordings are preserved. Verify the transcript and signal before keeping each take; word boundaries are optional for whole-utterance training.
2. Open **Training**. The overview uses the selected person, source and exact radar profile. It recommends continuing a collection or reviewing pending takes. **View data** explains exclusions and lets you leave whole collections out of the next run.
3. **Train phrase model** fits a small CPU classifier on this Mac. The confirmation shows training, development and reserved final-test counts. A fitting-only run is allowed before development data exists, but has no generalization score.
4. Inspect the development result. Each prediction opens its original recording and linked timeline. The result retains the annotation used for that run, even if the current recording is edited later.
5. After the baseline, **View curriculum → New sentence session** creates twenty new sentences in Capture, paired aloud and silent. **Use my own text** and **Collect an independent check** support further training and separate evaluation collections. The starter pool has eighty original training-only sentences; it is a starter, not a full dictation corpus.
6. **Prepare sentence model** freezes a portable worker job. Export it, execute it in the approved scheduled training environment, and import `result.zip`. The page says **prepared**, never **running on the rack**, until actual integration exists.
7. **Check final model** deliberately evaluates a completed, fixed candidate against reserved test recordings. This creates a separate result. Use development data for iteration; do not select prompts or tune models from final-test errors.

The same dataset can support repeated runs. Comparisons and learning curves require the same frozen evaluation membership, transcripts and trims, and the same recipe. A changed evaluation set starts a new comparison. Sentence headlines show **silent word error**, with speaking-mode and sitting breakdowns under details. Word error can exceed 100% when a model inserts many words.

## Curriculum and what “ready” means

The baseline still has four immutable protocols: Personal calibration, First speech, Return & repeat and Independent check. Training reads their existing progress instead of creating another onboarding flow.

Afterward the current experiment checkpoints are **30 minutes, 2 hours, 5 hours and 10 hours of accepted silent training signal**. Voiced references, controls, development/test data, pauses and review effort do not fill that counter. These are provisional budgets for learning curves, not evidence-backed promises that a particular quantity yields dictation.

Eight accepted training sentences permit a pipeline check. They are not enough to claim useful recognition. Validate actual USB/DCA timing and signal quality before committing hours. The broader [training design](design/TRAINING_JOURNEY.md) describes coverage, independent evaluation growth, uncertainty and later adaptive sampling. This release supplies explicit assignments and counters; it does not yet select new prompts automatically from model errors or compute phonetic coverage.

## Dataset contract

- Only explicitly verified, accepted takes with a reviewed transcript are eligible. Movement/background examples belong to the phrase/control diagnostic; sentence training excludes them. Personal calibration is separate from model scoring.
- Person, source, profile and tensor layout remain separate. Simulator results are visibly synthetic. USB and DCA are not silently combined.
- Collection roles determine training, development and final test. The UI does not offer random per-take splitting. New evaluation assignments require a fresh-sitting confirmation in Capture.
- Signal duplicates, paired recordings and a sitting cannot span roles. Sentence datasets also reject normalized text duplicates, shared source-document identities and overlapping eight-word passages across roles. Repeated phrase labels are allowed for the closed-vocabulary diagnostic.
- Each snapshot pins signal checksums, original paths, reviewed text, annotation revision, trim, actual timing, profile, capture/setup metadata, collection version and recipe. It is immutable and checksummed. Later corrections belong to a new snapshot.
- Deleting a source collection removes its cached export packages and makes affected snapshots unavailable for reuse. Historical labels/results remain as experiment provenance. Deletion is blocked while a local run is consuming that source. Exported copies outside Gasp cannot be recalled.

Stored under the existing local data root:

```text
Recordings/
  sessions/...                       # existing radar and optional reference media
  collections/...                    # immutable capture assignments
  datasets/<id>.json                 # frozen labels, provenance, membership
  training-runs/<id>/
    run.json                         # status, source identity, progress, result
    model.json + model.npz            # non-executable portable model
    package.zip                      # prepared worker inputs, when applicable
```

Routine jobs contain radar and reviewed labels for training/development only: **no reference audio and no final-test recordings or transcripts**. The explicit final job contains only its test inputs and the selected model. Package export is a local save; Gasp does not upload it automatically.

## Implemented model recipes

| Recipe | Inputs / method | Execution and evidence |
|---|---|---|
| Phrase check | Existing range-gated amplitude/phase features, training-only scaling, logistic classifier; majority and duration-only baselines | CPU on Mac; separate development and explicit final evaluation |
| Sentence model | Saved complex radar frames, 16 spatial range samples and all saved channels; amplitude, phase change and actual frame interval; two temporal convolutions, bidirectional GRU, character CTC, greedy decoding | Optional PyTorch worker; variable lengths, no temporal downsampling, no audio/prompt input to inference |

The sentence encoder is an offline experimental baseline, not a streaming dictation decoder. It preserves measured frames and marks phase discontinuities across large gaps. It does **not** turn DCA's burst structure into uniform high-rate samples, use raw within-chirp ADC, or reconstruct speech from microphone audio. Too-short CTC targets fail explicitly instead of producing zeroed losses. Checkpoint selection uses silent development WER; without silent development data it uses training loss and reports no silent generalization score.

Source tests include a small synthetic two-pattern overfit, reload/resume, invalid-length handling and a portable worker roundtrip. These establish software behavior only. No real silent-speech accuracy or rack throughput is claimed.

## Portable worker and rack boundary

The rack adapter is not configured in 0.7. **No SSH submission, scheduler polling or automatic result download is implemented yet.** The app exports the exact worker contract and imports its verified result; this keeps collection and model development usable while the live cluster contract is established.

For the Sunfish rack, begin with `ssh sunfish-spark cluster-context` (or `sunfish-asus`) and read `/etc/rack-cluster/AGENTS.md` plus project instructions. Use Boyd's daily identity, a named project workspace, declared memory/time, a digest-pinned rootless container and Slurm. Follow the live node catalog for ARM64/Blackwell-compatible PyTorch/CUDA; do not assume the Mac's wheel or an arbitrary CUDA image will run there. The local development pin is PyTorch 2.9.1, not a validated rack image.

Inside that approved allocation/container, using the **matching Gasp source** and its installed training dependencies:

```sh
python -m gasp.learning_worker /project/inputs/gasp-training-<id>.zip \
  --output /project/runs/<run-id>
```

Record the source commit, container digest and Slurm job ID in project-native ownership/progress records. Set `GASP_CONTAINER_DIGEST` in the scheduled environment so it enters the result receipt. Keep source packages, manifests and outputs together on project storage; never put credentials in them. The worker refuses ordinary execution without `SLURM_JOB_ID`, and refuses mismatched source hashes.

`progress.json` and `metrics.jsonl` contain worker progress. Sentence checkpoints preserve optimizer, RNG and model state at completed epoch boundaries. Re-running the same package with the same output path resumes; a different job is rejected. Termination is cooperative between bounded steps. **Retry** in the app creates a new attempt from its frozen snapshot; resuming a scheduled worker remains a scheduler/CLI action.

Import `result.zip` into its prepared run. Gasp validates run/job/source identities, weight structure, recipe and prediction coverage; it recomputes all scores from the frozen labels. Final evaluation must return the unchanged candidate weights **and** configuration. Results are imported as arrays/JSON, never as an executable pickle. A bounded `--smoke` CPU run is available for developer checks (at most 64 takes, two epochs); its output cannot be imported as a trained model.

The next rack increment is a configured transport adapter: stage packages, submit the approved Slurm template, persist job identity, reconcile scheduler states after reconnect, cancel through Slurm and retrieve the same result contract. It should not introduce another capture flow or expose scheduler fields during ordinary collection.
