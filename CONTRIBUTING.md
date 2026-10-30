# Contributing

Use Python 3.12 and `uv sync --frozen --extra dev`. Run `uv run pytest -q` for the software tests. DCA integration tests use loopback UDP and OS pseudoterminals; they do not contact physical hardware. A C compiler is required for the portable firmware encoder test. `python enclosure/iwr6843aop/checks/check_meshes.py` checks exported STL topology without the CAD toolchain.

Keep changes scoped and describe whether evidence comes from a fixture, emulator, physical board or real speech recordings. Preserve raw capture timing and packet-loss information. Include source/profile/participant checks for new inference paths. Keep full utterances and acquisition visits together in train/test splits.

Do not commit recordings, reference media, trained pickle/joblib models, credentials, local viewer URLs/tokens, or downloaded vendor packages. Fixtures should be generated or explicitly marked synthetic/emulated. Hardware datasets require a separate documented sharing decision.

The default dataset and models stay local under ignored `data/`. Manual browser QA can use `python tests/preview_dca.py`; its generated data belongs under ignored `test-data/`. The production app has no emulator injection switch.

The CAD rebuild procedure and dependency versions live in `enclosure/iwr6843aop/README.md`. Keep exported geometry, renders and fit reports consistent when modifying that design. The enclosure is currently a standalone USB prototype; do not assume it accepts a closed DCA/carrier stack.
