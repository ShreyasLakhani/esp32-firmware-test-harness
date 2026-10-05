"""UART-01 to UART-08: data frames and the command parser."""
import pytest

from tools import frame as pyframe


@pytest.mark.test_id("UART-01")
def test_uart01_frame_format(node):
    for f in node.frames(3):
        assert f.state in "NAF"
        assert 0 <= f.pot <= 4095


@pytest.mark.test_id("UART-02")
def test_uart02_checksum(node):
    bad = []
    node.mark()
    node.advance(3.0)
    lines = [l for l in node.lines[node.cursor:] if pyframe.is_frame(l)]
    for line in lines:
        try:
            pyframe.parse(line)
        except pyframe.FrameError as e:
            bad.append((line, str(e)))
    assert len(lines) >= 5
    assert not bad


@pytest.mark.test_id("UART-03")
def test_uart03_sequence(node):
    seqs = [f.seq for f in node.frames(6)]
    assert seqs == list(range(seqs[0], seqs[0] + 6))


@pytest.mark.test_id("UART-04")
def test_uart04_ping(node):
    assert node.command("PING") == "PONG"


@pytest.mark.test_id("UART-05")
def test_uart05_set_threshold(node):
    assert node.command("SET THR 2500") == "OK THR=2500"
    assert node.command("GET THR") == "OK THR=2500"


@pytest.mark.test_id("UART-06")
def test_uart06_range_error(node):
    assert node.command("SET THR 5000") == "ERR RANGE"
    assert node.command("SET STUCK 70000") == "ERR RANGE"
    assert node.command("GET THR") == "OK THR=3000"


@pytest.mark.test_id("UART-07")
def test_uart07_overflow(node):
    assert node.command("SET THR " + "1" * 40) == "ERR OVERFLOW"
    # parser still works after the long line
    assert node.command("PING") == "PONG"


@pytest.mark.test_id("UART-08")
def test_uart08_unknown_and_bad_args(node):
    assert node.command("FOO") == "ERR UNKNOWN"
    assert node.command("SET THR abc") == "ERR ARG"
    assert node.command("PING 1") == "ERR ARG"
