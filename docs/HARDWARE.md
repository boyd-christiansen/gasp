# Hardware bring-up on the Mac

## USB first

1. Identify the physical board revision and installed firmware. The target is **IWR6843AOP ES2 with SDK 3.x OOB AOP firmware**, not IWRL6843 and not a People Counting/vital-sign binary. TI renamed some older AOP example directories between releases; select by device/antenna/revision, not directory spelling alone.
2. Connect its onboard USB-to-UART bridge using a data-capable cable. Run `.venv/bin/python -m subvocal doctor`. Normally two serial endpoints appear. Prefer `/dev/cu.*` on macOS. If neither appears, check cable, bridge driver and board USB routing. [Silicon Labs VCP drivers](https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers) may be needed for the CP2105 bridge. Install the matching official macOS driver yourself if required by the OS.
3. Determine which endpoint is the CLI and which is binary data. Documentation differs across EVM generations; do not blindly map the lower port number, Enhanced/Standard wording, or suffix to a role. The app lists USB metadata and makes you choose explicitly. Default CLI is 115200; data is 921600.
4. Put the board in normal functional mode, with USB UART routing appropriate to its revision. Use the matching TI hardware guide for switch positions. Do not copy switch settings from a different revision.
5. Launch the workbench, select **USB serial** and **USB phase 10 Hz**, choose the two ports, inspect the config, then connect. Configuration halts on the first rejected or unacknowledged command. The reported error includes the offending command.
6. Confirm incoming frames **and** a complex signal. TLV 8 is the AOP azimuth/elevation zero-Doppler complex buffer. TLV 4 is the legacy azimuth buffer. Point clouds and magnitude profiles alone are insufficient for this pipeline.
7. Mount the sensor on a stable stand at mouth/chin height, initially 40–60 cm away. Keep the antenna unobstructed. Choose the live range bin at the face return. Record rest, deliberate jaw/lip movements, and repeated silent syllables. Check gaps, malformed packets, measured frame rate and whether phase survives between frames.
8. Create a new session with distance, angle, revision, firmware version and conditions in notes. Record silent phrases and rest/negative examples. Switch to 20 Hz only if the 10 Hz path is stable. The example profiles have valid software bounds but have not been tested against your physical board.

## If the firmware differs

Do not treat configuration acceptance or an open port as proof of compatibility. The decoder is deliberately restricted to SDK 3.x OOB packets. A different demo can reuse a TLV number for another payload. If it does not export compatible IQ, use a matching OOB firmware image or integrate the optional custom stream.

Firmware flashing is separate from serial runtime configuration. TI's R4/DSP compiler, SDK, bootloader procedure and exact board/silicon target must match. This repository does not include an unverified `.bin` and does not flash anything automatically. The initial USB route can run on existing compatible firmware; it does not require TI's acquisition GUI.

## DCA1000 fallback

Use this if you need the full time-resolved ADC stream rather than a frame's zero-Doppler summary. The supported stack uses DCA1000EVM and MMWAVEICBOOST. Depending on EVM revision, the carrier is needed for the LVDS connector and routing.

### Capture in the workbench

The source selector now supports **DCA1000 · raw ADC over Ethernet**. Disconnect the current source before switching; create a fresh session after switching. DCA and USB recordings use different source/profile identities, and cannot be pooled in one model.

1. Connect **IWR6843AOPEVM → MMWAVEICBOOST → DCA1000EVM** using the matching LVDS connector/routing for the actual revisions. Keep the radar's USB command connection to the Mac. Connect DCA Ethernet to the Mac, normally through a Gigabit Ethernet adapter. Follow TI's hardware guide for power and switch positions; the app does not flash firmware or program the DCA EEPROM.
2. Configure the Mac Ethernet adapter manually, normally `192.168.33.30/24`. The DCA defaults to `192.168.33.180`. Enter the actual addresses in the app. UDP command/data ports are 4096/4098. The app binds both ports before reconfiguring the radar, so an unavailable adapter/address or occupied port fails early. macOS may request local-network permission.
3. Select the **DCA raw ADC** profile and the radar **command** serial port. No binary USB data port is needed. Select the supported **two-lane complex16 ADC decoder**. This is an explicit format selection, not evidence that the physical lane mapping has already been validated.
4. Click **Connect source**. The app configures the radar, checks DCA acknowledgements/version, and arms the connection. Raw streaming remains off between takes.
5. Create a session, choose the phrase deck, and click **Record next trial**. After the countdown the app starts the DCA/radar and waits for data. **Wait for RECORDING before mouthing the phrase.** The requested duration begins after packets are observed. Raw capture starts earlier and stops later; those host timing markers are retained in the manifest. Media synchronization remains approximate.
6. On completion, the app stops the radar/DCA, drains pending UDP packets, retains `adc.bin`, `manifest.json` and `radar.cfg`, then imports range FFTs for every complete, loss-free ADC frame. Range/phase plots show the last completed take. Review, relabel, exclude, and train on the imported trials as usual. Review also offers raw ADC, manifest and configuration downloads.
7. **Cancel DCA capture** stops the hardware and retains partial raw files without adding a training trial. A transport/stop failure reports an error and requires disconnect/reconnect. Closing the server requests cancellation before releasing the connection.

Captures are bounded to **25 seconds / 512 MiB**, leaving arming margin within the configured 30-second FPGA timer. Raw artifacts live in `data/raw/<session-id>/<recording-id>/`. The app never overwrites an existing capture directory.

The default experimental profile uses **50 ADC frames/s, 16 chirp loops/frame and 12 TX×RX channels**, about **2.46 MB/s**. Each frame's chirp activity occupies about **2.26 ms**, followed by a frame gap. The average 800 chirp-loop samples/s is **not uniform 800 Hz sampling**, and is not a reproduction of mSilent's 240 Hz schedule. The importer retains burst timing and known missing-frame indices. Verify a known reflector and phase behavior before speech collection.

DCA supports prompted recordings, training/evaluation, and prediction of completed takes. Train on matching DCA sessions, then use **Predict last completed DCA take** in Train & evaluate, or **Predict saved take** in a trial's Review view. Compatible models are filtered by source, profile and participant in Review. Results identify training playback, previously held-out data, or a new take; model inputs contain radar only. Signal/model checksums and loss thresholds are checked before prediction. The app's “Classify the last 3 seconds” button requires a continuous USB source. Continuous raw inference is a separate future acquisition mode.

### CLI alternative

1. Wire LVDS, power and USB control according to the TI guides for the actual revisions. Connect the DCA1000 Ethernet port to the Mac's Ethernet adapter.
2. Set the adapter's IPv4 address to the DCA1000's configured destination subnet. Defaults are host `192.168.33.30`, board `192.168.33.180`, mask `255.255.255.0`. No router is needed for a direct connection. The app does not change system networking or rewrite DCA EEPROM settings. If another network uses this subnet, resolve the conflict before capture.
3. Close other radar applications and disconnect the USB workbench source, so only one process owns the CLI. The raw profile uses **16-bit complex ADC, RX non-interleaved, sequential single-TX TDM, two LVDS lanes, no HSI header and no software stream**. The decoder will not automatically guess another layout.
4. Capture a short labelled utterance:

```sh
.venv/bin/python -m subvocal dca-record \
  --cli-port /dev/cu.YOUR_COMMAND_PORT \
  --output data/raw/visit-01/add-note-001 --seconds 5
```

The Python driver sends FPGA/configuration/record commands over UDP 4096 and receives data on UDP 4098. It does not require Windows, mmWave Studio, a DLL, or a detached service. It stops the radar and attempts to stop the DCA recorder on errors, including Ctrl-C. Captures are limited to 25 seconds / 512 MiB. Existing output directories are never overwritten.

5. Inspect `manifest.json`. Missing byte intervals, duplicates and out-of-order packets are reported. Offsets reconstruct the raw file; holes are not silently presented as real samples. UDP cannot establish that the tail is complete, so trailing completeness remains explicitly unknown.
6. Validate the layout using a simple known reflector/range target first. Then import:

```sh
.venv/bin/python -m subvocal dca-import data/raw/visit-01/add-note-001 \
  --label 'add a note' --subject Boyd --confirm-layout
```

The result prints a `session_id`. Append subsequent captures from the same visit using `--session-id ID`; omit that option for a new visit. Frames intersecting known loss intervals are discarded. The importer preserves the nonuniform chirp-burst timing, performs a range FFT, and exposes `[time, range, TX×RX]` complex data to the same review/training system. It retains the raw capture path and quality summary. There are sub-millisecond bursts separated by frame gaps; sample arrival is not assumed uniform.

The DCA transport and decoder are covered by protocol/ADC fixtures. **Actual FPGA firmware compatibility, NIC delivery, lane ordering and RF data still require a hardware test.**
