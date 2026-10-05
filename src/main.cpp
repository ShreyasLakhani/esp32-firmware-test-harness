// mine sensor node firmware
// ESP32 + MPU6050 (I2C) + ILI9341 (SPI) + pot + button + alarm LED
#include <Arduino.h>
#include <SPI.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>

#include "frame.h"
#include "logic.h"

#define FW_VERSION "0.1.0"

// pins, same as diagram.json
#define PIN_SDA 21
#define PIN_SCL 22
#define PIN_POT 34
#define PIN_BTN 13
#define PIN_LED 25
#define PIN_TFT_CS 15
#define PIN_TFT_DC 2
#define PIN_TFT_RST 4

#define MPU_ADDR 0x68
#define MPU_REG_PWR 0x6B
#define MPU_REG_ACCEL 0x3B
#define MPU_REG_WHOAMI 0x75

#define FRAME_PERIOD_MS 500
#define SAMPLE_PERIOD_MS 20
#define DEBOUNCE_MS 30
#define SCREEN_REFRESH_MS 1000

// colors for each state, tests check these
#define COLOR_NORMAL 0x03E0  // dark green
#define COLOR_ALARM 0xF800   // red
#define COLOR_FAULT 0xFFE0   // yellow

Adafruit_ILI9341 tft(PIN_TFT_CS, PIN_TFT_DC, PIN_TFT_RST);

static settings_t settings;
static alarm_t alarm_state;
static fault_t fault_state;
static line_buf_t line_buf;

static bool sensor_ok = false;
static uint32_t seq = 0;
static uint16_t pot = 0;
static int16_t acc_mg[3] = {0, 0, 0};
static char state = 'N';
static char shown_state = 0;

static uint32_t next_frame_ms = 0;
static uint32_t next_sample_ms = 0;
static uint32_t next_screen_ms = 0;

static bool btn_stable = true;  // true = released (pull up)
static bool btn_last = true;
static uint32_t btn_changed_ms = 0;

static bool fault_stuck_reported = false;
static bool fault_range_reported = false;

// ---- I2C ----

static bool mpu_write(uint8_t reg, uint8_t val) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(reg);
    Wire.write(val);
    return Wire.endTransmission() == 0;
}

static bool mpu_read(uint8_t reg, uint8_t *buf, size_t n) {
    Wire.beginTransmission(MPU_ADDR);
    Wire.write(reg);
    if (Wire.endTransmission(false) != 0) return false;
    if (Wire.requestFrom((uint8_t)MPU_ADDR, (uint8_t)n) != n) return false;
    for (size_t i = 0; i < n; i++) buf[i] = Wire.read();
    return true;
}

static bool mpu_init() {
    uint8_t who = 0;
    if (!mpu_read(MPU_REG_WHOAMI, &who, 1)) {
        Serial.printf("I2C FAIL addr=0x%02X no ack\n", MPU_ADDR);
        return false;
    }
    if (who != 0x68) {
        Serial.printf("I2C FAIL addr=0x%02X whoami=0x%02X\n", MPU_ADDR, who);
        return false;
    }
    mpu_write(MPU_REG_PWR, 0x00);  // wake up
    Serial.printf("I2C OK addr=0x%02X whoami=0x%02X\n", MPU_ADDR, who);
    return true;
}

static void mpu_read_accel() {
    uint8_t b[6];
    if (!sensor_ok || !mpu_read(MPU_REG_ACCEL, b, 6)) {
        acc_mg[0] = acc_mg[1] = acc_mg[2] = 0;
        return;
    }
    for (int i = 0; i < 3; i++) {
        int16_t raw = (int16_t)((b[2 * i] << 8) | b[2 * i + 1]);
        acc_mg[i] = (int16_t)((int32_t)raw * 1000 / 16384);  // +-2g range
    }
}

// ---- display ----

static uint16_t state_color(char s) {
    if (s == 'A') return COLOR_ALARM;
    if (s == 'F') return COLOR_FAULT;
    return COLOR_NORMAL;
}

static const char *state_name(char s) {
    if (s == 'A') return "ALARM";
    if (s == 'F') return "FAULT";
    return "NORMAL";
}

static void draw_value() {
    uint16_t bg = state_color(shown_state);
    uint16_t fg = (shown_state == 'F') ? ILI9341_BLACK : ILI9341_WHITE;
    tft.fillRect(10, 120, 220, 80, bg);
    tft.setTextColor(fg, bg);
    tft.setTextSize(2);
    tft.setCursor(10, 120);
    tft.printf("POT %4u", pot);
    tft.setCursor(10, 145);
    tft.printf("THR %4u", settings.thr);
    tft.setCursor(10, 170);
    if (shown_state == 'F') {
        if (!sensor_ok) tft.print("NO SENSOR");
        else if (fault_state.range) tft.print("OUT OF RANGE");
        else if (fault_state.stuck) tft.print("STUCK");
    }
}

static void draw_screen() {
    shown_state = state;
    uint16_t bg = state_color(state);
    uint16_t fg = (state == 'F') ? ILI9341_BLACK : ILI9341_WHITE;
    tft.fillScreen(bg);
    tft.setTextColor(fg, bg);
    tft.setTextSize(4);
    tft.setCursor(10, 40);
    tft.print(state_name(state));
    draw_value();
    Serial.printf("EVT SCREEN %s\n", state_name(state));
}

// ---- inputs ----

static void handle_line() {
    char reply[48];
    if (line_buf.overflow) {
        Serial.println(cmd_status_str(CMD_ERR_OVERFLOW));
    } else {
        cmd_exec(line_buf.buf, &settings, reply, sizeof(reply));
        Serial.println(reply);
    }
    line_reset(&line_buf);
}

static void poll_serial() {
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (line_feed(&line_buf, c)) handle_line();
    }
}

static void on_button_press() {
    ack_result_t r = alarm_ack(&alarm_state, pot, settings.thr);
    if (r == ACK_CLEARED) Serial.println("EVT ACK CLEARED");
    else if (r == ACK_DENIED) Serial.println("EVT ACK DENIED");
    else Serial.println("EVT ACK IDLE");
}

static void poll_button(uint32_t now) {
    bool level = digitalRead(PIN_BTN) == HIGH;
    if (level != btn_last) {
        btn_last = level;
        btn_changed_ms = now;
    }
    if (level != btn_stable && (now - btn_changed_ms) >= DEBOUNCE_MS) {
        btn_stable = level;
        if (!btn_stable) on_button_press();  // pressed = low
    }
}

static void sample(uint32_t now) {
    pot = (uint16_t)analogRead(PIN_POT);

    fault_update(&fault_state, pot, now, settings.stuck_ms);
    if (fault_state.range && !fault_range_reported) {
        Serial.printf("EVT FAULT RANGE value=%u\n", pot);
    }
    if (fault_state.stuck && !fault_stuck_reported) {
        Serial.printf("EVT FAULT STUCK value=%u\n", pot);
    }
    if ((fault_range_reported && !fault_state.range) || (fault_stuck_reported && !fault_state.stuck)) {
        if (!fault_state.range && !fault_state.stuck) Serial.println("EVT FAULT CLEAR");
    }
    fault_range_reported = fault_state.range;
    fault_stuck_reported = fault_state.stuck;

    // no alarm on a bad reading
    if (!fault_state.range && alarm_update(&alarm_state, pot, settings.thr)) {
        Serial.printf("EVT ALARM value=%u thr=%u\n", pot, settings.thr);
    }

    state = state_char(&fault_state, &alarm_state, sensor_ok);
    digitalWrite(PIN_LED, alarm_state.latched ? HIGH : LOW);
}

static void send_frame(uint32_t now) {
    frame_t f;
    char out[FRAME_MAX_LEN + 1];
    mpu_read_accel();
    f.seq = seq++;
    f.ms = now;
    f.pot = pot;
    f.ax = acc_mg[0];
    f.ay = acc_mg[1];
    f.az = acc_mg[2];
    f.state = state;
    if (frame_encode(&f, out, sizeof(out)) > 0) Serial.println(out);
}

// ---- main ----

void setup() {
    Serial.begin(115200);
    pinMode(PIN_LED, OUTPUT);
    digitalWrite(PIN_LED, LOW);
    pinMode(PIN_BTN, INPUT_PULLUP);
    analogReadResolution(12);

    settings_default(&settings);
    fault_reset(&fault_state);
    alarm_state.latched = false;
    line_reset(&line_buf);

    Serial.printf("BOOT mine-sensor-node fw=%s\n", FW_VERSION);

    Wire.begin(PIN_SDA, PIN_SCL);
    Wire.setClock(100000);
    sensor_ok = mpu_init();

    tft.begin();
    tft.setRotation(0);
    Serial.println("SPI OK display=ili9341");

    uint32_t now = millis();
    sample(now);
    draw_screen();

    Serial.println("READY");
    now = millis();
    next_sample_ms = now + SAMPLE_PERIOD_MS;
    next_screen_ms = now + SCREEN_REFRESH_MS;
    next_frame_ms = now;
}

void loop() {
    uint32_t now = millis();

    poll_serial();
    poll_button(now);

    if ((int32_t)(now - next_sample_ms) >= 0) {
        next_sample_ms += SAMPLE_PERIOD_MS;
        sample(now);
        if (state != shown_state) draw_screen();
    }

    if ((int32_t)(now - next_screen_ms) >= 0) {
        next_screen_ms += SCREEN_REFRESH_MS;
        draw_value();
    }

    if ((int32_t)(now - next_frame_ms) >= 0) {
        send_frame(now);
        next_frame_ms += FRAME_PERIOD_MS;
    }
}
