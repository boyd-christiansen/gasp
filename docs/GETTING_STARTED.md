# Get started with Gasp

[Documentation](README.md) · [Training Studio manual](MAC_APP.md)

Start with the simulator to learn recording and review without a radar board. It generates clearly labelled synthetic signals; classifier scores from those signals do not establish speech-recognition accuracy.

## Install the Mac app

Build on an Apple Silicon Mac with Python 3.12, [uv](https://docs.astral.sh/uv/), and the Command Line Tools for Xcode:

```sh
git clone https://github.com/boyd-christiansen/gasp.git
cd gasp
uv sync --frozen --extra dev --extra macos-build
./scripts/build-macos.sh
./scripts/install-macos.sh
```

Open **Gasp** from `~/Applications/Gasp.app`. The capture engine and runtime are bundled; no Terminal window is needed after installation. This is an ad-hoc-signed development build, not Developer ID signed or notarized. See [build and compatibility details](MAC_APP.md#build-from-source).

## Launch from source instead

From the checkout:

```sh
./scripts/bootstrap.sh
./scripts/run.sh
```

Open **[the training workspace](http://127.0.0.1:8765/training)**, or double-click [Start Gasp.command](../Start%20Gasp.command). Keep its Terminal window open and stop it with Control-C. Dependencies stay in the project-local `.venv`, pinned by `uv.lock`.

The root page is an older research workbench. A source launch with `serve --research` explicitly enables its experimental phrase-classifier prediction tools; it does not enable transcription. The installed app keeps prediction disabled.

## Your first collection

1. In **Settings**, connect the **Simulator**. When using a physical board, follow [hardware bring-up](HARDWARE.md) first.
2. Open **Personal calibration → Start session**. Confirm your saved person, placement and face-to-radar distance, then choose **Enter recorder**. Edit the usual setup in Settings.
3. Enable reference audio for aloud hardware captures. Audio stays local and is never an input to the radar classifier. Gasp warms the microphone while the recorder is open; check the input meter and use macOS Standard microphone mode for syllable exercises.
4. For rest or movement, **press Space once**. A three-second countdown precedes the required recording duration, and capture stops automatically. These are action references with no spoken transcript.
5. For speech, **hold Space**, wait for the readiness cue, speak, then release. DCA takes must arm before recording. Quality warnings appear immediately after a take so you can retry it before moving on.
6. Open a saved take in the recording sidebar. Listen, inspect the signals, and confirm the words actually spoken. Automatic timing suggestions are drafts; drag word edges or select a word and drag across the audio waveform to adjust them. Whole-utterance text can be verified without word timing.
7. Choose **Verify & keep**, or reject the take and try again. New takes are excluded from training until approved. **Pause session** saves your place; the collection's **⋯ → Start a new session…** starts from the beginning without deleting earlier recordings.

The optional double-tap recording shortcut is configured in Settings and requires Input Monitoring. The on-screen controls and Space work without that permission.

Calibration includes stillness, movement, syllables, and vowels. It does not automatically calibrate a speech decoder or establish phonetic separability.

## Read longer text

After the guided baseline is complete, choose **New type → Read a book**, give the collection a name, and paste or import plain text. Start a passage, read naturally with paced highlighting, and finish it. Each passage is saved separately and can be reviewed on the shared radar/audio/text timeline. Continue the next passage or resume later. Optional voice following requires reference audio and an available on-device speech model. See [Reader and timeline controls](MAC_APP.md#reader-longer-text-and-books).

## Build your baseline

The overview guides you through **Personal calibration → First speech → Return & repeat → Independent check**. This initial protocol calls for 472 reviewed takes across at least three sittings; it is an engineering starting point, not a demonstrated minimum for full dictation. In **Training**, keep development and final-test sessions separate from fitting, with matching participant, source, profile and speech mode. The current trainer is a phrase classifier; sequence dictation training is not yet implemented.

See [collection and review](COLLECTIONS.md), [the data/training reference](DATA_AND_TRAINING.md), and [the protocol rationale](design/COLLECTION_JOURNEY.md) before collecting a larger dataset.

## Connect the hardware

Choose the [full capture stack or standalone enclosure](ENCLOSURES.md), then follow the [USB or DCA setup guide](HARDWARE.md). The app configures and starts/stops compatible hardware. Firmware flashing and Mac Ethernet configuration are separate steps. Validate a known reflector and a stable signal before collecting speech.
