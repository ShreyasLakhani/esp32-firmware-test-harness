"""ALM-01 to ALM-05: latching alarm and button acknowledge.
Default threshold is 3000. pot 0.5 is about 2048, 0.9 is about 3686."""
import pytest

LOW = 0.5
HIGH = 0.9


def raise_alarm(node):
    node.pot(LOW)
    node.advance(0.2)
    node.mark()
    node.pot(HIGH)
    return node.wait_line(r"^EVT ALARM value=(\d+) thr=(\d+)$", timeout=1)


@pytest.mark.test_id("ALM-01")
def test_alm01_alarm_above_threshold(node):
    m = raise_alarm(node)
    assert int(m.group(1)) > int(m.group(2)) == 3000
    node.advance(0.1)
    assert node.led()
    assert node.frames(1)[0].state == "A"


@pytest.mark.test_id("ALM-02")
def test_alm02_alarm_stays_latched(node):
    raise_alarm(node)
    node.pot(LOW)
    node.advance(1.0)
    assert node.led()
    assert all(f.state == "A" for f in node.frames(2))


@pytest.mark.test_id("ALM-03")
def test_alm03_button_clears_after_drop(node):
    raise_alarm(node)
    node.pot(LOW)
    node.advance(0.2)
    node.mark()
    node.press()
    node.wait_line(r"^EVT ACK CLEARED$", timeout=1)
    assert not node.led()
    node.frames(1)
    assert node.frames(1)[0].state == "N"


@pytest.mark.test_id("ALM-04")
def test_alm04_button_denied_while_high(node):
    raise_alarm(node)
    node.mark()
    node.press()
    node.wait_line(r"^EVT ACK DENIED$", timeout=1)
    assert node.led()
    assert node.frames(1)[0].state == "A"


@pytest.mark.test_id("ALM-05")
def test_alm05_threshold_from_uart(node):
    node.pot(LOW)
    node.advance(0.3)
    node.mark()
    node.press()
    node.wait_line(r"^EVT ACK IDLE$", timeout=1)  # nothing to ack yet
    assert node.command("SET THR 1500") == "OK THR=1500"
    node.wait_line(r"^EVT ALARM value=\d+ thr=1500$", timeout=1)
    node.advance(0.1)
    assert node.led()
