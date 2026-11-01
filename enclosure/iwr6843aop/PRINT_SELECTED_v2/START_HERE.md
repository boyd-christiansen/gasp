# Selected v2 enclosure print set

**v2.1 correction — reprint only `01_rear_flat.stl`.** This file now includes a 6 mm clearance opening for TP20, the upright ground test point. The other seven STL files are unchanged from the set already sent to print. A separately named replacement is also provided as `exports_v2_1/01_rear_TP20_clearance.stl` / `.3mf` in the main project. The corrected rear needs a physical dry fit; keep the test point upright.

This set uses the user's physical fit-test choices: 3.35 mm keys and a 4.35 mm stand sleeve. These are existing variants; the enclosure and sliding hooks have not been changed.

Print each of the eight STL files once at 100% scale. Files 04a and 04b are intentionally identical: the enclosure needs two keys.

| File | Print orientation |
| --- | --- |
| 01_rear_flat.stl | Flat outside back on bed, cavity up |
| 02_sliding_front.stl | Outside face on bed, hooks up |
| 03_aperture_shroud.stl | Wide mouth/flange on bed, legs up |
| 04a_locking_key_3p35.stl | As supplied, flat |
| 04b_locking_key_3p35.stl | As supplied, flat |
| 05_detachable_heel.stl | As supplied, socket axis upright |
| 06_heel_keeper.stl | Wide head on bed, stem up |
| 07_stand_socket_4p35.stl | Flange on bed |

You may reuse the undamaged 3.35 mm key and 4.35 mm sleeve from the test plate. If doing so, skip file 04a and file 07; print 04b to supply the second key.

Use the same printer, PLA and process settings as the successful fit tests. All files are in their intended print orientation. The heel's outward stud-head shoulders may need small local supports; inspect the sliced preview. Avoid filling the key slots, socket bore or vents with automatic supports.

The original `two_locking_keys.stl` uses 3.20 mm keys. This selected set supplies 3.35 mm keys instead.

The first slider test moved smoothly, but its isolated hook could rock out of engagement. Full enclosure retention and printed flex are still unverified; do not treat the fit tests as approval of the complete assembly. The approximately 1 mm reported take-up also remains unresolved against the 0.30 mm nominal clearance.

Assembly instructions are in `ASSEMBLY_GUIDE.md`. Its original full-print table describes the generic alternatives; use the eight files in this folder for the user's selected fit.
