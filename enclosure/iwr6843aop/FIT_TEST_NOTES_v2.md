# Physical fit-test feedback

## First slider-coupon test

User observations, standard black PLA, Bambu Studio:

- The pieces slide along the intended assembly axis quite smoothly, with no clear latch along that axis.
- When held engaged and pulled directly against the hooks, they resist separation after roughly 1 mm of travel.
- The isolated pieces tend to rotate inward and disengage. The user must bias them outward to maintain engagement.

Interpretation:

- Smooth sliding is a positive clearance result. These rails have no axial detent; the separate aperture shroud blocks the assembled cover's opening motion, and its two keys retain it.
- The single-hook coupon omits the opposing hooks and the connecting shell, so it does not independently validate enclosure retention. The need to hold it aligned is a limitation of the coupon.
- The roughly 1 mm observed travel exceeds the 0.30 mm nominal hook-to-ledge vertical clearance. Rocking, print variation and actual feature dimensions have not been separated; do not assume a cause or tighten the design based on this estimate alone.
- Full-shell retention and printed flex remain untested. Keep the current dimensions pending further fit evidence. A connected, opposed-hook coupon would be a more representative follow-up if retention needs testing before a full shell print.

Focused rigid-CAD check: `checks/slider_feedback_report.json`. The aligned single coupon blocks a 1 mm lift, but permits that lift after a 2.4 mm inward shift. The full cover encounters the rear during sampled lateral shifts of ±0.4/±0.6 mm, and during lifts of 0.4/1 mm. These samples do not prove all rotational escape paths or printed strength.

No production geometry or print exports were changed in response to this first observation.

## Aperture key and stand sleeve tests

User observations:

- The difference between keys was small, but the largest key felt tightest and best retained.
- The tightest stand connection was the best fit.

Selected variants for the next full enclosure prototype:

- Two 3.35 mm locking keys (`key_3p35_snug_trial.stl`).
- One 4.35 mm bore stand sleeve (`socket_4p35_snug_trial.stl`).

These are selections from the already printed trials; no geometry changes are needed. The key was tested in the coupon, and the sleeve on the existing stand. Full enclosure retention, service life and RF performance remain untested. The sliding-hook dimensions remain unchanged pending further evidence.

`PRINT_SELECTED_v2/` contains the eight STL parts using these preferred fits, including two separately named identical key files. Undamaged selected trial pieces can be reused; the test plate supplied one key of each size, so one additional 3.35 mm key is needed if reusing its key and sleeve. `iwr6843aop_v2_selected_fit.zip` packages this selected set. The original prototype archive and nominal pair remain historical alternatives.

## Full-board seating obstruction — 2026-11-01

User photo `/Users/boyd/Downloads/IMG_5497.JPG` identifies the upright metal loop beside the central bottom-side connector as the obstruction against the rear floor.

Identification from TI SPRR418A, Rev G Altium ASCII:

- Component TP20, component ID 126, bottom side, footprint FP-4953_HDR1-MFG.
- Manufacturer Keystone Electronics, part 4953, PC loop test point.
- Pad 1 belongs to net 234, named GND.
- Altium placement X=5764.1576 mil, Y=5964.4729 mil.
- Primary part source: https://www.keyelco.com/product.cfm/Loop-Type/4953/product_id/1307
- Drawing: https://www.keyelco.com/product-pdf.cfm?p=1307

TP20 was omitted from the selected components in `extract_ti_geometry.py` and from the enclosure reference/checks. Previous CAD clearance passes therefore do not establish clearance for this feature.

The v2.1 correction adds TP20 and its opposite-face tail to the extracted component reference using conservative 3 mm square envelopes, with 9.2 mm underside height and 2.6 mm top-side tail height. Position is taken directly from TI: enclosure coordinates (-7.142236, 5.685857) mm. The rear now has a 6 mm through-opening at that position, joining the neighboring vent; support height remains 10.4 mm. No other shell features or printed parts are modified. The through-opening avoids a thin residual floor and needs no support in the intended flat-back print orientation.

Replacement: `exports_v2_1/01_rear_TP20_clearance.stl` and `.3mf`. The standard rear in `exports_v2/` and `PRINT_SELECTED_v2/` is also updated. Reprint only the rear. `history/v2_before_tp20/` preserves the original rear for the regression comparison. `checks/tp20_report.json` records the actual check results. Physical seating of the revised print remains unverified; keep the board and test point unmodified.

## Full assembly feedback and v2.2 revision — 2026-11-01

The user reports cutting the printed cable passage to accommodate a molded strain-relief sleeve, tight horn wedges of uncertain size, and substantial play at both mount joints: about 1 mm per side, 3 mm behind the block, and 15–20 degrees of rotation with translation. The user explicitly confirmed that both the tightest 4.35 mm sleeve and the T-keeper were installed. This was not an omitted-part assembly error.

The old 26 mm block and tapered cradle explain the broad gaps geometrically. v2.2 uses a fitted tapered foot, a fused-in 4.35 mm split socket, wider mounting necks, and a new preload clip captured by the reused keeper and revised cover. It enlarges the cable passage to 10 mm and supplies thinner, labeled 3.20/3.35 key pairs. The new clip requires relief pockets in the new rear. Existing horn, keeper and stand are reused. TP20 clearance and board position are preserved.

New files live separately in `exports_v2_2`; see its `START_HERE.md` for print sequence, assumptions and assembly. Original print files remain historical evidence. Native-solid results are in `checks/v2_2_report.json`, and export validation is in `checks/mesh_v2_2_report.json`. Intentional elastic contact does not establish real spring force or retention. Physical fit of this revision remains unverified.
