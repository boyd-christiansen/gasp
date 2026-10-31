from dataclasses import dataclass, asdict
import hashlib
import math
from pathlib import Path


@dataclass(frozen=True)
class Profile:
    text: str
    sha256: str
    range_bins: int
    range_step_m: float
    frame_period_ms: float
    rx_count: int
    tx_count: int
    adc_samples: int
    loops: int
    chirp_period_us: float
    heatmap_enabled: bool
    lvds_adc: bool
    doppler_enabled: bool = False
    points_enabled: bool = False

    @property
    def doppler_bins(self):
        return max(8, 1 << (self.loops - 1).bit_length())

    @property
    def frame_hz(self):
        return 1000 / self.frame_period_ms

    def summary(self, baud=921600):
        # Worst-case all active AOP virtual antennas, range profile and stats.
        packet_bytes = 40 + 8 + self.range_bins * 2 + 8 + 24 + 8 + 28
        if self.heatmap_enabled:
            packet_bytes += 8 + self.range_bins * self.rx_count * self.tx_count * 4
        if self.doppler_enabled:
            packet_bytes += 8 + self.range_bins * self.doppler_bins * 2
        if self.points_enabled:
            # Conservative point-cloud reserve, including side information.
            packet_bytes += 16 + 1024 * 20
        packet_bytes = math.ceil(packet_bytes / 32) * 32
        rate = packet_bytes * self.frame_hz
        return {**asdict(self), "frame_hz": self.frame_hz,
                "adc_bytes_per_frame": self.adc_samples * self.rx_count * self.tx_count * self.loops * 4,
                "adc_bytes_s": round(self.adc_samples * self.rx_count * self.tx_count * self.loops * 4 * self.frame_hz),
                "complex_samples_s": self.loops * self.frame_hz,
                "burst_duration_ms": self.loops * self.tx_count * self.chirp_period_us / 1000,
                "estimated_uart_bytes_s": round(rate), "uart_capacity_bytes_s": baud // 10,
                "uart_utilization": round(rate / (baud / 10), 3)}


def commands(text: str):
    for raw in text.splitlines():
        line = raw.split("%", 1)[0].strip()
        if line:
            yield line


def parse_profile(text: str) -> Profile:
    rows = [line.split() for line in commands(text)]
    groups: dict[str, list[list[str]]] = {}
    for row in rows:
        groups.setdefault(row[0], []).append(row)
    for key in ("channelCfg", "adcCfg", "profileCfg", "chirpCfg", "frameCfg"):
        if len(groups.get(key, [])) != 1 and key != "chirpCfg":
            raise ValueError(f"Exactly one {key} is required (simple-frame SDK 3.x only)")
    if "advFrameCfg" in groups or "bpmCfg" in groups and any(int(x[-1]) for x in groups["bpmCfg"]):
        raise ValueError("Advanced frames and BPM are not supported")
    channel, adc, p, f = [groups[k][0] for k in ("channelCfg", "adcCfg", "profileCfg", "frameCfg")]
    if len(p) < 15 or len(f) < 8 or len(channel) < 4 or len(adc) < 3:
        raise ValueError("Incomplete SDK 3.x profile")
    if adc[1:3] != ["2", "1"]:
        raise ValueError("Use complex 16-bit ADC: adcCfg 2 1")
    if not 0 < int(channel[1]) <= 15 or not 0 < int(channel[2]) <= 7:
        raise ValueError("RX/TX channel bitmasks exceed IWR6843AOP hardware")
    buffers = groups.get("adcbufCfg", [])
    if len(buffers) != 1 or buffers[0][1:] != ["-1", "0", "1", "1", "1"]:
        raise ValueError("Use adcbufCfg -1 0 1 1 1: complex, I/Q unswapped, RX non-interleaved, one chirp threshold")
    samples, fs, slope = int(p[10]), float(p[11]) * 1000, float(p[8]) * 1e12
    start, idle, adc_start, ramp = map(float, p[2:6])
    loops, period = int(f[3]), float(f[5])
    first, last = int(f[1]), int(f[2])
    if not (64 <= samples <= 1024 and fs > 0 and slope > 0 and period > 0 and loops > 0):
        raise ValueError("Invalid sampling/frame parameters")
    if int(f[4]) != 0 or int(f[6]) != 1 or first != 0:
        raise ValueError("Use continuous, software-triggered frames starting at chirp zero")
    if adc_start + samples / fs * 1e6 > ramp + 1e-6:
        raise ValueError("ADC acquisition exceeds chirp ramp")
    if not (60 <= start and start + ramp * slope / 1e15 <= 64):
        raise ValueError("This profile must remain within the board's 60–64 GHz band")
    rx, tx = int(channel[1]).bit_count(), int(channel[2]).bit_count()
    if not (1 <= rx <= 4 and 1 <= tx <= 3 and last + 1 == tx):
        raise ValueError("Only one sequential TDM chirp per enabled transmitter is supported")
    chirps = groups.get("chirpCfg", [])
    masks = []
    for i in range(tx):
        matching = [r for r in chirps if int(r[1]) <= i <= int(r[2])]
        if len(matching) != 1 or len(matching[0]) < 9:
            raise ValueError("Each chirp needs exactly one chirpCfg")
        r = matching[0]
        if r[3] != p[1] or any(float(x) != 0 for x in r[4:8]):
            raise ValueError("Chirp profile variations are not supported")
        mask = int(r[8])
        if mask.bit_count() != 1 or not mask & int(channel[2]):
            raise ValueError("Each TDM chirp must use one enabled TX")
        masks.append(mask)
    if len(set(masks)) != tx or tx * loops * (idle + ramp) > period * 1000:
        raise ValueError("Invalid TDM schedule or chirps exceed frame period")
    if "clutterRemoval" in groups and int(groups["clutterRemoval"][0][-1]):
        raise ValueError("Disable static clutter removal to preserve the static complex stream")
    gui = groups.get("guiMonitor", [["guiMonitor", "-1", "0", "0", "0", "0", "0", "0"]])[0]
    lvds = groups.get("lvdsStreamCfg", [["lvdsStreamCfg", "-1", "0", "0", "0"]])[0]
    if len(gui) != 8 or len(lvds) != 5:
        raise ValueError("Expected SDK 3.x guiMonitor/lvdsStreamCfg syntax")
    if int(lvds[3]) and (int(lvds[2]) != 0 or int(lvds[3]) != 1 or int(lvds[4]) != 0):
        raise ValueError("DCA decoder requires headerless ADC-only LVDS, no software stream")
    canonical = "\n".join(commands(text)) + "\n"
    return Profile(canonical, hashlib.sha256(canonical.encode()).hexdigest(),
                   1 << (samples - 1).bit_length(), 299792458 * fs / (2 * slope * (1 << (samples - 1).bit_length())),
                   period, rx, tx, samples, loops, idle + ramp, int(gui[5]) > 0, int(lvds[3]) == 1,
                   int(gui[6]) > 0, int(gui[2]) > 0)


def bundled_profile(name="usb-phase-20hz") -> Profile:
    allowed = {"usb-phase-20hz", "usb-phase-10hz", "usb-doppler-10hz", "usb-spatial-2hz", "dca-raw"}
    if name not in allowed:
        raise ValueError("Unknown bundled profile")
    return parse_profile((Path(__file__).parent / "profiles" / (name + ".cfg")).read_text())
