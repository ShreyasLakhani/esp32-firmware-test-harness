"""SPI-01 to SPI-03: ILI9341 status screens.

Checks the background color of each screen. If a reference png is in
tests/sim/reference, the screenshot is also compared to it.
"""
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

from tools import vcd_decode

REF = Path(__file__).parent / "reference"

# RGB565 colors from main.cpp, as 8 bit RGB
NORMAL = (0, 124, 0)
ALARM = (248, 0, 0)
FAULT = (248, 252, 0)


def corner_color(png):
    img = Image.open(png).convert("RGB")
    return img.getpixel((2, 2))


def close(c1, c2, tol=24):
    return all(abs(a - b) <= tol for a, b in zip(c1, c2))


def compare_to_ref(png, name, max_diff=8.0):
    ref = REF / name
    if not ref.exists():
        return None
    a = Image.open(png).convert("RGB")
    b = Image.open(ref).convert("RGB")
    assert a.size == b.size
    diff = ImageStat.Stat(ImageChops.difference(a, b)).mean
    assert max(diff) <= max_diff, f"screen differs from {name}: mean diff {diff}"
    return diff


def wait_screen(node, name):
    node.wait_line(rf"^EVT SCREEN {name}$", timeout=3)
    node.advance(0.3)  # let the draw finish


@pytest.mark.test_id("SPI-01")
def test_spi01_normal_screen(node, artifacts):
    node.pot(0.5)
    node.advance(0.5)
    png = node.screenshot(artifacts / "spi-01.png")
    assert close(corner_color(png), NORMAL), corner_color(png)
    compare_to_ref(png, "spi-01.png")


@pytest.mark.test_id("SPI-02")
def test_spi02_alarm_screen(node, artifacts):
    node.mark()
    node.pot(0.9)
    wait_screen(node, "ALARM")
    png = node.screenshot(artifacts / "spi-02.png")
    assert close(corner_color(png), ALARM), corner_color(png)
    compare_to_ref(png, "spi-02.png")


@pytest.mark.test_id("SPI-03")
def test_spi03_fault_screen_and_bus(node, artifacts):
    node.mark()
    node.pot(1.0)
    wait_screen(node, "FAULT")
    png = node.screenshot(artifacts / "spi-03.png")
    assert close(corner_color(png), FAULT), corner_color(png)

    vcd = node.vcd()
    path = artifacts / "spi-03.vcd"
    path.write_text(vcd["vcd"])
    parsed = vcd_decode.parse_vcd(vcd["vcd"])
    # display traffic: CS goes low and the clock runs
    assert parsed.edges("CS", "fall") > 0
    assert parsed.edges("SCK", "rise") > 1000
