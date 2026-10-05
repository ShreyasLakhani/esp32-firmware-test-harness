// command parser, alarm latch and sensor fault checks
// plain C so the host tests can load it too
#ifndef LOGIC_H
#define LOGIC_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// ---- command line input ----
#define CMD_MAX_LEN 32

typedef struct {
    char buf[CMD_MAX_LEN + 1];
    size_t len;
    bool overflow;
} line_buf_t;

void line_reset(line_buf_t *lb);
// feed one char. returns true when a full line is ready in lb->buf.
// check lb->overflow before using the line. call line_reset after.
bool line_feed(line_buf_t *lb, char c);

// ---- commands ----
#define THR_DEFAULT 3000
#define THR_MAX 4095
#define STUCK_MS_MAX 60000

typedef struct {
    uint16_t thr;
    uint32_t stuck_ms;  // 0 = stuck check off
} settings_t;

typedef enum {
    CMD_OK = 0,
    CMD_ERR_RANGE,
    CMD_ERR_ARG,
    CMD_ERR_UNKNOWN,
    CMD_ERR_OVERFLOW,
} cmd_status_t;

void settings_default(settings_t *s);
// runs one command line. writes the reply line (no newline) into reply
cmd_status_t cmd_exec(const char *line, settings_t *s, char *reply, size_t cap);
const char *cmd_status_str(cmd_status_t st);

// ---- alarm ----
typedef struct {
    bool latched;
} alarm_t;

typedef enum {
    ACK_IDLE = 0,   // nothing to ack
    ACK_CLEARED,    // alarm cleared
    ACK_DENIED,     // value still above threshold, stays latched
} ack_result_t;

// returns true when the alarm just latched
bool alarm_update(alarm_t *a, uint16_t value, uint16_t thr);
ack_result_t alarm_ack(alarm_t *a, uint16_t value, uint16_t thr);

// ---- sensor faults ----
#define ADC_RANGE_MIN 10
#define ADC_RANGE_MAX 4085
#define STUCK_DELTA 8

typedef struct {
    bool started;
    uint16_t ref;
    uint32_t ref_ms;
    bool stuck;
    bool range;
} fault_t;

void fault_reset(fault_t *f);
void fault_update(fault_t *f, uint16_t value, uint32_t now_ms, uint32_t stuck_ms);

// N, A or F. fault wins over alarm
char state_char(const fault_t *f, const alarm_t *a, bool sensor_ok);

#ifdef __cplusplus
}
#endif

#endif
