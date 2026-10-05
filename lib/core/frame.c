#include "frame.h"

#include <stdio.h>
#include <string.h>

uint8_t frame_checksum(const char *s, size_t n) {
    uint8_t cs = 0;
    for (size_t i = 0; i < n; i++) {
        cs ^= (uint8_t)s[i];
    }
    return cs;
}

static int valid_state(char c) {
    return c == 'N' || c == 'A' || c == 'F';
}

int frame_encode(const frame_t *f, char *out, size_t cap) {
    char body[FRAME_MAX_LEN];
    if (f == NULL || out == NULL) return -1;
    if (f->pot > FRAME_POT_MAX || !valid_state(f->state)) return -1;

    int n = snprintf(body, sizeof(body), "D,%lu,%lu,%u,%d,%d,%d,%c",
                     (unsigned long)f->seq, (unsigned long)f->ms, (unsigned)f->pot,
                     (int)f->ax, (int)f->ay, (int)f->az, f->state);
    if (n < 0 || (size_t)n >= sizeof(body)) return -1;

    uint8_t cs = frame_checksum(body, (size_t)n);
    int total = snprintf(out, cap, "$%s*%02X", body, cs);
    if (total < 0 || (size_t)total >= cap) return -1;
    return total;
}

static int hex_val(char c) {
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

// reads an unsigned decimal from p up to the next ',' or end.
// no sign, no leading zeros. moves p past the number
static int read_uint(const char **p, const char *end, uint32_t max, uint32_t *out) {
    const char *s = *p;
    uint64_t v = 0;
    int digits = 0;
    while (s < end && *s >= '0' && *s <= '9') {
        if (digits > 0 && v == 0) return FRAME_ERR_FORMAT;  // leading zero
        v = v * 10 + (uint64_t)(*s - '0');
        if (v > max) return FRAME_ERR_RANGE;
        digits++;
        s++;
    }
    if (digits == 0) return FRAME_ERR_FORMAT;
    *out = (uint32_t)v;
    *p = s;
    return FRAME_OK;
}

static int read_int16(const char **p, const char *end, int16_t *out) {
    const char *s = *p;
    int neg = 0;
    if (s < end && *s == '-') {
        neg = 1;
        s++;
    }
    uint32_t v = 0;
    int rc = read_uint(&s, end, neg ? 32768u : 32767u, &v);
    if (rc != FRAME_OK) return rc;
    if (neg && v == 0) return FRAME_ERR_FORMAT;  // no "-0"
    *out = neg ? (int16_t)(-(int32_t)v) : (int16_t)v;
    *p = s;
    return FRAME_OK;
}

static int expect_comma(const char **p, const char *end) {
    if (*p >= end || **p != ',') return FRAME_ERR_FORMAT;
    (*p)++;
    return FRAME_OK;
}

int frame_parse(const char *line, frame_t *f) {
    if (line == NULL || f == NULL) return FRAME_ERR_FORMAT;
    size_t len = 0;
    while (len <= FRAME_MAX_LEN && line[len] != '\0') len++;
    if (len > FRAME_MAX_LEN || len < 6) return FRAME_ERR_FORMAT;
    if (line[0] != '$' || line[1] != 'D' || line[2] != ',') return FRAME_ERR_FORMAT;

    // checksum is the last 3 chars: *HH
    if (line[len - 3] != '*') return FRAME_ERR_FORMAT;
    int hi = hex_val(line[len - 2]);
    int lo = hex_val(line[len - 1]);
    if (hi < 0 || lo < 0) return FRAME_ERR_FORMAT;

    const char *body = line + 1;
    const char *end = line + len - 3;
    if (memchr(body, '*', (size_t)(end - body)) != NULL) return FRAME_ERR_FORMAT;

    frame_t t;
    uint32_t v;
    const char *p = line + 3;
    int rc;

    if ((rc = read_uint(&p, end, 0xFFFFFFFFu, &v)) != FRAME_OK) return rc;
    t.seq = v;
    if ((rc = expect_comma(&p, end)) != FRAME_OK) return rc;
    if ((rc = read_uint(&p, end, 0xFFFFFFFFu, &v)) != FRAME_OK) return rc;
    t.ms = v;
    if ((rc = expect_comma(&p, end)) != FRAME_OK) return rc;
    if ((rc = read_uint(&p, end, FRAME_POT_MAX, &v)) != FRAME_OK) return rc;
    t.pot = (uint16_t)v;
    if ((rc = expect_comma(&p, end)) != FRAME_OK) return rc;
    if ((rc = read_int16(&p, end, &t.ax)) != FRAME_OK) return rc;
    if ((rc = expect_comma(&p, end)) != FRAME_OK) return rc;
    if ((rc = read_int16(&p, end, &t.ay)) != FRAME_OK) return rc;
    if ((rc = expect_comma(&p, end)) != FRAME_OK) return rc;
    if ((rc = read_int16(&p, end, &t.az)) != FRAME_OK) return rc;
    if ((rc = expect_comma(&p, end)) != FRAME_OK) return rc;
    if (p >= end || !valid_state(*p)) return FRAME_ERR_FORMAT;
    t.state = *p++;
    if (p != end) return FRAME_ERR_FORMAT;

    uint8_t cs = frame_checksum(body, (size_t)(end - body));
    if (cs != (uint8_t)(hi * 16 + lo)) return FRAME_ERR_CHECKSUM;

    *f = t;
    return FRAME_OK;
}
