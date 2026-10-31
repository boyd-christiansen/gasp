from collections import deque
import threading
import time
import uuid
import numpy as np
from .transport import SerialSource, SimSource
from .dca import DCASource, CaptureCancelled, import_capture


class Engine:
    def __init__(self, store):
        self.store = store
        self.lock = threading.RLock()
        self.lifecycle = threading.Lock()
        self.source = None
        self.profile = None
        self.session = None
        self.ring = deque(maxlen=1200)
        self.status = "disconnected"
        self.error = None
        self.last_packet_ns = None
        self.frames = self.gaps = self.duplicates = 0
        self.complex_frames = 0
        self.last_number = None
        self.tlv_types = set()
        self.recording = None
        self.record_results = {}
        self.recorder_thread = None
        self.last_trial = None

    def connect(self, kind, profile, cli_port=None, data_port=None, data_baud=921600,
                host_ip="192.168.33.30", board_ip="192.168.33.180", confirm_layout=False):
        with self.lifecycle:
            with self.lock:
                if self.source or self.recording:
                    raise ValueError("Disconnect before changing sources")
                self.profile = profile
                self.session = None
                self.last_trial = None
                self.ring.clear()
                self.error = None
                self.frames = self.gaps = self.duplicates = 0
                self.complex_frames = 0
                self.magnitude = np.array([])
                self.last_number = self.last_packet_ns = None
                self.tlv_types.clear()
                self.status = "connecting"
            source = None
            try:
                if kind == "simulator":
                    source = SimSource(profile, self._frame, self._error)
                elif kind == "serial":
                    source = SerialSource(cli_port, data_port, profile, self._frame, self._error, data_baud)
                elif kind == "dca1000":
                    if not cli_port or not confirm_layout:
                        raise ValueError("Select a radar command port and the supported two-lane ADC decoder")
                    source = DCASource(profile, cli_port, host_ip, board_ip)
                else:
                    raise ValueError("Unknown source")
                self.source = source
                source.start()
                with self.lock:
                    if self.status != "error":
                        self.status = "connected"
            except BaseException:
                if source and self.source is source:
                    # SerialSource.start already closes on a configuration failure.
                    if kind in {"simulator", "dca1000"}:
                        source.close()
                self.source = None
                self.status = "disconnected"
                raise

    def disconnect(self):
        with self.lifecycle:
            with self.lock:
                if self.recording:
                    raise ValueError("Wait for the active trial to finish")
                source, self.source = self.source, None
            if source:
                source.close()
            self.status = "disconnected"

    def close(self):
        if self.recording:
            self.recording["_cancel"].set()
            self.recording["_stop"].set()
            if isinstance(self.source, DCASource):
                self.source.cancel.set()
        if self.recorder_thread:
            self.recorder_thread.join(35)
        self.disconnect()

    def _error(self, message):
        with self.lock:
            self.error, self.status = message, "error"

    def _frame(self, frame, stamp):
        try:
            z = frame.complex_heatmap(self.profile.range_bins)
            magnitude = frame.range_profile()
            with self.lock:
                self.frames += 1
                self.last_packet_ns = stamp
                self.tlv_types.update(frame.tlvs)
                if frame.subframe != 0:
                    raise ValueError("Advanced/subframe packets unsupported; use simple frame OOB firmware")
                if self.last_number is not None:
                    delta = (frame.number - self.last_number) & 0xffffffff
                    if delta == 0:
                        self.duplicates += 1
                        return
                    if delta > 0x7fffffff:
                        raise ValueError("Frame counter moved backwards; board restarted—reconnect in a new session")
                    self.gaps += max(0, delta - 1)
                self.last_number = frame.number
                if z is not None:
                    self.complex_frames += 1
                    item = {"t": stamp, "number": frame.number, "iq": z, "raw": frame.raw}
                    self.ring.append(item)
                    if self.recording:
                        self.recording["items"].append(item)
                if z is None and magnitude is not None:
                    self.magnitude = magnitude
        except Exception as exc:
            self._error(str(exc))

    def create_session(self, name, subject, notes, collection=None):
        with self.lock:
            if self.status != "connected" or not self.source:
                raise ValueError("Connect a source first")
            if self.recording:
                raise ValueError("A trial is active")
            kind = getattr(self.source, "kind", "simulator" if self.source.synthetic else "serial")
            self.session = self.store.create_session(name, subject, kind, self.profile, notes, collection,
                                                    getattr(self.source, "device_info", {}))
            self.last_trial = None
            return self.session

    def record(self, label, duration, articulation, notes, collection=None):
        with self.lock:
            if self.recording:
                raise ValueError("A trial is already recording")
            if not self.session or self.status != "connected":
                raise ValueError("Create a session with an active source first")
            is_dca = isinstance(self.source, DCASource)
            if is_dca and duration > 25:
                raise ValueError("DCA takes are limited to 25 seconds")
            if duration > 180:
                raise ValueError("USB passages are limited to three minutes; split longer scripts into passages")
            if not is_dca and (not self.ring or (time.monotonic_ns() - self.ring[-1]["t"]) > 2e9):
                raise ValueError("No recent complex heatmap; check guiMonitor, profile and firmware")
            rid = uuid.uuid4().hex
            started = time.monotonic_ns()
            self.recording = {"id": rid, "label": label, "duration_s": duration,
                              "started_ns": started, "items": [], "collection": collection,
                              "_stop": threading.Event(), "_cancel": threading.Event(), "events": []}
            if collection and not is_dca:
                self.recording["items"] = [x for x in self.ring if x["t"] >= started-350_000_000]
            if self.source.synthetic:
                self.source.label = label
                self.source.started = time.monotonic()
            self.record_results[rid] = {"id": rid, "status": "arming" if is_dca else "recording", "session_id": self.session["id"],
                                        "server_monotonic_start_ns": started, "server_wall_start_ns": time.time_ns()}
            if is_dca:
                self.source.cancel.clear()
            self.recorder_thread = threading.Thread(target=self._finish_dca_record if is_dca else self._finish_record,
                args=(rid, duration, articulation, notes), daemon=True, name="trial-recorder")
            self.recorder_thread.start()
            return self.record_results[rid].copy()

    def stop_record(self, rid):
        with self.lock:
            if not self.recording or self.recording["id"] != rid:
                raise ValueError("No active capture with this ID")
            result = self.record_results[rid]
            if result["status"] != "recording":
                raise ValueError("Wait until the sensor is recording")
            if time.monotonic_ns()-result["server_monotonic_start_ns"] < 500_000_000:
                raise ValueError("Record for at least half a second")
            self.recording["stop_requested_ns"] = time.monotonic_ns()
            self.recording["_stop"].set()
            result["status"] = "processing"
            return result.copy()

    def cancel_record(self, rid):
        with self.lock:
            if not self.recording or self.recording["id"] != rid:
                raise ValueError("No active capture with this ID")
            if isinstance(self.source, DCASource) and self.record_results[rid]["status"] == "processing":
                raise ValueError("Raw capture has ended; wait for decoding, then reject the saved take")
            self.recording["_cancel"].set()
            self.recording["_stop"].set()
            if isinstance(self.source, DCASource):
                self.source.cancel.set()
            self.record_results[rid]["status"] = "cancelling"
            return self.record_results[rid].copy()

    def add_event(self, rid, event):
        with self.lock:
            if not self.recording or self.recording["id"] != rid:
                raise ValueError("Capture is no longer active")
            if len(self.recording["events"]) >= 20:
                raise ValueError("Too many capture events")
            self.recording["events"].append(dict(event, received_monotonic_ns=time.monotonic_ns()))
            return {"ok": True}

    def collection_fields(self, rec):
        if not rec.get("collection"):
            return {}
        return dict(rec["collection"], schema=2, capture_events=rec["events"],
                    stop_requested_monotonic_ns=rec.get("stop_requested_ns"),
                    timing_note="Software/host timestamps; radar-to-audio offset must be validated on hardware")

    def _finish_dca_record(self, rid, duration, articulation, notes):
        with self.lock:
            source, session, rec = self.source, self.session, self.recording
        output = self.store.root / "raw" / session["id"] / rid
        def started(stamp):
            with self.lock:
                if not source.cancel.is_set():
                    self.record_results[rid].update(status="recording", server_monotonic_start_ns=stamp)
        try:
            source.capture(output, duration, on_started=started, context={
                "recording_id": rid, "session_id": session["id"], "label": rec["label"],
                "subject": session["subject"], "articulation": articulation, "notes": notes}, stop_event=rec["_stop"])
            with self.lock:
                if rec["_cancel"].is_set():
                    raise CaptureCancelled("Capture cancelled; raw diagnostics retained")
                self.record_results[rid]["status"] = "processing"
            meta = import_capture(self.store, output, session, rec["label"], articulation, notes, rid, self.collection_fields(rec))
            arr = self.store.load_signal(session["id"], meta["id"])
            with self.lock:
                self.ring.clear()
                # Retain a bounded preview. It is not a live continuous source.
                for t, n, z in zip(arr["timestamps_ns"][-1200:], arr["frame_numbers"][-1200:], arr["iq"][-1200:]):
                    self.ring.append({"t": int(t), "number": int(n), "iq": z, "raw": b""})
                self.frames = meta["adc_quality"]["kept_frames"]
                self.complex_frames = meta["frames"]
                self.gaps = meta["adc_quality"]["dropped_frames"]
                self.duplicates = meta["raw_quality"]["duplicates"]
                self.record_results[rid].update(status="complete", trial=meta)
                self.last_trial = {"session_id": session["id"], "trial_id": meta["id"]}
        except CaptureCancelled as exc:
            with self.lock:
                self.record_results[rid].update(status="cancelled", error=str(exc))
        except Exception as exc:
            with self.lock:
                self.record_results[rid].update(status="failed", error=str(exc))
                if source.snapshot()["status"] != "armed":
                    self.error, self.status = str(exc), "error"
        finally:
            with self.lock:
                self.recording = None

    def _finish_record(self, rid, duration, articulation, notes):
        with self.lock:
            rec = self.recording
        rec["_stop"].wait(duration)
        if rec.get("collection") and not rec["_cancel"].is_set():
            with self.lock:
                self.record_results[rid]["status"] = "processing"
            rec["_cancel"].wait(.25)
        with self.lock:
            items, session = rec["items"], self.session
            self.recording = None
            if self.source and self.source.synthetic:
                self.source.label = "rest"
            result = self.record_results[rid]
            try:
                if rec["_cancel"].is_set():
                    result.update(status="cancelled")
                    return
                if self.status == "error":
                    raise ValueError(self.error)
                elapsed = (time.monotonic_ns()-rec["started_ns"])/1e9
                if len(items) < max(8, self.profile.frame_hz * min(duration, elapsed) * 0.7):
                    raise ValueError("Too few frames: incomplete trial; no training sample saved")
                meta = self.store.save_trial(session["id"], rec["label"], [x["t"] for x in items],
                    [x["iq"] for x in items], [x["number"] for x in items], [x["raw"] for x in items],
                    {"articulation": articulation, "notes": notes, "recording_id": rid,
                     "server_monotonic_start_ns": rec["started_ns"], "source": session["source"],
                     "synthetic": session["synthetic"], **self.collection_fields(rec)})
                result.update(status="complete", trial=meta)
                self.last_trial = {"session_id": session["id"], "trial_id": meta["id"]}
            except Exception as exc:
                result.update(status="failed", error=str(exc))

    def snapshot(self, selected_bin=8, antenna=0):
        with self.lock:
            now = time.monotonic_ns()
            age = (now - self.last_packet_ns) / 1e9 if self.last_packet_ns else None
            parser = getattr(self.source, "parser", None)
            is_dca = isinstance(self.source, DCASource)
            state = {"status": self.status, "error": self.error,
                     "synthetic": bool(self.source and self.source.synthetic),
                     "source": getattr(self.source, "kind", "simulator" if self.source and self.source.synthetic else "serial" if self.source else None),
                     "capture_ready": self.status == "connected" and not self.recording and (is_dca or bool(self.ring) and (now-self.ring[-1]["t"]) < 2e9),
                     "live_decode_available": not is_dca,
                     "last_trial": self.last_trial,
                     "dca": self.source.snapshot() if is_dca else None,
                     "frames": self.frames, "complex_frames": self.complex_frames,
                     "frame_gaps": self.gaps, "duplicates": self.duplicates,
                     "bad_packets": parser.bad_packets if parser else 0,
                     "discarded_bytes": parser.discarded_bytes if parser else 0,
                     "packet_age_s": age, "tlv_types": sorted(self.tlv_types),
                     "complex_available": not is_dca and bool(self.ring) and (now-self.ring[-1]["t"]) < 2e9,
                     "session": self.session,
                     "recording": {k: v for k, v in self.recording.items() if k != "items" and not k.startswith("_")} if self.recording else None,
                     "profile": self.profile.summary() if self.profile else None}
            if self.ring:
                recent = list(self.ring)[-160:]
                z = recent[-1]["iq"]
                selected_bin = min(max(0, selected_bin), z.shape[0]-1)
                antenna = min(max(0, antenna), z.shape[1]-1)
                values = np.array([x["iq"][selected_bin, antenna] for x in recent])
                phase = np.unwrap(np.angle(values))
                phase -= phase[0]
                dt = (recent[-1]["t"] - recent[0]["t"]) / 1e9
                state.update(range_magnitude=np.abs(z).mean(axis=1).tolist(),
                             phase=phase.tolist(), selected_bin=selected_bin, antenna=antenna,
                             antenna_count=z.shape[1], measured_hz=(len(recent)-1)/dt if dt else 0)
            else:
                state.update(range_magnitude=getattr(self, "magnitude", np.array([])).tolist(), phase=[], measured_hz=0)
            return state
