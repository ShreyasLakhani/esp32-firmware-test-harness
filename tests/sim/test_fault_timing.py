"""FLT-01, FLT-02 and TIM-01."""
import pytest


@pytest.mark.test_id("FLT-01")
def test_flt01_stuck_sensor(node):
    node.pot(0.5)
    node.advance(0.2)
    assert node.command("SET STUCK 2000") == "OK STUCK=2000"
    node.mark()
    m = node.wait_line(r"^EVT FAULT STUCK value=\d+$", timeout=3)
    assert m
    node.frames(1)
    assert node.frames(1)[0].state == "F"
    # moving the pot clears it
    node.mark()
    node.pot(0.6)
    node.wait_line(r"^EVT FAULT CLEAR$", timeout=1)


@pytest.mark.test_id("FLT-01")
def test_flt01_no_stuck_when_off(node):
    node.pot(0.5)
    node.no_line(r"^EVT FAULT STUCK", seconds=3)


@pytest.mark.test_id("FLT-02")
def test_flt02_out_of_range(node):
    node.pot(0.5)
    node.advance(0.2)
    node.mark()
    node.pot(1.0)
    node.wait_line(r"^EVT FAULT RANGE value=\d+$", timeout=1)
    node.frames(1)
    assert node.frames(1)[0].state == "F"
    node.mark()
    node.pot(0.0)
    node.no_line(r"^EVT FAULT CLEAR", seconds=0.5)  # 0 is out of range too
    node.pot(0.5)
    node.wait_line(r"^EVT FAULT CLEAR$", timeout=1)


@pytest.mark.test_id("FLT-02")
def test_flt02_rail_does_not_raise_alarm(node):
    node.pot(0.5)
    node.advance(0.2)
    node.mark()
    node.pot(1.0)
    node.no_line(r"^EVT ALARM", seconds=1.0)
    assert not node.led()


@pytest.mark.test_id("TIM-01")
def test_tim01_frame_period(node):
    frames = node.frames(11)
    deltas = [b.ms - a.ms for a, b in zip(frames, frames[1:])]
    assert all(480 <= d <= 520 for d in deltas), deltas
    assert abs(sum(deltas) / len(deltas) - 500) <= 5, deltas
