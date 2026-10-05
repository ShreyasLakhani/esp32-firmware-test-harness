"""Small wrapper around wokwi-client for the sim tests.

Sim time only moves when we ask it to (wait_until_simulation_time),
so timing checks do not depend on how fast CI is.
"""
import json
import re
import threading
import time
from pathlib import Path

from wokwi_client import WokwiClientSync

from tools import frame as pyframe

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / ".pio" / "build" / "esp32"
STEP_S = 0.05
POT_START = 512 / 1023  # "value": "512" in diagram.json


class SimTimeout(AssertionError):
    pass


class Node:
    def __init__(self, token, diagram=ROOT / "diagram.json"):
        self.client = WokwiClientSync(token)
        self.client.connect()
        self.client.upload_file("diagram.json", Path(diagram))
        parts = json.loads(Path(diagram).read_text())["parts"]
        self.has_imu = any(p["id"] == "imu" for p in parts)
        self.client.upload_file("firmware.bin", BUILD / "firmware.bin")
        self.client.upload_file("firmware.elf", BUILD / "firmware.elf")
        self._lock = threading.Lock()
        self._buf = ""
        self.lines = []
        self.cursor = 0
        self.t = 0.0
        self.started = False

    # ---- sim control ----

    def start(self):
        """(Re)start the sim from reset and wait for READY."""
        self.client.stop_serial_monitors()
        with self._lock:
            self._buf = ""
            self.lines = []
        self.cursor = 0
        if not self.started:
            self.client.start_simulation(firmware="firmware.bin", elf="firmware.elf", pause=True)
            self.started = True
        else:
            self.client.restart_simulation(pause=True)
        self.client.last_pause_nanos = 0
        self.t = 0.0
        # restart keeps the part controls from the last test, so put them back
        self.reset_controls()
        self.client.serial_monitor(self._on_serial)
        self.wait_line(r"^READY$", timeout=5)

    def close(self):
        try:
            self.client.disconnect()
        except Exception:
            pass

    def advance(self, seconds):
        self.t += seconds
        self.client.wait_until_simulation_time(self.t)
        time.sleep(0.02)  # let the serial callback catch up

    def _on_serial(self, data):
        text = data.decode("utf-8", errors="replace") if isinstance(data, (bytes, bytearray)) else str(data)
        with self._lock:
            self._buf += text
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                self.lines.append(line.rstrip("\r"))

    # ---- serial ----

    def send(self, cmd):
        self.client.serial_write(cmd + "\n")

    def mark(self):
        """Only look at lines after this point."""
        with self._lock:
            self.cursor = len(self.lines)

    def _new_lines(self, start):
        with self._lock:
            return self.lines[start:]

    def wait_line(self, pattern, timeout=3.0):
        rx = re.compile(pattern)
        start = self.cursor
        end_t = self.t + timeout
        while True:
            for i, line in enumerate(self._new_lines(start)):
                m = rx.search(line)
                if m:
                    self.cursor = start + i + 1
                    return m
            if self.t >= end_t:
                raise SimTimeout(f"no line matching {pattern!r} in {timeout}s sim time. last lines: {self.lines[-8:]}")
            self.advance(STEP_S)

    def command(self, cmd, timeout=1.0):
        """Send a command and return the first reply line (not a frame or event)."""
        self.mark()
        self.send(cmd)
        m = self.wait_line(r"^(?!\$D,|EVT )(.+)$", timeout)
        return m.group(1)

    def frames(self, count, timeout=None):
        """Wait for the next `count` frames and parse them."""
        timeout = timeout or count * 0.5 + 1.5
        out = []
        while len(out) < count:
            m = self.wait_line(r"^\$D,.*$", timeout)
            out.append(pyframe.parse(m.group(0)))
        return out

    def no_line(self, pattern, seconds):
        """Run for `seconds` and check nothing matched."""
        start = self.cursor
        self.advance(seconds)
        rx = re.compile(pattern)
        hits = [line for line in self._new_lines(start) if rx.search(line)]
        assert not hits, f"unexpected lines: {hits}"

    # ---- parts ----

    def reset_controls(self):
        """Same start values as diagram.json."""
        self.client.set_control("pot", "position", POT_START)
        self.client.set_control("btn", "pressed", 0)
        if self.has_imu:
            for name, value in (("accelX", 0.0), ("accelY", 0.0), ("accelZ", 1.0)):
                self.client.set_control("imu", name, value)

    def pot(self, position):
        self.client.set_control("pot", "position", float(position))

    def press(self, hold=0.1):
        self.client.set_control("btn", "pressed", 1)
        self.advance(hold)
        self.client.set_control("btn", "pressed", 0)
        self.advance(0.05)

    def led(self):
        return bool(self.client.read_pin("led", "A")["value"])

    def screenshot(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return self.client.save_framebuffer_png("lcd", path)

    def vcd(self):
        return self.client.read_vcd()


def pot_adc(position):
    return round(position * 4095)
