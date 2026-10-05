"""VCD helper checks with a made up capture. sigrok parts skip if sigrok-cli is missing."""
import shutil

import pytest

from tools import vcd_decode

NEED_SIGROK = pytest.mark.skipif(shutil.which("sigrok-cli") is None, reason="sigrok-cli not installed")

HALF = 5000  # ns, 100 kHz clock


class Gen:
    """Builds a small VCD with the same 6 channels as the logic analyzer."""

    def __init__(self):
        self.t = 0
        self.state = {n: 1 for n in vcd_decode.DEFAULT_CHANNELS}
        self.state["SCK"] = 0
        self.events = [(0, dict(self.state))]

    def set(self, **kw):
        self.state.update(kw)
        self.events.append((self.t, dict(self.state)))

    def wait(self, ns=HALF):
        self.t += ns

    def text(self):
        ids = {n: chr(33 + i) for i, n in enumerate(vcd_decode.DEFAULT_CHANNELS)}
        out = ["$timescale 1ns $end", "$scope module logic $end"]
        for n, i in ids.items():
            out.append(f"$var wire 1 {i} {n} $end")
        out += ["$upscope $end", "$enddefinitions $end"]
        prev = {}
        for t, st in self.events:
            lines = [f"{st[n]}{ids[n]}" for n in ids if prev.get(n) != st[n]]
            if lines:
                out.append(f"#{t}")
                out += lines
            prev = st
        out.append(f"#{self.t + HALF}")
        return "\n".join(out) + "\n"

    # I2C, SCL idles high
    def i2c_start(self):
        self.set(SDA=0)
        self.wait()
        self.set(SCL=0)
        self.wait()

    def i2c_byte(self, b):
        for i in range(8):
            self.set(SDA=(b >> (7 - i)) & 1)
            self.wait()
            self.set(SCL=1)
            self.wait()
            self.set(SCL=0)
            self.wait()
        self.set(SDA=0)  # ack from device
        self.wait()
        self.set(SCL=1)
        self.wait()
        self.set(SCL=0)
        self.wait()

    def i2c_stop(self):
        self.set(SDA=0)
        self.wait()
        self.set(SCL=1)
        self.wait()
        self.set(SDA=1)
        self.wait()

    # SPI mode 0
    def spi_bytes(self, data):
        self.set(CS=0)
        self.wait()
        for b in data:
            for i in range(8):
                self.set(MOSI=(b >> (7 - i)) & 1)
                self.wait()
                self.set(SCK=1)
                self.wait()
                self.set(SCK=0)
        self.wait()
        self.set(CS=1)
        self.wait()


def i2c_capture(tmp_path):
    g = Gen()
    g.wait()
    g.i2c_start()
    g.i2c_byte(0x68 << 1)
    g.i2c_byte(0x75)
    g.i2c_stop()
    p = tmp_path / "i2c.vcd"
    p.write_text(g.text())
    return p


def spi_capture(tmp_path):
    g = Gen()
    g.wait()
    g.spi_bytes([0x2A, 0x00, 0xEF])
    p = tmp_path / "spi.vcd"
    p.write_text(g.text())
    return p


def test_parse_vcd_counts_edges(tmp_path):
    vcd = vcd_decode.parse_vcd(spi_capture(tmp_path).read_text())
    assert vcd.timescale_ns == 1.0
    assert vcd.edges("SCK", "rise") == 24
    assert vcd.edges("CS", "fall") == 1


def test_channel_lookup_by_index():
    text = "$timescale 1ns $end\n$var wire 1 ! D0 $end\n$var wire 1 \" D1 $end\n$enddefinitions $end\n#0\n1!\n1\"\n"
    vcd = vcd_decode.parse_vcd(text)
    assert vcd.channel("SCL") == "D0"
    assert vcd.channel("SDA") == "D1"


@NEED_SIGROK
def test_sigrok_i2c(tmp_path):
    lines = vcd_decode.sigrok_decode(i2c_capture(tmp_path), "i2c")
    assert vcd_decode.i2c_bytes(lines) == [("AW", 0x68), ("DW", 0x75)]


@NEED_SIGROK
def test_sigrok_spi(tmp_path):
    lines = vcd_decode.sigrok_decode(spi_capture(tmp_path), "spi")
    assert vcd_decode.spi_bytes(lines) == [0x2A, 0x00, 0xEF]
