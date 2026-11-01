# Collection journey: building toward dictation

Design and protocol rationale, 31 October 2026. The collection journey is implemented in Gasp 0.6; see [the usage guide](../COLLECTIONS.md) for production behavior. The accompanying [clickable prototype](collection-journey.html) uses demonstration data and never connects to a device or changes recordings.

## Decision

Build the collector around **personal, open-ended silent dictation**. Use a small repeated-phrase experiment as a diagnostic within that program. Keep enough original signal and supervision to improve models without asking the participant to repeat the entire dataset.

Require a curated baseline before revealing the collection-type library and builder. Completing the baseline means that the participant has usable, reviewed reference data and independent evaluation captures. It does not mean that transcription works, that a model has been trained, or that enough data exists for useful dictation. Training outcomes belong in Training; they do not arbitrarily lock access to further collection.

## Evidence and its practical implications

These studies establish useful scales and methods, not a universal minimum for our sensor.

| Work | What was actually tested | Implication for Gasp |
|---|---|---|
| [Wagner et al., 2022](https://pmc.ncbi.nlm.nih.gov/articles/PMC8913675/) | Custom 1–6 GHz transmission sensing with three skin-mounted antennas, 100 updates/s. Two speakers, 50 words, 10 repetitions in each of three sessions: 1,500 utterances per person. Data were vocalized; reported mean recognition was 99.17% across mixed sessions and 88.87% across held-out sessions. | Useful precedent for repeated words and placement variation. Its antenna geometry, frequencies, and task differ from our desktop reflection sensor. It supplies neither an open-dictation data minimum nor a silent-speech success guarantee. |
| [mSilent, 2023](https://wanhaoran.github.io/assets/papers/mSilent_final.pdf), §§4.1, 6, 7.4, 9 | TI IWR1843 plus DCA1000, 240 range-angle frames/s. Ten participants each recorded 500 distinct sentences once aloud and three times silently. The study collected 21,404 samples including challenge conditions. Main splits randomly partitioned recordings; the authors explicitly identify unseen sentences as a limitation. | Strong hardware-family precedent for sentence sequences and paired modes. Preserve ADC and temporal information. The headline WER is not an unrestricted-dictation benchmark; reserve new text and acquisition sittings ourselves. |
| [Lee & Yu, 2025 preprint](https://arxiv.org/html/2509.26409v1) | External IR-UWB sensor, one person, 50 English words over 20 sessions: 1,000 recordings. A learned temporal model achieved 91.1% leave-one-session-out accuracy versus 74.0% with the conventional features. | Keep lightly processed signals and acquisition groups. Better temporal models can improve on a basic feature classifier; poor results from our current classifier need not establish a sensing limit. |
| [SoniSpeech, 2026 preprint](https://arxiv.org/html/2608.00803v1), §§3–5 | Acoustic-sensing glasses, one person, 18,000 utterances; 34.1 session hours and 26.7 usable utterance hours. Voiced and silent versions share text. Silent WER was 78.4% with voiced-only training, 33.7% with silent-only training, and 26.3% with both. Scaling had not saturated at the largest silent training subset. | Particularly useful collection/scaling precedent, though this is ultrasound rather than radar. Record silent speech directly, add voiced references, and measure learning curves. Session time and accepted signal duration are different quantities. |
| [Gaddy, 2022 dissertation](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2022/EECS-2022-68.html), chapter 2; [official implementation](https://github.com/dgaddy/silent_speech) | Single-speaker EMG corpus: 18.6 hours in the open-vocabulary condition, with book passages and paired silent/voiced recordings. The implementation includes a CTC text decoder. | Book reading and utterance-level transcripts are a practical path to language diversity. Paired utterances have the same text but different timelines; do not copy audio word boundaries onto silent takes. Different sensing modality, not a radar sample-complexity estimate. |

[Lip-Siri, 2026 preprint](https://arxiv.org/html/2601.18177v1) is another useful RF bridge: it uses Wi-Fi backscatter, learned motion representations, and lexicon-guided subword sequences. Its 36.87% sentence WER concerns that lexicon-based setting. It is not evidence of unrestricted dictation on TI hardware.

[Subvocal's current product description](https://subvocal.company/) describes open-ended silent speech and short personal calibration. That is a company claim about its current system. The cited 2022 paper should not be treated as the extent of their work, nor does it establish their current sensor architecture or training-set size. Gasp's longer initial program reflects that we do not yet have a trained personal or population model.

## Required baseline v1

**Planning estimate: 60–90 minutes, with extra time for difficult takes or detailed review, spread across three independent sittings.** This is our proposed collection budget, not a published minimum or predicted accuracy. The interface should update time estimates from the participant's actual pace.

| User-facing step | Required captures | Assignment |
|---|---|---|
| 1. Personal calibration | Existing 12 rest, movement, sound and sentence checks. Verify acquisition and inspect the facial response before proceeding. | Calibration only |
| 2. First speech | Eight short benchmark phrases, ten silent repetitions each and one voiced reference each. Sixty different everyday sentences, each aloud and silently. Twelve rest/movement controls. | Training sitting A |
| 3. Return & repeat | Same eight benchmark phrases, five silent repetitions and one voiced reference each. Thirty new sentences, each aloud and silently. Twelve controls. | Development sitting B |
| 4. Independent check | Same benchmark schedule as B, thirty further new sentences in paired modes, twelve controls. | Final-test sitting C |

Total: **472 accepted takes**: 12 calibration, 160 silent benchmark phrases, 24 voiced phrase references, 240 sentence takes covering 120 distinct sentences, and 36 controls. Those counts include all dataset roles; they are not all training examples. Initially the sequence-training portion contains only 60 paired sentences and is a seed corpus, not a credible dictation model by itself.

The benchmark phrases should include both distinguishable phrases and similar alternatives, rather than eight deliberately exaggerated gestures. The sentence set should prioritize ordinary contemporary language and useful articulation variety. Audit its phoneme and phoneme-pair distribution before calling it balanced; a checklist of isolated sounds does not establish coverage in connected speech. Curate original or appropriately licensed text and retain provenance.

Use three quiet-rest, three head-turn, three swallow, and three typing controls per speech sitting. Keep these labels separate. Avoid automatic speech transcription for these controls.

### How the baseline runs

- First launch shows only four ordered cards. The current step has one action. Future cards show a title, time estimate, and prerequisite; no complete prompt list or custom-plan form.
- Open the current card for a concise description and its sessions. Its header's **⋯ → View collection definition** opens a read-only, versioned recipe. No chunk-size or speech-mode controls appear during baseline onboarding.
- Setup confirms a saved person, location and placement. The distance remains easy to check. Persistent enclosure, mount and orientation belong in Settings. Radar and microphone each have a separate gear. No placement affirmation checkbox.
- The recorder shows one task at a time. Break long sittings into roughly five-minute chunks with pause/resume. Paired speech uses small voiced/silent batches to reduce repeated mode switching while preserving pair identity. Prompt order is shuffled within the appropriate task/mode block.
- Review is part of each chunk. Retakes replace progress credit for a prompt; rejected/empty takes do not count. A user can inspect any original take.
- Before B and C, explicitly ask the participant to leave and return/reseat, ideally on a later day. Retain nominal sensor settings while checking the setup again. A new session ID or elapsed timer alone is not proof of independence.
- Lock custom types until all four steps have enough accepted data and reviewed acquisition checks. Show **Baseline collected**, then the library. Never show **Your model is ready** merely because a quota was reached.
- Device failure, missing complex samples, or a wrong profile halts progress with a specific repair action. The initial facial-signal check requires human inspection until its automatic quality measures have been physically validated.
- Track this per person and compatible source/profile. A profile change creates a new acquisition cohort and a relevant setup check; it must not silently mix USB and ADC data. Existing collections stay accessible for review during onboarding.

## What unlocks

The home screen becomes a quiet library of **configured collections**. For example, **The Odyssey** is a configured collection using the **Read a book** template. The card opens that collection's sessions. Empty template names do not appear as working collections; they live in **New type**, which appears after onboarding. Baseline collections remain available in a smaller section below.

| Type | Primary recording interaction | Review tools |
|---|---|---|
| Words & phrases | One prompt, hold/release, randomized repetitions | Utterance boundaries; radar replay; label correction |
| Sentences | Natural connected speech, small paired-mode batches | Audio-assisted transcript checking; optional word alignment |
| Book / long text | Resumable passages with reading progress; start/stop | Passage text and unified timeline; corrections; document order |
| Position study | A position cue, setup snapshot, then a shared speech block | Compare equivalent prompts across measured conditions |
| Free capture | Start/stop with optional reference microphone | Review audio transcript for voiced capture; confirm intended text separately for silent capture |

The builder composes these same task primitives. A position is a condition on a recording block, a book supplies ordered text, and a sentence supplies an utterance target; these should not become unrelated implementations of recording. Silent free capture cannot obtain ground-truth words from a silent microphone. It needs intended text supplied by the participant or another explicit labeling method.

## Data growth and training path

1. **Instrument check:** demonstrate repeatable motion in the actual complex/raw measurements and account for timing and loss. Validate raw DCA acquisition before committing to a large speech corpus. Current USB 10/20 Hz summaries and DCA's 50 Hz burst schedule do not reproduce mSilent's acquisition. The raw data path should preserve enough information to evaluate revised profiles and preprocessing.
2. **First benchmark:** fit the existing phrase baseline on A, use B for choices, and freeze an evaluation on C. Report per-class confusion, uncertainty and controls. Add a temporal model before concluding that a flattened baseline exhausts the signal. Phrase success is a diagnostic, not the long-term product or a mandatory accuracy threshold for unlocking more data.
3. **Sentence learning:** add a radar temporal encoder with character/subword CTC, then compare a sequence decoder and pretrained audio/visual teacher objectives where appropriate. Start with reviewed utterance transcripts; expensive hand-adjusted word timings are optional. Teacher inputs and prompts must not leak into radar-only evaluation.
4. **Scale the personal corpus:** after onboarding, target **2, 5, then 10 hours of accepted silent-speech radar**, retaining a substantial paired voiced subset. Budget expansion to **20+ silent hours** if development curves keep improving. These are experimental checkpoints, not proven requirements. Count voiced data, silent data, idle controls, unique text and wall-clock effort separately.
5. **Evaluate generalization:** maintain separate scores for familiar phrases on new sittings, new sentences/word combinations, and later different positions or rooms. Use development data for the repeated learning curve. Use the final test after freezing the experiment; retire an overused test to development and collect a fresh sealed test for the next major cycle.
6. **Future personalization:** once a compatible multi-person base model exists, determine a shorter onboarding dose empirically (for example, compare several calibration durations). Do not market a five-minute adaptation claim before measuring it.

Suggested initial growth mix: mostly varied modern sentences, then book passages and task-specific language, with a smaller repeated diagnostic and movement-control set. In a book, split by held-out chapter/passages rather than nearby windows of the same recording. Learn from data, but also measure whether acquisition discarded the information we want to learn from.

## Data and navigation contract

- **Template**: a starting point such as Read a book, Words & phrases, Position study or Free capture. Available only in the builder after onboarding.
- **Configured collection / collection type**: stable ID plus immutable version; a name such as The Odyssey, task stages, script source/hash, mode policy, duration bounds and condition schema. A reusable recipe. Creating a different recipe produces a new definition; existing sessions never acquire a rewritten class definition.
- **Session**: an execution of that version, under one person/setup/source snapshot, with immutable acquisition-group and dataset-role identifiers. Resuming preserves them; an actual reseat starts a new acquisition group.
- **Take**: original signal and timestamps, prompt, intended/confirmed text, articulation mode, quality, review state and optional annotations. Retain paired-utterance identity and source passage identity.
- Baseline program progress references those records rather than a mutable `completed` checkbox. Historical plan-less sessions get an explicit legacy grouping based on recorded definition/provenance, not accidental name matching.
- All voiced/silent pairs, retakes and derived windows stay together in a split. Sentence identity and source-document overlap must also be checked; independent session IDs alone cannot prevent text leakage. Holdout data must be excluded from pretraining, fitted preprocessing and decoder/tokenizer fitting as well as supervised fitting.
- Sidebar: collection types → collapsible sessions → takes, with search and filters. One toggle controls it. Contextual breadcrumbs navigate up a level; remove the unconditional Overview control.
- Radar control: one visible bordered capsule. Status/settings on the left; centered chevron on the right, divided by a vertical rule. Connection is represented by a dot plus text, never color alone.
- Keep one main scroll area. Type details, optional settings and the recorder reuse the same content surface. Deep technical evidence belongs in these docs, not the home screen.

## Prototype scope

The prototype demonstrates first launch, in-progress onboarding, completion/unlocked library, read-only definitions, setup, sample recording/review, the grouped sidebar and split radar control. The HTML, CSS and JavaScript are separate files in this directory. Its separate preview toolbar can jump between states. Progress, preferences and signals are simulated and reset on reload; it has no capture, storage, deletion, device or training API access. The installed app and actual data are untouched by this design pass.

### Refinement: setup and linked review

- **Setup:** the small placement drawing remains. Start preview opens the same Radar settings dialog as the gear and top-bar status control. Settings edits affect the next session's snapshot. Each simulated session keeps its definition and setup snapshot.
- **Radar preview:** a range plot compares reflections to a dashed marker at the saved distance. The spatial preview profile enables top, side and fixed 3D views of illustrative detections. The complex speech profile only offers distance. DCA spatial preview is disabled pending calibrated reconstruction. Source and command/data controls explain the two paths in plain language, with detailed port controls behind a disclosure.
- **Capability honesty:** these displays are simulated interaction examples, not evidence that the physical board sees the participant's face. No point cloud is fitted to a face. A real implementation must consume the active profile's capabilities, surface empty/weak detections and timestamps, and avoid treating a strong reflection as confirmed facial placement. Positioning-profile changes must be temporary and restore the collection profile before recording; a preview does not silently change a session's acquisition definition.
- **Recorder:** uses “1 of 12 steps,” a visible elapsed timer and a suggested duration. No “first chunk” heading. Jaw/lip tasks have an optional illustrated movement guide. Books and free capture use press-to-start/press-to-finish; short tasks use hold/release. The baseline speech fixtures demonstrate a few sample utterances, not the final curated 120-sentence corpus.
- **Review:** one ruler and playhead spans reference audio, word intervals, phase and range–time. Scrub directly on any temporal track; click a word to seek; drag word edges or use left/right keys on an edge (50 ms, Shift for 10 ms). Zoom keeps all tracks in the same viewport. Horizontal scrolling belongs beneath the last channel; the page keeps one vertical scrolling surface.
- **Instantaneous views:** I/Q/time, range profile and an explicitly illustrative moving face sit beside the transcript and follow the same clock. Historical waveform/heatmap tracks remain static while the playhead travels through them. These demonstration waveforms contain no audible speech or real video. A real reference-video track would use the same capture timebase when available; the current app does not acquire camera video.
- **Annotation integrity:** dragging labels never regenerates the underlying demo waveform. Original word timing used to construct that fixture stays separate from editable annotations. The production equivalent must retain original radar, audio and timestamp data, and save edits as annotation revisions.
- **Collection builder:** templates create named, fixed definitions. Entered text is retained and used by the example recorder. The Odyssey is a short illustrative book fixture, not an imported edition. Position-study definitions preserve their distance list and prompt block; each take receives a position condition.

Production integration requires versioned types and baseline provenance before wiring these screens into real recording. The existing replay data, audio synchronization, annotation revisions and permanent-delete behavior should be carried forward.

### Interaction checks for this revision

Verified in the in-app browser at 860 × 650, 1240 × 850 and the normal panel size: first-launch gating; read-only definition; setup editing and separate microphone settings; calibration hold/release → review → next step; illustrated movement guide; custom book text → aloud/silent recording steps; historical setup retained after changing preferences; word seek; pointer-drag and keyboard boundary edits with undo; shared zoom; channel hiding; and capability-gated positioning views. The main page has no horizontal overflow and one vertical scroll area, including with the recording sidebar open. Timeline horizontal scrolling stays local to the shared tracks. The earlier empty movement-word-list error was fixed and the calibration path was rechecked. JavaScript syntax and whitespace checks passed.

Hardware accuracy, real audio playback, camera/video capture, persistent baseline progress and production migration are outside this isolated prototype. The live app's existing recordings were not opened or changed during these checks.

## Production implementation · Gasp 0.6

The app uses immutable collection definitions and setup snapshots, a reviewed-data baseline gate per person/source/profile, twelve-take review breaks, persisted preferences, grouped history, real linked replay tracks and capability-aware USB positioning preview. The prototype above remains an isolated demonstration. Custom types unlock after the baseline; the sequence decoder and hardware accuracy remain future validation work. Camera/video recording is not currently captured.
