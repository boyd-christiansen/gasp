"""TI SDK 3.x OOB UART packets. This is NOT the People Counting TLV dialect.

SDK 3.x TLV lengths are payload lengths, excluding the eight-byte TL header.
The whole packet is padded to 32 bytes. IQ is signed int16, imaginary first.
"""
from dataclasses import dataclass, field
import struct
import numpy as np

MAGIC = bytes.fromhex("0201040306050807")
HEADER = struct.Struct("<8s8I")
TL = struct.Struct("<II")
MAX_PACKET = 2 * 1024 * 1024
COMPLEX_TYPES = (4, 8)  # azimuth; AOP azimuth/elevation static heatmap
ROI_TYPE = 0x53565031  # Our optional firmware extension, SVP1
ROI_HEADER = struct.Struct("<6HI")


@dataclass
class Frame:
    number: int
    version: int
    platform: int
    cpu_cycles: int
    subframe: int
    raw: bytes
    tlvs: dict[int, bytes] = field(default_factory=dict)

    def complex_heatmap(self, range_bins: int) -> np.ndarray | None:
        if ROI_TYPE in self.tlvs:
            payload = self.tlvs[ROI_TYPE]
            if len(payload) < ROI_HEADER.size:
                raise ValueError("Truncated custom ROI header")
            version, total, first, count, channels, reserved, period_us = ROI_HEADER.unpack_from(payload)
            if (version != 1 or total != range_bins or reserved != 0 or not period_us
                    or not 1 <= channels <= 12 or not 1 <= count <= total or first+count > total
                    or len(payload) != ROI_HEADER.size + count*channels*4):
                raise ValueError("Unsupported or malformed custom ROI packet")
            pairs = np.frombuffer(payload, dtype="<i2", offset=ROI_HEADER.size).reshape(count, channels, 2)
            z = np.zeros((total, channels), dtype=np.complex64)
            z[first:first+count] = pairs[..., 1].astype(np.float32) + 1j*pairs[..., 0]
            return z
        for kind in (8, 4):
            payload = self.tlvs.get(kind)
            if payload is None:
                continue
            if len(payload) % (range_bins * 4):
                raise ValueError("Complex heatmap length disagrees with configured range bins")
            channels = len(payload) // (range_bins * 4)
            if not 1 <= channels <= 12:
                raise ValueError("Unsupported antenna count; check firmware/profile dialect")
            iq = np.frombuffer(payload, dtype="<i2").reshape(range_bins, channels, 2)
            return (iq[..., 1].astype(np.float32) + 1j * iq[..., 0]).astype(np.complex64)
        return None

    def range_profile(self) -> np.ndarray | None:
        payload = self.tlvs.get(2)
        if payload is None:
            return None
        if len(payload) % 2:
            raise ValueError("Malformed range profile")
        return np.frombuffer(payload, dtype="<u2").astype(np.float32)


class Parser:
    def __init__(self):
        self.buffer = bytearray()
        self.bad_packets = 0
        self.discarded_bytes = 0

    def feed(self, data: bytes) -> list[Frame]:
        self.buffer.extend(data)
        result = []
        while True:
            pos = self.buffer.find(MAGIC)
            if pos < 0:
                discard = max(0, len(self.buffer) - 7)
                self.discarded_bytes += discard
                del self.buffer[:discard]
                break
            if pos:
                self.discarded_bytes += pos
                del self.buffer[:pos]
            if len(self.buffer) < HEADER.size:
                break
            magic, version, size, platform, num, cpu, objects, n_tlv, sub = HEADER.unpack_from(self.buffer)
            if not HEADER.size <= size <= MAX_PACKET or n_tlv > 64:
                self.bad_packets += 1
                del self.buffer[0]
                continue
            if len(self.buffer) < size:
                break
            packet = bytes(self.buffer[:size])
            try:
                offset, tlvs = HEADER.size, {}
                for _ in range(n_tlv):
                    if offset + TL.size > size:
                        raise ValueError("Truncated TLV header")
                    kind, length = TL.unpack_from(packet, offset)
                    offset += TL.size
                    if length > size - offset or kind in tlvs:
                        raise ValueError("Truncated or duplicate TLV")
                    tlvs[kind] = packet[offset:offset + length]
                    offset += length
                if size - offset > 31:
                    raise ValueError("Unexpected padding; not SDK 3.x OOB framing")
                result.append(Frame(num, version, platform, cpu, sub, packet, tlvs))
                del self.buffer[:size]
            except ValueError:
                self.bad_packets += 1
                del self.buffer[0]
        return result


def encode_frame(number: int, signal: np.ndarray, kind: int = 8) -> bytes:
    """Synthetic/test packet generator using the actual UART wire format."""
    iq = np.stack([signal.imag, signal.real], axis=-1)
    payload = np.clip(np.rint(iq), -32768, 32767).astype("<i2").tobytes()
    size = HEADER.size + TL.size + len(payload)
    padded = (size + 31) // 32 * 32
    return (HEADER.pack(MAGIC, 0x03060200, padded, 0xA6843, number, 0, 0, 1, 0)
            + TL.pack(kind, len(payload)) + payload + bytes(padded - size))
