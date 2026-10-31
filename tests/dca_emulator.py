"""Test-only radar CLI + actual UDP DCA peer. Never used by production capture.

Signals are fixtures, not physical speech. The preview runner uses an isolated
dataset and names its subject/session EMULATED to avoid claiming hardware proof.
"""
import os
import pty
import select
import socket
import struct
import threading
import time
import numpy as np
from gasp import dca
from gasp.profile import bundled_profile


class DCAEmulator:
    def __init__(self, data_port=4098):
        self.profile = bundled_profile('dca-raw')
        self.master, self.slave = pty.openpty()
        self.cli_port = os.ttyname(self.slave)
        self.control = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control.bind(('127.0.0.1', 0))
        self.control_port = self.control.getsockname()[1]
        self.sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sender.bind(('127.0.0.1', 0))
        if data_port is None:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as available:
                available.bind(('127.0.0.1', 0))
                data_port = available.getsockname()[1]
        self.data_port = data_port
        self.done = threading.Event()
        self.lock = threading.Lock()
        self.radar_running = self.capturing = False
        self.no_data = False
        self.fail_stop = False
        self.offset = self.sequence = self.frame = 0
        self.commands, self.dca_commands = [], []
        self.threads = [threading.Thread(target=fn, daemon=True) for fn in (self._cli, self._control, self._data)]
        self.original_control = dca.DCAControl

    def start(self):
        for worker in self.threads:
            worker.start()
        return self

    def make_control(self, host, board):
        return self.original_control(host, board, port=self.control_port, local_port=0)

    def _cli(self):
        pending = b''
        while not self.done.is_set():
            if not select.select([self.master], [], [], .05)[0]:
                continue
            try:
                pending += os.read(self.master, 4096)
            except OSError:
                return
            while b'\n' in pending:
                line, pending = pending.split(b'\n', 1)
                line = line.decode(errors='replace').strip()
                if not line:
                    continue
                self.commands.append(line)
                if line == 'sensorStop' and self.fail_stop:
                    os.write(self.master, b'Error -99: fixture stop failure\n')
                    continue
                with self.lock:
                    if line == 'sensorStart':
                        self.radar_running = True
                    elif line == 'sensorStop':
                        self.radar_running = False
                os.write(self.master, b'Done\n')

    def _control(self):
        while not self.done.is_set():
            if not select.select([self.control], [], [], .05)[0]:
                continue
            data, peer = self.control.recvfrom(1024)
            if len(data) < 8:
                continue
            header, command, count = struct.unpack('<3H', data[:6])
            if header != dca.HEADER or len(data) != count+8:
                continue
            self.dca_commands.append(command)
            with self.lock:
                if command == dca.START:
                    self.offset = self.frame = 0
                    self.sequence = 1
                    self.capturing = True
                elif command == dca.STOP:
                    self.capturing = False
            status = 0x1234 if command == dca.VERSION else 0
            self.control.sendto(struct.pack('<4H', dca.HEADER, command, status, dca.FOOTER), peer)

    def _adc_frame(self):
        p = self.profile
        sample = np.arange(p.adc_samples)
        antenna = np.arange(p.tx_count*p.rx_count).reshape(p.tx_count, p.rx_count, 1)
        loop = np.arange(p.loops).reshape(p.loops, 1, 1, 1)
        phase = .2*np.sin(self.frame*.2 + loop*.01) + antenna*.04
        z = 1000*np.exp(2j*np.pi*8*sample/p.adc_samples + 1j*phase)
        pair = z.reshape(-1, 2)
        return np.stack([pair[:, 0].real, pair[:, 1].real, pair[:, 0].imag, pair[:, 1].imag], axis=1).astype('<i2').tobytes()

    def _data(self):
        while not self.done.wait(self.profile.frame_period_ms/1000):
            with self.lock:
                if not self.capturing or not self.radar_running or self.no_data:
                    continue
                payload = self._adc_frame()
                for start in range(0, len(payload), 1456):
                    chunk = payload[start:start+1456]
                    packet = struct.pack('<I', self.sequence)+self.offset.to_bytes(6, 'little')+chunk
                    self.sender.sendto(packet, ('127.0.0.1', self.data_port))
                    self.sequence += 1
                    self.offset += len(chunk)
                self.frame += 1

    def close(self):
        self.done.set()
        for worker in self.threads:
            worker.join(1)
        for sock in (self.control, self.sender):
            sock.close()
        os.close(self.master)
        os.close(self.slave)
