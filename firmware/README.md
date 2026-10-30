# Optional USB complex-ROI extension

The first route uses the standard SDK complex heatmap and requires no custom firmware. This directory is an **optional portable C packet encoder for a future SDK integration**, not a flashable board image. Its C output is compiled with the Mac C compiler and decoded in the Python tests. It has not been compiled with TI's toolchain or run on the radar.

`phase_roi.c` selects a contiguous range gate from a completed complex `[range][antenna]` buffer and emits an SDK-framed packet with custom TLV `0x53565031` (`SVP1`). It preserves signed imaginary/real values. A 12-bin × 12-antenna gate needs 640 bytes/packet, rather than streaming all 64 bins. At 100 packets/s that is 64 kB/s, within 921600-baud 8N1. Whether radar processing can sustain 100 Hz, and whether the input is coherent enough, must be measured.

## Integration contract

1. Pin the exact TI SDK and AOP ES2 antenna variant matching the board. Locate the existing static-heatmap export code in that SDK's OOB demo; verify its layout, allocation and lifetime from source.
2. Add `phase_roi.c` to that project and pass the existing ready complex range/antenna buffer to `sv_roi_packet`. If using SDK `cmplx16ImRe_t`, verify it has the same signed 16-bit imaginary-then-real field layout. Do not pass the log-magnitude range profile or a detection matrix.
3. Choose range gate bounds using the actual profile's range spacing. Make the configured feature gate a subset of the exported gate. The reference encoder accepts one set of complex values per packet; it does not collect chirps, configure the radar or perform a range FFT.
4. Serialize the returned packet on the data UART from the existing output task, without another concurrent writer. Do not release/reuse the input or output buffers until transmission completes. On cached/shared-memory paths, implement the SDK's cache maintenance and address translation correctly.
5. Disable the full heatmap output to avoid sending both payloads. Set the frame period to a measured sustainable value and update the host profile accordingly. The header reports that period; it does not enforce it.
6. Build with TI's supported R4/DSP compiler and SDK dependencies. Validate the image/device/silicon/revision before a separate flashing step. The Mac host application is already able to decode this custom packet.

No proprietary SDK source or toolchain is included. There is deliberately no guessed SDK patch or universal flash script: old AOP variants use different project paths and processing structures.

## Payload contract

All fields little endian. Standard 40-byte SDK OOB header, TL header `<uint32 type, uint32 payload_length>`, then:

| Offset | Type | Meaning |
| --- | --- | --- |
| 0 | uint16 | Schema version, 1 |
| 2 | uint16 | Total range bins in the radar profile |
| 4 | uint16 | First exported range bin |
| 6 | uint16 | Number of exported bins |
| 8 | uint16 | Virtual antenna count, 1–12 |
| 10 | uint16 | Reserved, zero |
| 12 | uint32 | Frame period in microseconds |
| 16 | int16 pairs | Imaginary, real; antenna varies fastest, then range |

The packet is padded to 32 bytes. The host expands the cropped data into the original range coordinates with zeros outside the gate; those zeros are unobserved, not measured returns. Use only an exported range gate for feature extraction.
