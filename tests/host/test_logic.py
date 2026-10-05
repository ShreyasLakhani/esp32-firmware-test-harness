"""Host checks for the command parser, alarm latch and fault logic.
Same code the firmware runs. Quick to run, no simulator."""
import ctypes

import pytest
from hypothesis import given
from hypothesis import strategies as st

from core_lib import AlarmT, FaultT, SettingsT

OK, ERR_RANGE, ERR_ARG, ERR_UNKNOWN, ERR_OVERFLOW = range(5)
ACK_IDLE, ACK_CLEARED, ACK_DENIED = range(3)


def fresh(core):
    s = SettingsT()
    core.lib.settings_default(ctypes.byref(s))
    return s


def test_cmd_basic(core):
    s = fresh(core)
    assert core.cmd(b"PING", s) == (OK, "PONG")
    assert core.cmd(b"GET THR", s) == (OK, "OK THR=3000")
    assert core.cmd(b"SET THR 2500", s) == (OK, "OK THR=2500")
    assert s.thr == 2500
    assert core.cmd(b"SET THR 4096", s) == (ERR_RANGE, "ERR RANGE")
    assert core.cmd(b"SET THR 99999999999999", s) == (ERR_RANGE, "ERR RANGE")
    assert s.thr == 2500
    assert core.cmd(b"SET THR abc", s) == (ERR_ARG, "ERR ARG")
    assert core.cmd(b"SET THR", s) == (ERR_ARG, "ERR ARG")
    assert core.cmd(b"FOO", s) == (ERR_UNKNOWN, "ERR UNKNOWN")
    assert core.cmd(b"SET STUCK 2000", s) == (OK, "OK STUCK=2000")
    assert core.cmd(b"A" * 33, s) == (ERR_OVERFLOW, "ERR OVERFLOW")


@given(st.integers(0, 4095))
def test_cmd_thr_in_range(core, v):
    s = fresh(core)
    assert core.cmd(f"SET THR {v}".encode(), s) == (OK, f"OK THR={v}")


@given(st.integers(4096, 10**12))
def test_cmd_thr_out_of_range(core, v):
    s = fresh(core)
    assert core.cmd(f"SET THR {v}".encode(), s)[0] == ERR_RANGE
    assert s.thr == 3000


@given(st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=32))
def test_cmd_never_crashes(core, line):
    s = fresh(core)
    st_, reply = core.cmd(line.encode(), s)
    assert 0 <= st_ <= 4
    assert reply


def test_alarm_latch(core):
    a = AlarmT()
    assert core.lib.alarm_update(ctypes.byref(a), 3100, 3000) is True
    assert core.lib.alarm_update(ctypes.byref(a), 1000, 3000) is False
    assert a.latched
    assert core.lib.alarm_ack(ctypes.byref(a), 3100, 3000) == ACK_DENIED
    assert core.lib.alarm_ack(ctypes.byref(a), 1000, 3000) == ACK_CLEARED
    assert not a.latched
    assert core.lib.alarm_ack(ctypes.byref(a), 1000, 3000) == ACK_IDLE


def test_fault_range(core):
    f = FaultT()
    core.lib.fault_reset(ctypes.byref(f))
    core.lib.fault_update(ctypes.byref(f), 4095, 0, 0)
    assert f.range
    core.lib.fault_update(ctypes.byref(f), 2000, 20, 0)
    assert not f.range
    core.lib.fault_update(ctypes.byref(f), 0, 40, 0)
    assert f.range


@pytest.mark.parametrize("stuck_ms", [500, 2000])
def test_fault_stuck(core, stuck_ms):
    f = FaultT()
    core.lib.fault_reset(ctypes.byref(f))
    t = 0
    while t < stuck_ms:
        core.lib.fault_update(ctypes.byref(f), 2000 + (t // 20) % 3, t, stuck_ms)  # small noise only
        assert not f.stuck
        t += 20
    core.lib.fault_update(ctypes.byref(f), 2000, t, stuck_ms)
    assert f.stuck
    core.lib.fault_update(ctypes.byref(f), 2100, t + 20, stuck_ms)
    assert not f.stuck


def test_fault_stuck_off_by_default(core):
    f = FaultT()
    core.lib.fault_reset(ctypes.byref(f))
    for t in range(0, 100000, 1000):
        core.lib.fault_update(ctypes.byref(f), 2000, t, 0)
    assert not f.stuck
