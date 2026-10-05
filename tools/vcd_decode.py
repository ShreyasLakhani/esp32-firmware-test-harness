"""Decode the logic analyzer VCD from Wokwi into I2C / SPI bytes.

Uses sigrok-cli for the protocol decoding. Has a small VCD reader too,
so tests can count edges without sigrok.

usage:
  python tools/vcd_decode.py capture.vcd i2c
  python tools/vcd_decode.py capture.vcd spi
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# logic analyzer wiring from diagram.json
DEFAULT_CHANNELS = {"SCL": 0, "SDA": 1, "SCK": 2, "MOSI": 3, "CS": 4, "TX": 5}

UNITS_NS = {"s": 1e9, "ms": 1e6, "us": 1e3, "ns": 1.0, "ps": 1e-3, "fs": 1e-6}


class Vcd:
    def __init__(self, timescale_ns, names, changes):
        self.timescale_ns = timescale_ns
        self.names = names  # list of var names in file order
        self.changes = changes  # name -> [(time_ns, value)]

    def channel(self, label):
        """Find a channel by label (SCL, SDA...) or by D0..D7 index."""
        if label in self.changes:
            return label
        idx = DEFAULT_CHANNELS.get(label)
        if idx is not None:
            for cand in (f"D{idx}", f"d{idx}"):
                if cand in self.changes:
                    return cand
            if idx < len(self.names):
                return self.names[idx]
        raise KeyError(f"no channel {label} in {self.names}")

    def edges(self, label, kind="any"):
        ch = self.channel(label)
        out = 0
        prev = None
        for _, v in self.changes[ch]:
            if prev is not None and v != prev:
                if kind == "any" or (kind == "rise" and v == 1) or (kind == "fall" and v == 0):
                    out += 1
            prev = v
        return out


def parse_vcd(text):
    ts_ns = 1.0
    m = re.search(r"\$timescale\s+(\d+)\s*(s|ms|us|ns|ps|fs)\s+\$end", text)
    if m:
        ts_ns = int(m.group(1)) * UNITS_NS[m.group(2)]
    ids = {}
    names = []
    for vm in re.finditer(r"\$var\s+\S+\s+\d+\s+(\S+)\s+(\S+)", text):
        ids[vm.group(1)] = vm.group(2)
        names.append(vm.group(2))
    changes = {n: [] for n in names}
    body = text.split("$enddefinitions", 1)[-1]
    t = 0
    for tok in body.split():
        if tok.startswith("#"):
            t = int(tok[1:]) * ts_ns
        elif tok[0] in "01xXzZ" and tok[1:] in ids:
            v = 1 if tok[0] == "1" else 0
            changes[ids[tok[1:]]].append((t, v))
    return Vcd(ts_ns, names, changes)


def _downsample(vcd, target_ns):
    # sigrok makes one sample per timescale unit, so big captures get huge.
    # keep about target_ns per sample
    return max(1, int(target_ns / vcd.timescale_ns))


def sigrok_decode(vcd_path, proto, sample_ns=50):
    if shutil.which("sigrok-cli") is None:
        raise RuntimeError("sigrok-cli not found. apt install sigrok-cli")
    vcd = parse_vcd(Path(vcd_path).read_text())
    ds = _downsample(vcd, sample_ns)
    if proto == "i2c":
        pd = f"i2c:scl={vcd.channel('SCL')}:sda={vcd.channel('SDA')}"
        ann = "i2c=address-read:address-write:data-read:data-write"
    elif proto == "spi":
        pd = f"spi:clk={vcd.channel('SCK')}:mosi={vcd.channel('MOSI')}:cs={vcd.channel('CS')}"
        ann = "spi=mosi-data"
    else:
        raise ValueError(proto)
    cmd = ["sigrok-cli", "-I", f"vcd:downsample={ds}", "-i", str(vcd_path), "-P", pd, "-A", ann]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return [line.strip() for line in res.stdout.splitlines() if line.strip()]


def i2c_bytes(lines):
    """['Address write: 68', 'Data write: 75', ...] -> [('AW', 0x68), ('DW', 0x75), ...]"""
    tags = {"Address write": "AW", "Address read": "AR", "Data write": "DW", "Data read": "DR"}
    out = []
    for line in lines:
        m = re.search(r"(Address write|Address read|Data write|Data read): ([0-9A-Fa-f]{2})", line)
        if m:
            out.append((tags[m.group(1)], int(m.group(2), 16)))
    return out


def spi_bytes(lines):
    out = []
    for line in lines:
        m = re.search(r"\b([0-9A-Fa-f]{2})\s*$", line)
        if m:
            out.append(int(m.group(1), 16))
    return out


def save_text(text):
    f = tempfile.NamedTemporaryFile("w", suffix=".vcd", delete=False)
    f.write(text)
    f.close()
    return f.name


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("vcd")
    ap.add_argument("proto", choices=["i2c", "spi"])
    ap.add_argument("--limit", type=int, default=200, help="max lines to print")
    args = ap.parse_args(argv)
    lines = sigrok_decode(args.vcd, args.proto)
    for line in lines[: args.limit]:
        print(line)
    if len(lines) > args.limit:
        print(f"... {len(lines) - args.limit} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
