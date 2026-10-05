// UART data frame
// format: $D,<seq>,<ms>,<pot>,<ax>,<ay>,<az>,<state>*<CS>
// CS = XOR of all chars between $ and *, two upper case hex digits
// ax/ay/az are in mg. state is N (normal), A (alarm) or F (fault)
#ifndef FRAME_H
#define FRAME_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FRAME_MAX_LEN 80
#define FRAME_POT_MAX 4095

#define FRAME_OK 0
#define FRAME_ERR_FORMAT -1
#define FRAME_ERR_CHECKSUM -2
#define FRAME_ERR_RANGE -3

typedef struct {
    uint32_t seq;
    uint32_t ms;
    uint16_t pot;
    int16_t ax;
    int16_t ay;
    int16_t az;
    char state;
} frame_t;

uint8_t frame_checksum(const char *s, size_t n);

// writes a null terminated frame (no newline). returns length or -1
int frame_encode(const frame_t *f, char *out, size_t cap);

// strict parser. no leading zeros, no extra fields, upper case hex only
// returns FRAME_OK or a negative error
int frame_parse(const char *line, frame_t *f);

#ifdef __cplusplus
}
#endif

#endif
