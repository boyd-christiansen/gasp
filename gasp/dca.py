"""Native UDP DCA1000 support, restricted to headerless 16-bit complex ADC.

Protocol: TI DCA1000-Protocol.pdf and SWRA581B. No TI GUI or DLL is used.
Physical wiring, FPGA firmware, NIC configuration and ADC lane mapping must
still be verified with real hardware. Packet loss is recorded, never hidden.
"""
import json
from pathlib import Path
import socket
import struct
import threading
import time
from ipaddress import IPv4Address
import numpy as np
from .storage import atomic_json

HEADER, FOOTER = 0xA55A, 0xEEAA
CONNECT, VERSION, CONFIG, PACKET, START, STOP = 9, 14, 3, 11, 5, 6
DATA_PORT = 4098


def command_packet(command, payload=b""):
    if len(payload) > 504:
        raise ValueError("DCA command payload too large")
    return struct.pack("<HHH", HEADER, command, len(payload)) + payload + struct.pack("<H", FOOTER)


def parse_reply(data, expected):
    if len(data) != 8:
        raise ValueError("Expected eight-byte DCA command response")
    head, cmd, status, foot = struct.unpack("<4H", data)
    if (head, cmd, foot) != (HEADER, expected, FOOTER):
        raise ValueError("DCA command response framing mismatch")
    if expected != VERSION and status:
        raise RuntimeError(f"DCA command {cmd:#x} failed with status {status:#x}")
    return status


class DCAControl:
    def __init__(self, host_ip="192.168.33.30", board_ip="192.168.33.180", port=4096, timeout=2, local_port=None):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.sock.bind((host_ip, port if local_port is None else local_port))
        except BaseException:
            self.sock.close()
            raise
        self.sock.settimeout(timeout)
        self.board = (board_ip, port)

    def command(self, code, payload=b""):
        self.sock.sendto(command_packet(code, payload), self.board)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            try:
                data, address = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            if address == self.board and len(data) == 8:
                # A delayed reply/async error must not masquerade as this command's acknowledgement.
                head, received, status, foot = struct.unpack("<4H", data)
                if received == 10 and head == HEADER and foot == FOOTER:
                    raise RuntimeError(f"DCA asynchronous system error {status:#x}")
                if received == code:
                    return parse_reply(data, code)
        raise TimeoutError("No DCA acknowledgement")

    def configure(self):
        self.command(CONNECT)
        version = self.command(VERSION)
        # RAW logging, two LVDS lanes (AR1642 mode), capture, Ethernet, 16 bit, 30s timer.
        self.command(CONFIG, bytes([1, 2, 1, 2, 3, 30]))
        # 1472 total UDP bytes incl 10-byte header, 25us at 125MHz; reserved=0.
        self.command(PACKET, struct.pack("<HHH", 1472, 3125, 0))
        return version

    def close(self):
        self.sock.close()


class PacketWriter:
    def __init__(self, path, max_bytes=512*1024*1024):
        self.path = Path(path)
        self.file = self.path.open("xb+")
        self.max_bytes = max_bytes
        self.intervals = []
        self.packets = self.duplicates = self.out_of_order = 0
        self.seen = set()
        self.last_sequence = None

    def add(self, packet):
        if len(packet) < 11:
            raise ValueError("Truncated DCA UDP packet")
        sequence = int.from_bytes(packet[:4], "little")
        offset = int.from_bytes(packet[4:10], "little")
        payload = packet[10:]
        if len(payload) > 1456 or offset + len(payload) > self.max_bytes:
            raise ValueError("DCA payload or byte offset exceeds configured capture limit")
        key = (sequence, offset)
        if key in self.seen:
            self.duplicates += 1
            return
        if self.last_sequence is not None and sequence < self.last_sequence:
            self.out_of_order += 1
        self.last_sequence = sequence
        self.seen.add(key)
        self.file.seek(offset)
        self.file.write(payload)
        self.intervals.append((offset, offset+len(payload)))
        self.packets += 1

    def finish(self):
        self.file.flush()
        self.file.close()
        cursor, missing = 0, []
        for start, end in sorted(self.intervals):
            if start > cursor:
                missing.append([cursor, start])
            cursor = max(cursor, end)
        return {"packets": self.packets, "duplicates": self.duplicates, "out_of_order": self.out_of_order,
                "bytes": cursor, "missing_intervals": missing,
                "missing_bytes": sum(b-a for a, b in missing),
                "tail_loss_unknown": True}


class CaptureCancelled(RuntimeError):
    pass


class DCASource:
    """Armed, exclusive hardware connection. Each take retains its own raw capture.

    UDP reception runs independently of CLI acknowledgements and stopping, so
    buffered data is drained before the raw file is closed. Plots are generated
    after capture; this source does not pretend to be a live UART heatmap.
    """
    synthetic = False
    kind = "dca1000"

    def __init__(self, profile, cli_port, host_ip, board_ip):
        if not profile.lvds_adc or profile.heatmap_enabled:
            raise ValueError("DCA requires the raw ADC LVDS profile with USB heatmap disabled")
        self.host_ip, self.board_ip = str(IPv4Address(host_ip)), str(IPv4Address(board_ip))
        if self.host_ip == "0.0.0.0" or self.host_ip == self.board_ip and not IPv4Address(self.host_ip).is_loopback:
            raise ValueError("Choose the Mac's Ethernet IPv4 address and a different DCA IPv4 address")
        self.profile, self.cli_port = profile, cli_port
        self.cli = self.control = self.udp = None
        self.cancel = threading.Event()
        self.lock = threading.RLock()
        self.state = {"status": "disconnected", "packets": 0, "bytes": 0,
                      "host_ip": self.host_ip, "board_ip": self.board_ip}

    def start(self):
        from .transport import RadarCLI
        from .profile import commands
        try:
            # Bind both ports before sending configuration: an invalid NIC or a
            # competing application fails before the radar is reconfigured.
            self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 8*1024*1024)
            self.udp.bind((self.host_ip, DATA_PORT))
            self.udp.settimeout(0.1)
            self.control = DCAControl(self.host_ip, self.board_ip)
            self.cli = RadarCLI(self.cli_port)
            for line in commands(self.profile.text):
                if line != "sensorStart":
                    self.cli.command(line)
            version = self.control.configure()
            self.configuration_log = list(self.cli.log)
            with self.lock:
                self.state.update(status="armed", fpga_version_word=version,
                                  receive_buffer_bytes=self.udp.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF))
        except BaseException:
            self.close()
            raise

    def snapshot(self):
        with self.lock:
            return self.state.copy()

    def capture(self, output, duration=5, on_started=None, context=None, stop_event=None):
        if not self.cli or not self.control or not self.udp:
            raise ValueError("Arm the DCA source first")
        if not 0 < duration <= 25:
            raise ValueError("Limit a DCA take to 25 seconds to leave arming margin within the FPGA's 30-second timer")
        output = Path(output)
        output.mkdir(parents=True, exist_ok=False)
        (output / "radar.cfg").write_text(self.profile.text)
        report = {"schema": 2, "status": "arming", "profile": self.profile.summary(),
                  "source": "dca1000", "synthetic": False, "host_ip": self.host_ip,
                  "board_ip": self.board_ip, "requested_duration_s": duration,
                  "started_wall_ns": time.time_ns(),
                  "fpga_version_word": self.state["fpga_version_word"],
                  "configuration_log": self.configuration_log,
                  "adc_layout": "2lane-complex-I0-I1-Q0-Q1-rx-noninterleaved",
                  "timing": "ADC-relative schedule; host start estimate, no hardware media synchronization",
                  "context": context or {}}
        atomic_json(output / "manifest.json", report)
        with self.lock:
            self.state.update(status="arming", packets=0, bytes=0, duplicates=0, out_of_order=0)
        writer = PacketWriter(output / "adc.bin")
        done, first = threading.Event(), threading.Event()
        receive_errors = []
        log_start = len(self.cli.log)
        error = None
        # Remove packets left from a previous take before the new START command.
        self.udp.setblocking(False)
        try:
            while True:
                self.udp.recvfrom(65536)
        except BlockingIOError:
            pass
        finally:
            self.udp.settimeout(0.1)

        def receive():
            try:
                while not done.is_set():
                    try:
                        data, address = self.udp.recvfrom(65536)
                    except socket.timeout:
                        continue
                    if address[0] != self.board_ip:
                        continue
                    writer.add(data)
                    stamp = time.monotonic_ns()
                    if not first.is_set():
                        report["first_packet_monotonic_ns"] = stamp
                        first.set()
                    report["last_packet_monotonic_ns"] = stamp
                    with self.lock:
                        self.state.update(packets=writer.packets, bytes=max(self.state["bytes"],
                            int.from_bytes(data[4:10], "little") + len(data)-10),
                            duplicates=writer.duplicates, out_of_order=writer.out_of_order)
            except Exception as exc:
                receive_errors.append(exc)
                first.set()

        worker = threading.Thread(target=receive, daemon=True, name="dca-udp")
        worker.start()
        try:
            self.control.command(START)
            report["radar_start_command_monotonic_ns"] = time.monotonic_ns()
            self.cli.command("sensorStart")
            for _ in range(20):
                if self.cancel.is_set() or first.wait(0.1):
                    break
            if self.cancel.is_set():
                raise CaptureCancelled("Capture cancelled; partial raw files retained")
            if receive_errors:
                raise receive_errors[0]
            if not first.is_set():
                raise RuntimeError("No DCA packets received; check Ethernet IPv4, LVDS wiring and firmware")
            report["prompt_ready_monotonic_ns"] = time.monotonic_ns()
            with self.lock:
                self.state["status"] = "recording"
            if on_started:
                on_started(report["prompt_ready_monotonic_ns"])
            deadline = time.monotonic() + duration
            while time.monotonic() < deadline:
                if stop_event is not None and stop_event.is_set():
                    break
                if self.cancel.wait(min(0.05, max(0, deadline-time.monotonic()))):
                    raise CaptureCancelled("Capture cancelled; partial raw files retained")
                if receive_errors:
                    raise receive_errors[0]
            report["prompt_end_monotonic_ns"] = time.monotonic_ns()
        except BaseException as exc:
            error = exc
        finally:
            with self.lock:
                self.state["status"] = "stopping"
            # Keep receiving while sensorStop is acknowledged, then drain packets
            # already in the NIC/FPGA. Neither silence nor offsets prove tail completeness.
            for target, code, name in ((self.cli, "sensorStop", "sensor_stop_error"),
                                       (self.control, STOP, "capture_stop_error")):
                try:
                    target.command(code)
                except Exception as exc:
                    report[name] = str(exc)
                    if error is None or isinstance(error, CaptureCancelled):
                        error = RuntimeError(f"Hardware stop failed: {exc}; disconnect before another capture")
            time.sleep(0.2)
            done.set()
            worker.join(1)
            if self.cancel.is_set() and error is None:
                error = CaptureCancelled("Capture cancelled; partial raw files retained")
            if receive_errors and error is None:
                error = receive_errors[0]
            report.update(writer.finish())
            report["cli_log"] = self.cli.log[log_start:]
            report["status"] = "cancelled" if isinstance(error, CaptureCancelled) else "failed" if error else "complete"
            if error:
                report["error"] = str(error)
            atomic_json(output / "manifest.json", report)
            with self.lock:
                self.state.update(status="armed" if error is None or isinstance(error, CaptureCancelled) else "error",
                                  last_capture=report)
        if error:
            raise error
        return report

    def close(self):
        if self.snapshot()["status"] == "error":
            # Retry stopping after a failed take before releasing exclusive ports.
            for target, code in ((self.cli, "sensorStop"), (self.control, STOP)):
                if target:
                    try:
                        target.command(code)
                    except Exception:
                        pass
        for obj in (self.udp, self.control, self.cli):
            if obj:
                obj.close()
        self.udp = self.control = self.cli = None
        with self.lock:
            self.state["status"] = "disconnected"


def capture(profile, output, cli_port, host_ip, board_ip, duration=5):
    source = DCASource(profile, cli_port, host_ip, board_ip)
    try:
        source.start()
        return source.capture(output, duration)
    finally:
        source.close()


def decode_adc(path, profile, missing_intervals=(), max_bytes=512*1024*1024):
    """Return TX/RX complex range FFTs per chirp loop with physical sample times.

    Explicit supported layout: 2 LVDS lanes, complex16, non-interleaved RX,
    TDM TX, no HSI/software headers. Do not silently autodetect raw layouts.
    """
    path = Path(path)
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError("Capture too large for this bounded importer; split into shorter captures")
    frame_bytes = profile.adc_samples * profile.rx_count * profile.tx_count * profile.loops * 4
    count = size // frame_bytes
    if not count:
        raise ValueError("No complete ADC frames")
    raw = np.memmap(path, dtype="<i2", mode="r", shape=(count, frame_bytes // 2))
    good = [i for i in range(count) if not any(a < (i+1)*frame_bytes and b > i*frame_bytes for a, b in missing_intervals)]
    if not good:
        raise ValueError("Every ADC frame intersects a packet-loss interval")
    blocks = raw[good].reshape(-1, 4).astype(np.float32)
    iq = np.empty((len(blocks), 2), dtype=np.complex64)
    iq[:, 0], iq[:, 1] = blocks[:, 0] + 1j*blocks[:, 2], blocks[:, 1] + 1j*blocks[:, 3]
    cube = iq.reshape(len(good), profile.loops, profile.tx_count, profile.rx_count, profile.adc_samples)
    cube -= cube.mean(axis=-1, keepdims=True)
    ranges = np.fft.fft(cube * np.hanning(profile.adc_samples), n=profile.range_bins, axis=-1).astype(np.complex64)
    # [frame, loop, range, TX, RX] -> common model representation [time, range, virtual antenna].
    signal = ranges.transpose(0, 1, 4, 2, 3).reshape(-1, profile.range_bins, profile.tx_count*profile.rx_count)
    timestamps = [round((i*profile.frame_period_ms*1e-3 + loop*profile.tx_count*profile.chirp_period_us*1e-6)*1e9)
                  for i in good for loop in range(profile.loops)]
    return signal, np.asarray(timestamps, dtype=np.int64), {"complete_frames": count, "kept_frames": len(good),
        "dropped_frames": count-len(good), "kept_frame_indices": good, "trailing_bytes": size % frame_bytes,
        "note": "Burst timing preserved; validate lane/channel mapping on physical hardware before speech experiments"}


def import_capture(store, folder, session, label, articulation="silent", notes="", recording_id=None, extra=None):
    """Shared UI/CLI importer; keep raw loss offsets and original sample indices."""
    from .profile import parse_profile
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text())
    if manifest["status"] != "complete":
        raise ValueError("Capture was not completed successfully")
    profile = parse_profile(manifest["profile"]["text"])
    if session["source"] != "dca1000" or session["profile"]["sha256"] != profile.sha256:
        raise ValueError("Existing DCA session source/profile mismatch")
    iq, stamps, quality = decode_adc(folder / "adc.bin", profile, manifest["missing_intervals"])
    indices = np.asarray([i*profile.loops+j for i in quality["kept_frame_indices"]
                          for j in range(profile.loops)], dtype=np.uint32)
    epoch = manifest.get("radar_start_command_monotonic_ns", 1)
    return store.save_trial(session["id"], label, stamps+epoch, iq, indices, extra={
        "source": "dca1000", "synthetic": False, "articulation": articulation, "notes": notes,
        "recording_id": recording_id, "adc_quality": quality, "raw_capture_dir": str(folder.resolve()),
        "sample_clock": "ADC-relative chirp schedule; TDM channels have within-loop time offsets",
        "server_monotonic_start_ns": epoch,
        "prompt_ready_monotonic_ns": manifest.get("prompt_ready_monotonic_ns"),
        "prompt_end_monotonic_ns": manifest.get("prompt_end_monotonic_ns"),
        "raw_quality": {k: manifest[k] for k in ("packets", "bytes", "missing_bytes", "duplicates",
                                                "out_of_order", "tail_loss_unknown") if k in manifest}, **(extra or {})})
