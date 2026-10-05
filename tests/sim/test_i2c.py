"""I2C-01 to I2C-04: MPU6050 on the I2C bus."""
import pytest

from tools import vcd_decode


@pytest.mark.test_id("I2C-01")
def test_i2c01_sensor_found_at_boot(sim):
    sim.start()
    # boot lines come before READY, so search everything
    assert "I2C OK addr=0x68 whoami=0x68" in sim.lines


@pytest.mark.test_id("I2C-02")
def test_i2c02_default_accel(node):
    for f in node.frames(3):
        assert abs(f.ax) <= 20
        assert abs(f.ay) <= 20
        assert 950 <= f.az <= 1050  # 1 g at rest


@pytest.mark.test_id("I2C-03")
def test_i2c03_accel_follows_sensor(node, artifacts, tmp_path):
    node.client.set_control("imu", "accelX", 0.5)
    node.client.set_control("imu", "accelZ", -1.0)
    node.frames(1)  # skip one frame in flight
    f = node.frames(1)[0]
    assert 450 <= f.ax <= 550
    assert -1050 <= f.az <= -950

    # the I2C bytes on the logic analyzer should show reads from 0x68
    vcd = node.vcd()
    path = artifacts / "i2c-03.vcd"
    path.write_text(vcd["vcd"])
    parsed = vcd_decode.parse_vcd(vcd["vcd"])
    assert parsed.edges("SCL", "rise") > 0
    try:
        lines = vcd_decode.sigrok_decode(path, "i2c")
    except RuntimeError:
        pytest.skip("sigrok-cli not installed, edge check only")
    addrs = {b for kind, b in vcd_decode.i2c_bytes(lines) if kind in ("AW", "AR")}
    assert 0x68 in addrs


@pytest.mark.test_id("I2C-04")
def test_i2c04_no_sensor(sim_no_sensor):
    sim_no_sensor.start()
    assert any(l.startswith("I2C FAIL addr=0x68") for l in sim_no_sensor.lines)
    for f in sim_no_sensor.frames(2):
        assert f.state == "F"
        assert (f.ax, f.ay, f.az) == (0, 0, 0)
