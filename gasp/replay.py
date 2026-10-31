"""Views derived from original samples. Display decimation never edits capture data."""
from collections import OrderedDict
import json
import threading
import numpy as np
from .protocol import Parser


class Replay:
    def __init__(self, store):
        self.store = store
        self.lock = threading.Lock()
        self.cache = OrderedDict()
        self.bytes = 0

    def load(self, sid, tid):
        path = self.store.trial_dir(sid, tid)
        stat = (path / "radar.npz").stat()
        key = (sid, tid, stat.st_mtime_ns, stat.st_size)
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return self.cache[key][0]
        arr = self.store.load_signal(sid, tid)
        arr["relative_s"] = (arr["timestamps_ns"]-arr["timestamps_ns"][0])/1e9
        aux = {}
        raw = path / "uart.bin"
        if raw.exists():
            parser = Parser()
            with raw.open("rb") as stream:
                while block := stream.read(65536):
                    for frame in parser.feed(block):
                        if 5 in frame.tlvs or 1 in frame.tlvs:
                            aux[frame.number] = frame
        arr["aux"] = aux
        cost = sum(v.nbytes for v in arr.values() if isinstance(v, np.ndarray)) + sum(len(f.raw) for f in aux.values())
        with self.lock:
            if key in self.cache:
                return self.cache[key][0]
            while self.cache and self.bytes + cost > 192 * 1024**2:
                _, (_, old_cost) = self.cache.popitem(last=False)
                self.bytes -= old_cost
            if cost <= 192 * 1024**2:
                self.cache[key] = (arr, cost)
                self.bytes += cost
        return arr

    def preview(self, sid, tid, range_bin=8, antenna=0, limit=900):
        arr = self.load(sid, tid)
        z, t = arr["iq"], arr["relative_s"]
        r, a = min(max(0, range_bin), z.shape[1]-1), min(max(0, antenna), z.shape[2]-1)
        indices = np.unique(np.linspace(0, len(t)-1, min(limit, len(t)), dtype=int))
        chosen = z[:, r, a]
        numbers = arr["frame_numbers"].astype(np.int64)
        gaps = np.flatnonzero(((numbers[1:]-numbers[:-1]) & 0xffffffff) > 1)
        profile = self.store.session(sid)["profile"]
        phase = np.unwrap(np.angle(z[:, r, a]))
        phase -= phase[0]
        kinds = {k for f in arr["aux"].values() for k in f.tlvs}
        return dict(time_s=t[indices].tolist(), sample_indices=indices.tolist(),
                    all_time_s=t.tolist(), signal_time_s=t.tolist(),
                    total_samples=len(t), duration_s=float(t[-1]), shape=list(z.shape),
                    first_timestamp_ns=str(int(arr["timestamps_ns"][0])),
                    range_step_m=profile["range_step_m"],
                    range_m=(np.arange(z.shape[1])*profile["range_step_m"]).tolist(),
                    range_time=np.abs(z[indices]).mean(axis=2).round(3).tolist(),
                    phase=phase.tolist(), i=chosen.real.tolist(), q=chosen.imag.tolist(),
                    selected_bin=r, antenna=a,
                    gaps=[[float(t[i]),float(t[i+1])] for i in gaps],
                    capabilities=dict(range_time=True,phase=True,iq=True,
                        range_doppler=5 in kinds or profile["lvds_adc"], points=1 in kinds or profile.get("points_enabled",False)),
                    display_decimated=len(indices)<len(t),
                    timing="Radar host-arrival time" if not profile["lvds_adc"] else "ADC-relative burst schedule")

    def frame(self, sid, tid, index):
        arr = self.load(sid, tid)
        index = min(max(0, index), len(arr["iq"])-1)
        z = arr["iq"][index]
        session = self.store.session(sid)
        profile = session["profile"]
        bins = max(8, 1 << (profile["loops"]-1).bit_length())
        frame = arr["aux"].get(int(arr["frame_numbers"][index]))
        rd = frame.range_doppler(z.shape[0], bins) if frame else None
        points = frame.points() if frame else None
        unit = "TI log-magnitude units"
        if profile["lvds_adc"]:
            numbers = arr["frame_numbers"]
            frame_number = int(numbers[index]) // profile["loops"]
            keep = np.flatnonzero(numbers // profile["loops"] == frame_number)
            if len(keep) == profile["loops"]:
                cube = arr["iq"][keep] * np.hanning(len(keep))[:,None,None]
                rd = 20*np.log10(np.maximum(1e-9,np.abs(np.fft.fftshift(np.fft.fft(cube,n=bins,axis=0),axes=0))).mean(axis=2).T)
                unit = "Relative dB"
        # Approximate centre frequency from the saved profile, not a universal 60 GHz constant.
        p = next(row.split() for row in profile["text"].splitlines() if row.startswith("profileCfg "))
        centre = float(p[2])*1e9 + float(p[8])*1e12*(float(p[4])*1e-6+profile["adc_samples"]/(float(p[11])*1000)/2)
        velocity_step = 299792458/(2*centre*profile["tx_count"]*profile["chirp_period_us"]*1e-6*bins)
        return dict(index=index,time_s=float(arr["relative_s"][index]),
                    range_magnitude=np.abs(z).mean(axis=1).tolist(),
                    range_doppler=rd.tolist() if rd is not None else None,
                    doppler_velocity_m_s=((np.arange(bins)-bins//2)*velocity_step).tolist(),
                    doppler_unit=unit,points=points.tolist() if points is not None else None,
                    spatial_note="Firmware Cartesian detections; verify placement/range/phase calibration")
