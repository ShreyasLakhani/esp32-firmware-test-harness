#include "logic.h"

#include <stdio.h>
#include <string.h>

// ---- command line input ----

void line_reset(line_buf_t *lb) {
    lb->len = 0;
    lb->overflow = false;
    lb->buf[0] = '\0';
}

bool line_feed(line_buf_t *lb, char c) {
    if (c == '\r') return false;
    if (c == '\n') {
        lb->buf[lb->len] = '\0';
        return lb->len > 0 || lb->overflow;
    }
    if (lb->len >= CMD_MAX_LEN) {
        lb->overflow = true;  // drop the rest until newline
        return false;
    }
    lb->buf[lb->len++] = c;
    return false;
}

// ---- commands ----

void settings_default(settings_t *s) {
    s->thr = THR_DEFAULT;
    s->stuck_ms = 0;
}

const char *cmd_status_str(cmd_status_t st) {
    switch (st) {
        case CMD_OK: return "OK";
        case CMD_ERR_RANGE: return "ERR RANGE";
        case CMD_ERR_ARG: return "ERR ARG";
        case CMD_ERR_UNKNOWN: return "ERR UNKNOWN";
        case CMD_ERR_OVERFLOW: return "ERR OVERFLOW";
    }
    return "ERR UNKNOWN";
}

// digits only. RANGE if above max, ARG if not a number
static cmd_status_t parse_num(const char *s, uint32_t max, uint32_t *out) {
    uint32_t v = 0;
    if (s == NULL || *s == '\0') return CMD_ERR_ARG;
    for (const char *p = s; *p; p++) {
        if (*p < '0' || *p > '9') return CMD_ERR_ARG;
    }
    for (const char *p = s; *p; p++) {
        v = v * 10 + (uint32_t)(*p - '0');
        if (v > max) return CMD_ERR_RANGE;
    }
    *out = v;
    return CMD_OK;
}

static cmd_status_t reply_err(cmd_status_t st, char *reply, size_t cap) {
    snprintf(reply, cap, "%s", cmd_status_str(st));
    return st;
}

cmd_status_t cmd_exec(const char *line, settings_t *s, char *reply, size_t cap) {
    char tmp[CMD_MAX_LEN + 1];
    char *tok[4] = {0};
    int n = 0;

    if (strlen(line) > CMD_MAX_LEN) return reply_err(CMD_ERR_OVERFLOW, reply, cap);
    strcpy(tmp, line);

    // split on spaces, at most 3 tokens
    char *p = tmp;
    while (*p) {
        while (*p == ' ') *p++ = '\0';
        if (!*p) break;
        if (n == 3) return reply_err(CMD_ERR_ARG, reply, cap);
        tok[n++] = p;
        while (*p && *p != ' ') p++;
    }
    if (n == 0) return reply_err(CMD_ERR_UNKNOWN, reply, cap);

    if (strcmp(tok[0], "PING") == 0) {
        if (n != 1) return reply_err(CMD_ERR_ARG, reply, cap);
        snprintf(reply, cap, "PONG");
        return CMD_OK;
    }

    if (strcmp(tok[0], "GET") == 0) {
        if (n != 2) return reply_err(CMD_ERR_ARG, reply, cap);
        if (strcmp(tok[1], "THR") == 0) {
            snprintf(reply, cap, "OK THR=%u", (unsigned)s->thr);
            return CMD_OK;
        }
        if (strcmp(tok[1], "STUCK") == 0) {
            snprintf(reply, cap, "OK STUCK=%lu", (unsigned long)s->stuck_ms);
            return CMD_OK;
        }
        return reply_err(CMD_ERR_UNKNOWN, reply, cap);
    }

    if (strcmp(tok[0], "SET") == 0) {
        if (n != 3) return reply_err(CMD_ERR_ARG, reply, cap);
        uint32_t v = 0;
        cmd_status_t st;
        if (strcmp(tok[1], "THR") == 0) {
            st = parse_num(tok[2], THR_MAX, &v);
            if (st != CMD_OK) return reply_err(st, reply, cap);
            s->thr = (uint16_t)v;
            snprintf(reply, cap, "OK THR=%u", (unsigned)s->thr);
            return CMD_OK;
        }
        if (strcmp(tok[1], "STUCK") == 0) {
            st = parse_num(tok[2], STUCK_MS_MAX, &v);
            if (st != CMD_OK) return reply_err(st, reply, cap);
            s->stuck_ms = v;
            snprintf(reply, cap, "OK STUCK=%lu", (unsigned long)s->stuck_ms);
            return CMD_OK;
        }
        return reply_err(CMD_ERR_UNKNOWN, reply, cap);
    }

    return reply_err(CMD_ERR_UNKNOWN, reply, cap);
}

// ---- alarm ----

bool alarm_update(alarm_t *a, uint16_t value, uint16_t thr) {
    if (!a->latched && value > thr) {
        a->latched = true;
        return true;
    }
    return false;
}

ack_result_t alarm_ack(alarm_t *a, uint16_t value, uint16_t thr) {
    if (!a->latched) return ACK_IDLE;
    if (value > thr) return ACK_DENIED;
    a->latched = false;
    return ACK_CLEARED;
}

// ---- sensor faults ----

void fault_reset(fault_t *f) {
    memset(f, 0, sizeof(*f));
}

void fault_update(fault_t *f, uint16_t value, uint32_t now_ms, uint32_t stuck_ms) {
    f->range = value < ADC_RANGE_MIN || value > ADC_RANGE_MAX;

    int diff = (int)value - (int)f->ref;
    if (!f->started || diff > STUCK_DELTA || diff < -STUCK_DELTA) {
        f->started = true;
        f->ref = value;
        f->ref_ms = now_ms;
    }
    f->stuck = stuck_ms > 0 && (uint32_t)(now_ms - f->ref_ms) >= stuck_ms;
}

char state_char(const fault_t *f, const alarm_t *a, bool sensor_ok) {
    if (!sensor_ok || f->range || f->stuck) return 'F';
    if (a->latched) return 'A';
    return 'N';
}
