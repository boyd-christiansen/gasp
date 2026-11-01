# Hardware and enclosures

[Documentation](README.md) · [Hardware bring-up](HARDWARE.md)

Choose a capture path and enclosure below. These are prototypes; current revisions still need physical connector, cable, strength, thermal and RF validation. Print a fit coupon before the large parts, and print individual part files rather than display assemblies.

## Capture options

| Source | Hardware and connection | Recorded signal |
|---|---|---|
| Simulator | Mac only | Clearly labelled synthetic fixtures for software checks |
| USB | IWR6843AOPEVM with compatible SDK 3.x OOB AOP firmware; command and data USB serial ports | Frame-averaged complex range/antenna heatmaps, not raw ADC |
| DCA1000 | IWR6843AOPEVM + MMWAVEICBOOST + DCA1000EVM; radar command USB and DCA Ethernet | Raw ADC packets plus decoded range FFTs; prompted takes up to 25 seconds |

USB and DCA data have different source/profile identities and cannot be pooled in one model. Example RF profiles, physical lane ordering, and signal quality still need board validation. [Follow the connection guide →](HARDWARE.md)

## Full capture stack

The v1.2 tabletop enclosure holds **IWR6843AOPEVM Rev G + MMWAVEICBOOST Rev B + DCA1000EVM Rev A** together. It has an open radar window, sculpted ripple cover with matching vents, indexed 0–40° upward aim, cable tie stations, and a removable rear cable guide.

<p>
  <img src="../enclosure/capture_stack/renders/assembled_20.png" alt="Full capture-stack enclosure at 20 degrees" width="300">
  <img src="../enclosure/capture_stack/renders/exploded_assembly.png" alt="Exploded capture enclosure with separate ripple cover and front bezel" width="300">
</p>

- [Assembly and printing](../enclosure/capture_stack/README.md)
- [Hardware counts](../enclosure/capture_stack/HARDWARE.md) and [cable routing](../enclosure/capture_stack/CABLE_ROUTING.md)
- [STEP/STL/GLB files](../enclosure/capture_stack/exports), [parametric source](../enclosure/capture_stack/src), and [check reports](../enclosure/capture_stack/checks)

There are nine printable STL designs; the largest part is 214 × 195 mm in its supplied print orientation. Assembly exports include non-printable board references. The supplied short LVDS cable's installed bend remains to be checked with the actual boards.

## Single-board enclosure v2.2

The latest standalone USB enclosure is **v2.2**. It adds clearance for the USB cable's molded strain relief, keeps the TP20 test-point opening, and refines the aperture keys and desktop mount. It holds the **IWR6843AOPEVM only**; use the full capture stack above for MMWAVEICBOOST + DCA1000EVM.

<p>
  <img src="../enclosure/iwr6843aop/renders/v2_2_desktop_front.png" alt="Front view of the single-board v2.2 enclosure on the desktop stand" width="300">
  <img src="../enclosure/iwr6843aop/renders/v2_2_mount_installation.png" alt="Installation of the fitted v2.2 mount and preload clip" width="300">
</p>

- [v2.2 revision guide](../enclosure/iwr6843aop/README_v2_2.md) and [print/assembly instructions](../enclosure/iwr6843aop/exports_v2_2/START_HERE.md)
- [STEP, STL, 3MF and GLB exports](../enclosure/iwr6843aop/exports_v2_2), including a six-piece small-parts plate and a two-piece replacement case plate
- [Parametric source](../enclosure/iwr6843aop/src/enclosure_v2_2.py), [manifest](../enclosure/iwr6843aop/MANIFEST_v2_2.json), [checksums](../enclosure/iwr6843aop/SHA256SUMS_v2_2.txt), and [mesh validation](../enclosure/iwr6843aop/checks/mesh_v2_2_report.json)

Reuse the existing shroud, desktop stand and T-shaped keeper. Replace the old mounting block and separate socket sleeve with the fitted mount and preload clip. Native CAD and exported mesh checks pass; physical fit, insertion force, strength and RF performance remain unverified. Print and test the small parts first.

## Earlier single-board revisions

The [v2 guide](../enclosure/iwr6843aop/README_v2.md), [selected v2/v2.1 print set](../enclosure/iwr6843aop/PRINT_SELECTED_v2/START_HERE.md) and [fit-test notes](../enclosure/iwr6843aop/FIT_TEST_NOTES_v2.md) document the earlier printed iterations.

The smaller **IWR6843AOPEVM v1.2** enclosure is for standalone USB capture. It has interchangeable solid-radome and open-aperture fronts, printed PCB washers, standard 2.5 mm cable-tie slots, and a captive metal ¼″-20 arm mount. It does not house MMWAVEICBOOST or DCA1000EVM.

<p>
  <img src="../enclosure/iwr6843aop/renders/desktop_dock_assembled.png" alt="Single-board enclosure in the tabletop dock" width="300">
  <img src="../enclosure/iwr6843aop/renders/desktop_dock_open.png" alt="Open-aperture front on the same tabletop dock" width="300">
</p>

The **drop-in desktop dock** holds either v1.2 front at a fixed 20° upward aim. It uses a smooth locating pin and heel cradle, needs no additional metal hardware, and has a USB cable groove. The enclosure rests under gravity and lifts out along the pin axis; it has no latch or threaded lock.

- [Enclosure v1.2 assembly and printing](../enclosure/iwr6843aop/README_v1_2.md), [hardware list](../enclosure/iwr6843aop/HARDWARE_v1_2.md), and [enclosure print files](../enclosure/iwr6843aop/exports_v1_2)
- [Reinforced rear shell v1.3](../enclosure/iwr6843aop/README_v1_3.md) and [replacement print files](../enclosure/iwr6843aop/exports_v1_3): wider, tapered PCB supports and a sloped roof over the mount opening, following feedback from the v1.2 print. Reuse the front, retainer, washers, hardware and dock. This revision is not yet print-tested.
- [Desktop dock guide](../enclosure/iwr6843aop/DESKTOP_STAND.md), [dock print files](../enclosure/iwr6843aop/exports_dock), and [dock manifest](../enclosure/iwr6843aop/DESKTOP_STAND_MANIFEST.json)
- [Parametric source](../enclosure/iwr6843aop/src) and [fit/mesh reports](../enclosure/iwr6843aop/checks)

The dock footprint is 100 × 120 mm. Print the optional cradle-fit sample first and check the actual nut, rear retainer, and cable. The original [v1.1 enclosure guide](../enclosure/iwr6843aop/README.md) and exports remain available for reference. For a new standalone build, start with v2.2 above.
