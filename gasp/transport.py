import hashlib
import threading
import time
import numpy as np
from .protocol import Parser, encode_frame


def ports():
    from serial.tools import list_ports
    return [{"device": p.device, "description": p.description, "serial_number": p.serial_number,
             "manufacturer": p.manufacturer, "interface": p.interface, "vid": p.vid, "pid": p.pid}
            for p in list_ports.comports()]


class RadarCLI:
    def __init__(self, port: str, timeout=3.0):
        import serial
        self.serial = serial.Serial(port, 115200, timeout=0.05, write_timeout=2, exclusive=True)
        self.timeout = timeout
        self.log = []

    def command(self, line: str):
        self.serial.reset_input_buffer()
        self.serial.write((line + "\n").encode("ascii"))
        # write_timeout bounds enqueueing; the Done reply confirms delivery.
        # tcdrain/flush can block forever on a backpressured macOS serial/PTY.
        deadline, response = time.monotonic() + self.timeout, bytearray()
        while time.monotonic() < deadline:
            response.extend(self.serial.read(4096))
            text = response.decode("ascii", errors="replace")
            if any(word in text.lower() for word in ("error", "not recognized", "exception", "unsupported")):
                self.log.append({"command": line, "response": text})
                raise RuntimeError(f"Board rejected {line!r}: {text.strip()}")
            if "Done" in text:
                self.log.append({"command": line, "response": text})
                return text
        self.log.append({"command": line, "response": response.decode("ascii", errors="replace")})
        raise TimeoutError(f"No Done acknowledgement for {line!r}; check CLI port and SDK OOB firmware")

    def close(self):
        self.serial.close()


class SerialSource:
    synthetic = False

    def __init__(self, cli_port, data_port, profile, on_frame, on_error, data_baud=921600):
        import serial
        if cli_port == data_port:
            raise ValueError("CLI and data ports must be different")
        if profile.lvds_adc:
            raise ValueError("Use a USB profile here; raw LVDS belongs to the DCA capture command")
        if profile.summary(data_baud)["uart_utilization"] > 0.85:
            raise ValueError("Profile exceeds the safe UART budget; lower frame rate or payload size")
        self.cli = RadarCLI(cli_port)
        try:
            self.data = serial.Serial(data_port, data_baud, timeout=0.1, exclusive=True)
        except BaseException:
            self.cli.close()
            raise
        self.profile, self.on_frame, self.on_error = profile, on_frame, on_error
        self.parser = Parser()
        self.stop = threading.Event()
        self.thread = None

    def start(self):
        from .profile import commands
        try:
            for line in commands(self.profile.text):
                if line != "sensorStart":
                    self.cli.command(line)
            if self.data.baudrate != 921600:
                self.cli.command(f"configDataPort {self.data.baudrate} 0")
            self.data.reset_input_buffer()
            self.thread = threading.Thread(target=self._read, daemon=True, name="radar-uart")
            self.thread.start()
            self.cli.command("sensorStart")
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            while not self.stop.is_set():
                for frame in self.parser.feed(self.data.read(65536)):
                    self.on_frame(frame, time.monotonic_ns())
        except Exception as exc:
            if not self.stop.is_set():
                self.on_error(str(exc))

    def close(self):
        try:
            # Keep draining binary output while the board handles sensorStop.
            # Stopping the reader first can backpressure the device's CLI task.
            self.cli.command("sensorStop")
        except Exception:
            pass
        self.stop.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(2)
        self.data.close()
        self.cli.close()


def synthetic_signal(label, t, range_bins=64, channels=12, seed=0):
    """A deliberately learnable fixture, not a physical silent-speech simulation."""
    rng = np.random.default_rng(seed)
    code = int.from_bytes(hashlib.sha256(label.encode()).digest()[:4], "little")
    r = np.arange(range_bins)[:, None]
    a = np.arange(channels)[None, :]
    envelope = np.exp(-0.5 * ((r - 8) / 2.0) ** 2)
    frequency = 0.8 + (code % 13) * 0.35
    motion = (0.5 * np.sin(2 * np.pi * frequency * t) + 0.2 * np.sin(2 * np.pi * frequency * 2.3 * t))
    phase = 0.2 * r + 0.1 * a + envelope * motion * (1 + a / channels)
    amp = 300 + 5000 * envelope * (1 + 0.08 * np.sin(2 * np.pi * frequency * t))
    return (amp * np.exp(1j * phase) + rng.normal(0, 10, (range_bins, channels))
            + 1j * rng.normal(0, 10, (range_bins, channels))).astype(np.complex64)


class SimSource:
    synthetic = True

    def __init__(self, profile, on_frame, on_error):
        self.profile, self.on_frame, self.on_error = profile, on_frame, on_error
        self.stop = threading.Event()
        self.label = "rest"
        self.thread = None
        self.started = time.monotonic()
        self.parser = Parser()

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True, name="synthetic-radar")
        self.thread.start()

    def _run(self):
        number, period = 0, self.profile.frame_period_ms / 1000
        deadline = time.monotonic()
        try:
            while not self.stop.is_set():
                signal = synthetic_signal(self.label, time.monotonic() - self.started,
                                          self.profile.range_bins, seed=number)
                # Exercise the SAME binary parser as hardware, including fragmentation.
                raw = encode_frame(number, signal)
                self.parser.feed(raw[:19])
                for frame in self.parser.feed(raw[19:]):
                    self.on_frame(frame, time.monotonic_ns())
                number += 1
                deadline += period
                self.stop.wait(max(0, deadline - time.monotonic()))
        except Exception as exc:
            self.on_error(str(exc))

    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(2)
