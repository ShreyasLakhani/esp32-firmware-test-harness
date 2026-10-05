# Test plan

Mine sensor node on a simulated ESP32 (Wokwi). 24 test cases.
Sim tests run the real firmware.bin through wokwi-client. Host tests run lib/core on the PC.
Each test has a `test_id` marker so the JUnit XML shows the ID.

Setup for all sim tests: boot from reset, wait for `READY`. Pot starts at about 2048 (value 512 in diagram.json). Threshold 3000.

## UART (tests/sim/test_uart.py)

| ID | What | Pass if |
|---|---|---|
| UART-01 | Frame format | 3 frames match `$D,seq,ms,pot,ax,ay,az,state*CS` |
| UART-02 | Checksum | every frame in 3 s has a good XOR checksum, at least 5 frames |
| UART-03 | Sequence number | 6 frames in a row count up by 1 |
| UART-04 | PING | reply `PONG` |
| UART-05 | Set threshold | `SET THR 2500` gives `OK THR=2500`, `GET THR` reads it back |
| UART-06 | Range error | `SET THR 5000` and `SET STUCK 70000` give `ERR RANGE`, threshold not changed |
| UART-07 | Overflow | line over 32 chars gives `ERR OVERFLOW`, next `PING` still works |
| UART-08 | Unknown and bad args | `FOO` gives `ERR UNKNOWN`, `SET THR abc` and `PING 1` give `ERR ARG` |

## I2C (tests/sim/test_i2c.py)

| ID | What | Pass if |
|---|---|---|
| I2C-01 | Sensor found at boot | boot log has `I2C OK addr=0x68 whoami=0x68` |
| I2C-02 | Default accel | ax, ay near 0 and az 950 to 1050 mg |
| I2C-03 | Accel follows sensor | set accelX 0.5 g and accelZ -1 g, frame shows about 500 and -1000 mg. Logic analyzer shows reads from 0x68 |
| I2C-04 | No sensor | diagrams/no-sensor: boot log has `I2C FAIL`, frames have state F and accel 0 |

## SPI display (tests/sim/test_spi.py)

| ID | What | Pass if |
|---|---|---|
| SPI-01 | Normal screen | green background. Matches reference/spi-01.png if it exists |
| SPI-02 | Alarm screen | pot 0.9, red background. Matches reference/spi-02.png if it exists |
| SPI-03 | Fault screen and bus | pot 1.0, yellow background. VCD shows CS going low and SCK running |

## Alarm (tests/sim/test_alarm.py)

| ID | What | Pass if |
|---|---|---|
| ALM-01 | Alarm above threshold | pot 0.9 gives `EVT ALARM`, LED on, state A |
| ALM-02 | Latch | pot back to 0.5, LED stays on, state stays A |
| ALM-03 | Ack after drop | button press gives `EVT ACK CLEARED`, LED off, state N |
| ALM-04 | Ack while high | button press gives `EVT ACK DENIED`, LED stays on |
| ALM-05 | Threshold from UART | `SET THR 1500` with pot 0.5 raises the alarm |

## Faults and timing (tests/sim/test_fault_timing.py)

| ID | What | Pass if |
|---|---|---|
| FLT-01 | Stuck sensor | `SET STUCK 2000`, pot not moving gives `EVT FAULT STUCK` and state F. Moving the pot clears it. Off by default |
| FLT-02 | Out of range | pot at 1.0 gives `EVT FAULT RANGE` and state F, no alarm. Clears when pot is back in range |
| TIM-01 | Frame period | 10 gaps between frames are 480 to 520 ms, average 495 to 505 ms |

## Host (tests/host)

| ID | What | Pass if |
|---|---|---|
| HOST-01 | Frame parser with Hypothesis | C encode matches Python, round trip works, C and Python parsers agree on random input, a one char change is rejected, random bytes do not crash it |

tests/host also has plain unit tests for the command parser, alarm and fault code, and for the VCD helper. They have no test ID.

## Reference screenshots

SPI-01 and SPI-02 save screenshots to artifacts/. To set the references, take spi-01.png and spi-02.png from the CI artifact of a good run and put them in tests/sim/reference/.

## Limits

- Only runs in the simulator. No real hardware timing or ADC noise.
- Stuck check is off by default because the simulated pot does not move by itself.
- Accel range is fixed at 2 g.
- Screen checks use the corner color plus an optional reference image, not OCR.
- The button is read in the main loop. A full screen redraw blocks the loop for a few tens of ms, so a very short press during a redraw can be missed. ALM tests wait for the screen to finish before pressing. An interrupt would fix this.
