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

## Your first training visit

1. In **Settings**, connect the **Simulator**. When using a physical board, follow [hardware bring-up](HARDWARE.md) first.
2. Create a **Personal calibration** visit. Save your participant name, distance, posture, and room notes. Paired collection records each speech prompt aloud and then silently as separate takes. Rest and movement checks have their own labels.
3. Optionally enable reference audio. The installed app asks for microphone access only when you enable it. Audio stays local and is never an input to the radar classifier. Optional on-device speech assistance can suggest annotation times.
4. Hold Space or the on-screen recording button for a phrase; release to finish. In the installed app’s **Settings**, you can enable a **double tap of Right Option** after granting Input Monitoring. Tap once to finish or press Escape to cancel. Buttons work without that permission.
5. **Wait for the readiness sound and Recording indicator**, then perform the prompt. DCA capture arms before it is ready. Finish after the utterance, within the take limit.
6. Click a saved take in the Capture library, inspect the trace and loss figures, listen to reference audio if present, and confirm what you actually performed. Preserve repetitions and fillers. Use **Use prompt** only when you followed it exactly.
7. Choose **Verify & keep**, or reject the take and try again. New takes are excluded from training until approved. Scripts and visit progress survive restarts.

Calibration includes stillness, movement, syllables, and vowels. It does not automatically calibrate a speech decoder or establish phonetic separability.

## Read longer text

Choose **New capture → Reader**, paste or import plain text, and save the capture conditions. Start a passage, read naturally with paced highlighting, and finish it. Each passage is saved separately and can be reviewed on the shared radar/audio/text timeline. Continue the next passage or resume the script later. Optional voice following requires reference audio and an available on-device speech model. See [Reader and timeline controls](MAC_APP.md#reader-longer-text-and-books).

## First phrase experiment

Move to **First phrase experiment** across separate visits. Reserve validation and final test visits. In **Train baseline**, use at least two approved examples of every label on each side of a whole-visit holdout, with matching participant, source, profile, and speech mode. Calibration references are not phrase-evaluation visits.

See [collection and review](MAC_APP.md#collection-plan), [the data/training reference](DATA_AND_TRAINING.md), and [the experiment plan](EXPERIMENTS.md) before collecting a larger dataset.

## Connect the hardware

Choose the [full capture stack or standalone enclosure](ENCLOSURES.md), then follow the [USB or DCA setup guide](HARDWARE.md). The app configures and starts/stops compatible hardware. Firmware flashing and Mac Ethernet configuration are separate steps. Validate a known reflector and a stable signal before collecting speech.
