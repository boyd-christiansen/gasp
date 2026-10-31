"""A versioned baseline representation, not a validated speech decoder."""
from dataclasses import dataclass, asdict
import numpy as np


@dataclass
class FeatureSpec:
    version: int = 1
    range_min_m: float = 0.2
    range_max_m: float = 0.85
    time_steps: int = 64
    range_steps: int = 16
    antennas: int = 4

    def to_dict(self):
        return asdict(self)


def features(iq, timestamps_ns, range_step_m, spec: FeatureSpec):
    z = np.asarray(iq)
    t = np.asarray(timestamps_ns, dtype=np.int64)
    if z.ndim != 3 or len(t) != len(z) or len(z) < 8 or not np.iscomplexobj(z):
        raise ValueError("At least 8 complex frames are required")
    if not np.isfinite(z).all() or np.any(np.diff(t) <= 0):
        raise ValueError("Invalid signal or non-monotonic timestamps")
    if range_step_m <= 0 or not 0 <= spec.range_min_m < spec.range_max_m:
        raise ValueError("Invalid range gate")
    lo = max(0, int(np.ceil(spec.range_min_m / range_step_m)))
    hi = min(z.shape[1], int(np.floor(spec.range_max_m / range_step_m)) + 1)
    if hi - lo < 2 or z.shape[2] < spec.antennas:
        raise ValueError("Range gate or antenna dimensions are incompatible with this model")
    z = z[:, lo:hi, :spec.antennas]
    if np.max(np.abs(z)) == 0:
        raise ValueError("No radar energy in selected gate")
    amp = np.log1p(np.abs(z))
    amp -= np.median(amp, axis=0, keepdims=True)
    phase = np.angle(z[1:] * z[:-1].conj())
    # Phase increments are unreliable in zero/low-amplitude channels.
    power = np.abs(z[1:]) * np.abs(z[:-1])
    phase *= power / (power + np.median(power) * 0.05 + 1e-6)
    phase = np.concatenate([phase[:1], phase], axis=0)
    source_t = (t - t[0]) / (t[-1] - t[0])
    target_t = np.linspace(0, 1, spec.time_steps)
    target_r = np.linspace(0, hi - lo - 1, spec.range_steps)
    blocks = []
    for block in (amp, phase):
        temporal = np.stack([np.interp(target_t, source_t, block[:, r, a])
                             for r in range(block.shape[1]) for a in range(spec.antennas)], axis=1)
        temporal = temporal.reshape(spec.time_steps, hi-lo, spec.antennas)
        spatial = np.stack([np.interp(target_r, np.arange(hi-lo), temporal[i, :, a])
                            for i in range(spec.time_steps) for a in range(spec.antennas)])
        blocks.append(spatial.ravel())
    return np.concatenate([*blocks, [(t[-1]-t[0]) / 1e9]]).astype(np.float32)
