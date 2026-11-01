# Single-board enclosure v2.2

This fit revision addresses the molded USB strain relief, tight unmarked aperture keys and loose connections at both ends of the desktop mount. It preserves the TP20 opening and board/antenna positions.

Start with [the print and assembly guide](exports_v2_2/START_HERE.md). The two geometry-only print plates are `exports_v2_2/PRINT_FIRST_mount_and_keys.3mf` (six small pieces) and `exports_v2_2/REPRINT_case_pair.3mf` (rear and front). Reuse the existing horn, stand and T-shaped keeper; retire the old block and separate socket sleeve.

The native source is `src/enclosure_v2_2.py`. Rebuild standing exports with `cadgen +0.8.4 run src/exports_v2_2.py`. Run the fit checks with `cadgen +0.8.4 run checks/check_v2_2.py` and the exported mesh checks with `python3 checks/check_exports_v2_2.py`, from this directory. The archive includes the imported enclosure modules and board reference JSON.

Native CAD and exported mesh checks pass. The 4.35 mm socket/4.5 mm peg and 0.10 mm clip/head preload are intentional compliant fits, not rigid clearances. Physical fit, insertion forces, strength, creep and RF performance remain unverified.
