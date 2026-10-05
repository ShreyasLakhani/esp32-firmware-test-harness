# esp32-firmware-test-harness
Simulated ESP32 mine sensor node in Wokwi with automated UART, I2C and SPI firmware tests in Pytest and GitHub Actions.

[![ci](https://github.com/ShreyasLakhani/esp32-firmware-test-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/ShreyasLakhani/esp32-firmware-test-harness/actions/workflows/ci.yml)

## What it does

The node reads a pot and an MPU6050 accelerometer.
It sends a data frame on UART every 500 ms.
It raises a latching alarm when the pot goes over the threshold. The button clears it once the level drops.
It shows the state on an ILI9341 screen. Green is normal, red is alarm, yellow is fault.

Frame format: `$D,seq,ms,pot,ax,ay,az,state*CS`. State is N, A or F. CS is an XOR checksum.

UART commands: `PING`, `SET THR <n>`, `GET THR`, `SET STUCK <ms>`.

## Wiring

All parts are in `diagram.json`. Same pins as `src/main.cpp`.

| Part | Pin | ESP32 |
|---|---|---|
| MPU6050 | SDA | GPIO 21 |
| MPU6050 | SCL | GPIO 22 |
| Pot | SIG | GPIO 34 |
| Button | 1.l | GPIO 13 (other side to GND) |
| Alarm LED | A | GPIO 25 through 220 ohm |
| ILI9341 | SCK | GPIO 18 |
| ILI9341 | MOSI | GPIO 23 |
| ILI9341 | MISO | GPIO 19 |
| ILI9341 | CS | GPIO 15 |
| ILI9341 | D/C | GPIO 2 |
| ILI9341 | RST | GPIO 4 |

Power for the sensor, pot and screen is 3V3 and GND.

A logic analyzer watches SCL, SDA, SCK, MOSI, CS and TX. The tests read its VCD output.

`diagrams/no-sensor/diagram.json` is the same board without the MPU6050. I2C-04 uses it.

## Tests

Test plan with all 24 test IDs: [docs/test-plan.md](docs/test-plan.md)

- `tests/sim` runs the real firmware in Wokwi through wokwi-client.
- `tests/host` runs the frame parser and logic code on the PC. Hypothesis is used for the parser.

Each test has a `test_id` marker. The report job in CI turns the JUnit XML into a table of test IDs.

## Run it

```
pip install -r requirements.txt
pio run -e esp32
pytest tests/host
```

Sim tests need a Wokwi CI token:

```
set WOKWI_CLI_TOKEN=<your token>
pytest tests/sim
```

On Linux or macOS use `export` instead of `set`.

## CI

`.github/workflows/ci.yml` has four jobs.

- build: builds firmware.bin and firmware.elf
- host-tests: runs tests/host
- sim-tests: runs tests/sim against the built firmware
- report: writes the test ID table to the job summary

Screenshots and VCD files from the sim tests are saved in the sim-captures artifact.

## Limits

- Only runs in the simulator. No real hardware timing or ADC noise.
- Stuck check is off by default because the simulated pot does not move by itself.
- Accel range is fixed at 2 g.
- Screen checks use the corner color plus a reference image. No OCR.
- The button is read in the main loop. A full screen redraw blocks the loop for a few tens of ms, so a very short press can be missed. The alarm tests wait for the redraw first. An interrupt would fix this.
- Sim tests depend on the Wokwi service. The harness retries when the connection drops, but a long outage still fails the run.
