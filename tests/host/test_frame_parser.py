"""HOST-01: frame parser checks with Hypothesis. Runs the real C code from lib/core."""
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tools import frame as pyframe
from core_lib import FrameT

pytestmark = pytest.mark.test_id("HOST-01")

frames = st.builds(
    pyframe.Frame,
    seq=st.integers(0, 0xFFFFFFFF),
    ms=st.integers(0, 0xFFFFFFFF),
    pot=st.integers(0, 4095),
    ax=st.integers(-32768, 32767),
    ay=st.integers(-32768, 32767),
    az=st.integers(-32768, 32767),
    state=st.sampled_from("NAF"),
)

# ascii text that looks a bit like a frame, so we hit the deeper code paths
frame_chars = st.sampled_from(list("$D,*-0123456789ABCDEFNAFxyz \t"))
frame_like = st.lists(frame_chars, max_size=90).map("".join)


def to_c(f):
    return FrameT(f.seq, f.ms, f.pot, f.ax, f.ay, f.az, f.state.encode())


def from_c(c):
    return pyframe.Frame(c.seq, c.ms, c.pot, c.ax, c.ay, c.az, c.state.decode())


@given(frames)
def test_host01_c_encode_matches_python(core, f):
    assert core.encode(to_c(f)) == pyframe.encode(f)


@given(frames)
def test_host01_roundtrip(core, f):
    line = pyframe.encode(f)
    rc, out = core.parse(line.encode())
    assert rc == 0
    assert from_c(out) == f


@settings(max_examples=500)
@given(st.one_of(frame_like, st.text(alphabet=st.characters(min_codepoint=1, max_codepoint=127), max_size=100)))
def test_host01_c_and_python_agree(core, text):
    rc, out = core.parse(text.encode())
    try:
        py = pyframe.parse(text)
    except pyframe.FrameError:
        py = None
    if rc == 0:
        assert py == from_c(out)
        # accepted input must be the canonical form
        assert pyframe.encode(py) == text
    else:
        assert py is None


@given(frames, st.data())
def test_host01_single_char_change_is_rejected(core, f, data):
    line = pyframe.encode(f)
    i = data.draw(st.integers(1, len(line) - 1))
    new = data.draw(st.sampled_from("0123456789ABCDEF,-*NAFD").filter(lambda c: c != line[i]))
    bad = line[:i] + new + line[i + 1:]
    rc, _ = core.parse(bad.encode())
    assert rc != 0


@given(st.binary(max_size=200))
def test_host01_parser_survives_random_bytes(core, raw):
    raw = raw.replace(b"\x00", b"")
    rc, _ = core.parse(raw)
    assert rc in (0, -1, -2, -3)


def test_host01_known_frame(core):
    line = "$D,0,0,2047,0,0,1000,N*" + format(pyframe.checksum("D,0,0,2047,0,0,1000,N"), "02X")
    rc, out = core.parse(line.encode())
    assert rc == 0
    assert out.pot == 2047 and out.az == 1000


@pytest.mark.parametrize(
    "line",
    [
        "",
        "$D,1,2,3,4,5,6,N",  # no checksum
        "$D,01,2,3,4,5,6,N*00",  # leading zero
        "$D,1,2,4096,4,5,6,N*00",  # pot too big
        "$D,1,2,3,-0,5,6,N*00",  # minus zero
        "$D,1,2,3,4,5,6,X*00",  # bad state
        "$D,1,2,3,4,5,6,7,N*00",  # extra field
    ],
)
def test_host01_bad_frames(core, line):
    rc, _ = core.parse(line.encode())
    assert rc != 0
