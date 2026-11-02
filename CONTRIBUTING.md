# Contributing

Use Python 3.12 and `uv sync --frozen --extra dev`. Run `uv run pytest -q` for the software tests. DCA integration tests use loopback UDP and OS pseudoterminals; they do not contact physical hardware. A C compiler is required for the portable firmware encoder test. `python enclosure/iwr6843aop/checks/check_meshes.py` checks exported STL topology without the CAD toolchain.

Keep changes scoped and describe whether evidence comes from a fixture, emulator, physical board or real speech recordings. Preserve raw capture timing and packet-loss information. Include source/profile/participant checks for new inference paths. Keep full utterances and acquisition visits together in train/test splits.

Do not commit recordings, reference media, trained pickle/joblib models, credentials, local viewer URLs/tokens, or downloaded vendor packages. Fixtures should be generated or explicitly marked synthetic/emulated. Hardware datasets require a separate documented sharing decision.

The default dataset and models stay local under ignored `data/`. Manual browser QA can use `python tests/preview_dca.py`; its generated data belongs under ignored `test-data/`. The production app has no emulator injection switch.

CAD rebuild procedures and dependency versions live in the [standalone USB enclosure guide](enclosure/iwr6843aop/README_v1_2.md) and the [three-board capture enclosure guide](enclosure/capture_stack/README.md). The latter houses IWR6843AOPEVM + MMWAVEICBOOST + DCA1000EVM. Keep exported geometry, renders, checksums and fit reports consistent when modifying either design. Run `python enclosure/capture_stack/checks/check_meshes.py` for the nine capture-stack print meshes. The single-board case also has a [drop-in desktop dock](enclosure/iwr6843aop/DESKTOP_STAND.md); run `python enclosure/iwr6843aop/checks/check_dock_meshes.py` for its two print meshes. All designs still require physical validation.

The [v1.3 reinforced rear shell](enclosure/iwr6843aop/README_v1_3.md) has its own geometry report, exports and checksum manifest. Check its print mesh with `python enclosure/iwr6843aop/checks/check_meshes_v1_3.py`; retain the earlier revision's files for existing prints.

## Mac app

For interface work, read [the product design guidance](docs/design/PRODUCT_DESIGN.md). Preserve the existing navigation and data semantics; review complete interaction sequences, including intermediate and failure states, rather than only finished screenshots.

The training workspace is `gasp/static/training.*`; `macos/Sources` provides the native shell, modifier gesture, recording overlay and timestamped optional audio. `macos/backend.py` is the frozen worker entry point. Keep transcription disabled in this first release and preserve original prompts independently of reviewed transcripts.

The collect/train/evaluate backend is `gasp/learning_*.py`; its UI is `gasp/static/learning.*`. Install `--extra training` to run the optional CTC tests as well as the core suite. `python tests/preview_learning.py` creates a synthetic UI workspace under ignored `test-data/`. Read [the worker contract](docs/TRAINING.md) before changing dataset roles, exported jobs or model artifacts. Never test against the installed app's real recordings. The preview's `/ui-check` page provides 900 × 650, 1280 × 800 and wide-desktop frames plus a continuity check for focus, pending uploads, expanded details and incremental rendering.

On Mac, install the pinned `macos-build` extra, run `scripts/build-macos.sh`, and verify the packaged worker with:

```sh
.venv/bin/python tests/smoke_bundle.py dist/Gasp.app
swiftc macos/Sources/RecordingGesture.swift macos/tests/main.swift -o /tmp/gasp-gesture-tests
/tmp/gasp-gesture-tests
```

Do not claim microphone, global shortcut or physical radar validation from emulators or gesture fixtures. Keep private reference media and training data outside commits. See [the app guide](docs/MAC_APP.md).
