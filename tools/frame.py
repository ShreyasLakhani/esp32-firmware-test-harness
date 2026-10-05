"""Python side of the UART frame. Same rules as lib/core/frame.c.

$D,<seq>,<ms>,<pot>,<ax>,<ay>,<az>,<state>*<CS>
"""
import re
from dataclasses import dataclass

FRAME_RE = re.compile(
    r"\$(D,(0|[1-9][0-9]*),(0|[1-9][0-9]*),(0|[1-9][0-9]*),"
    r"(0|-?[1-9][0-9]*),(0|-?[1-9][0-9]*),(0|-?[1-9][0-9]*),([NAF]))\*([0-9A-F]{2})"
)
MAX_LEN = 80


class FrameError(ValueError):
    pass


@dataclass(frozen=True)
class Frame:
    seq: int
    ms: int
    pot: int
    ax: int
    ay: int
    az: int
    state: str


def checksum(body: str) -> int:
    cs = 0
    for ch in body.encode("latin-1"):
        cs ^= ch
    return cs


def encode(f: Frame) -> str:
    body = f"D,{f.seq},{f.ms},{f.pot},{f.ax},{f.ay},{f.az},{f.state}"
    return f"${body}*{checksum(body):02X}"


def parse(line: str) -> Frame:
    if len(line) > MAX_LEN:
        raise FrameError("too long")
    m = FRAME_RE.fullmatch(line)
    if not m:
        raise FrameError("bad format")
    seq, ms, pot, ax, ay, az = (int(m.group(i)) for i in range(2, 8))
    if seq > 0xFFFFFFFF or ms > 0xFFFFFFFF or pot > 4095:
        raise FrameError("out of range")
    for v in (ax, ay, az):
        if v < -32768 or v > 32767:
            raise FrameError("out of range")
    if checksum(m.group(1)) != int(m.group(9), 16):
        raise FrameError("bad checksum")
    return Frame(seq, ms, pot, ax, ay, az, m.group(8))


def is_frame(line: str) -> bool:
    return line.startswith("$D,")
