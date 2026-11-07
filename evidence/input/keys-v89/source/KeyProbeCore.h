// SPDX-License-Identifier: BSD-2-Clause-Patent
// SM-T970 read-only SPMI PMIC arbiter access for the PON and PM8150L GPIO keys.
// Version-5 layout (SM8250, EE 0): APID map at core + 0x900, EE owner table at
// cnfg + 0x700, observer channels at 0x80 per APID. Only extended reads are
// issued; only the observer command register is written, never PMIC state.
#pragma once
#include <stdint.h>

enum {
    T970_ARB_V5_MIN = 0x50000000u,
    T970_ARB_V7_MIN = 0x70000000u,
    T970_ARB_CORE_BYTES = 0x1100,
    T970_ARB_V5_APID_MAP = 0x900,
    T970_ARB_V5_OWNER = 0x700,
    T970_ARB_OBS_STRIDE = 0x80,
    T970_ARB_CMD = 0x00,
    T970_ARB_STATUS = 0x08,
    T970_ARB_RDATA = 0x18,
    T970_ARB_DONE = 1u << 0,
    T970_ARB_ERRORS = 0xeu,
    T970_ARB_POLLS = 100000,
    T970_PON_PPID = 0x008,
    T970_GPIO_PPID = 0x4c3,
    T970_PON_RT_STS = 0x10,
    T970_GPIO_RT_STS = 0x10,
    T970_PON_POWER = 1u << 0,
    T970_PON_RESIN = 1u << 1,
    T970_GPIO_ACTIVE_LOW = 1u << 0,
};

struct t970_arbiter {
    volatile uint32_t *core;
    volatile uint32_t *cnfg;
    volatile uint32_t *obs;
    uint32_t apids;
};

// 0 for the version-5 layout this code knows; 1 otherwise.
static inline int t970_arb_version(struct t970_arbiter *a, uint32_t *version)
{
    uint32_t value = a->core[0];
    *version = value;
    if (value < T970_ARB_V5_MIN || value >= T970_ARB_V7_MIN) return 1;
    return 0;
}

// Number of APIDs the arbiter serves, bounded by the window the caller mapped.
static inline int t970_arb_apids(struct t970_arbiter *a, uint32_t *count)
{
    // Vendor v5 scans the APID table to core_size, not INT_EN at +4.
    uint32_t value = (T970_ARB_CORE_BYTES - T970_ARB_V5_APID_MAP) / 4;
    a->apids = value;
    *count = value;
    return 0;
}

// APID serving ppid, preferring one this execution environment owns. 0 found.
static inline int t970_arb_find(const struct t970_arbiter *a, uint32_t ppid, uint32_t *apid)
{
    int found = -1;
    for (uint32_t i = 0; i < a->apids; ++i) {
        uint32_t map = a->core[(T970_ARB_V5_APID_MAP + 4 * i) / 4];
        if (!map || ((map >> 8) & 0xfff) != ppid) continue;
        uint32_t owner = a->cnfg[(T970_ARB_V5_OWNER + 4 * i) / 4] & 7u;
        if (owner == 0) found = (int)i;
        if (owner == 0 && (map >> 24) & 1u) break;
    }
    if (found < 0) return 2;
    *apid = (uint32_t)found;
    return 0;
}

// One 4-byte extended read from a peripheral register page. 0 on success.
// 1 = no completion, 2 = the arbiter reported an error.
static inline int t970_arb_read32(const struct t970_arbiter *a, uint32_t apid, uint8_t reg, uint32_t *value)
{
    if (apid >= a->apids || reg > 0xfc) return 3;
    volatile uint32_t *ch = a->obs + (T970_ARB_OBS_STRIDE * apid) / 4;
    ch[T970_ARB_CMD / 4] = (1u << 27) | ((uint32_t)reg << 4) | 3u;
#if defined(__aarch64__)
    __asm__ volatile("dsb sy" ::: "memory");
#endif
    for (unsigned n = 0; n < T970_ARB_POLLS; ++n) {
        uint32_t status = ch[T970_ARB_STATUS / 4];
        if (status & T970_ARB_DONE) {
            if (status & T970_ARB_ERRORS) return 2;
            *value = ch[T970_ARB_RDATA / 4];
            return 0;
        }
    }
    return 1;
}

// The three key levels as one mask: bit 0 power, bit 1 volume up, bit 2 volume down.
static inline uint32_t t970_keys_mask(uint32_t pon_status, uint32_t gpio_status)
{
    uint32_t mask = 0;
    if (pon_status & T970_PON_POWER) mask |= 1u << 0;
    if (!(gpio_status & T970_GPIO_ACTIVE_LOW)) mask |= 1u << 1;
    if (pon_status & T970_PON_RESIN) mask |= 1u << 2;
    return mask;
}

// One key's edge state. `last` keeps the raw level, `live` ignores the level the
// key already had when the probe started (a held key must be released first),
// `down` is the reported state and `presses`/`releases` count accepted edges.
struct t970_key_state {
    uint8_t last, live, down;
    uint32_t presses, releases;
};

// 0 = no accepted change, 1 = press, 2 = release. Bounce is rejected because an
// edge only counts once two samples agree.
static inline int t970_key_update(struct t970_key_state *k, int down, int usable)
{
    down = down != 0;
    int steady = (k->last == down);
    k->last = (uint8_t)down;
    if (!usable || !steady) return 0;
    if (!k->live) {
        if (!down) k->live = 1;
        return 0;
    }
    if (k->down == down) return 0;
    k->down = (uint8_t)down;
    if (down) {
        ++k->presses;
        return 1;
    }
    ++k->releases;
    return 2;
}

// One report line: "Keys: v=50000000 pon=8 gpio=4c3 mask=5 power=1/1 up=0/1 down=0/0".
// Self-contained formatting so the same header builds in the kernel and on the host.
static inline char *t970_key_hex(char *out, uint32_t value, unsigned digits)
{
    static const char hex[] = "0123456789abcdef";
    for (unsigned i = 0; i < digits; ++i) out[digits - 1 - i] = hex[(value >> (4 * i)) & 15];
    out[digits] = 0;
    return out + digits;
}

static inline char *t970_key_dec(char *out, uint32_t value)
{
    char digits[10];
    unsigned n = 0;
    do { digits[n++] = (char)('0' + value % 10); value /= 10; } while (value);
    while (n) *out++ = digits[--n];
    *out = 0;
    return out;
}

static inline void t970_keys_text(char *out, unsigned size, uint32_t version, uint32_t pon_apid,
                                 uint32_t gpio_apid, uint32_t mask, const struct t970_key_state k[3])
{
    if (!out || !size) return;
    // Max-width counters fit in this local buffer; copy only what the caller owns.
    char text[192];
    char *p = text, *end = text + sizeof(text) - 1;
    const char *prefix = "Keys: v=";
    while (*prefix && p < end) *p++ = *prefix++;
    p = t970_key_hex(p, version, 8);
    const char *body = " pon=";
    while (*body) *p++ = *body++;
    p = t970_key_dec(p, pon_apid);
    body = " gpio=";
    while (*body) *p++ = *body++;
    p = t970_key_hex(p, gpio_apid, 3);
    body = " mask=";
    while (*body) *p++ = *body++;
    p = t970_key_dec(p, mask);
    for (unsigned i = 0; i < 3 && p < end; ++i) {
        const char *names[3] = {" power=", " up=", " down="};
        for (const char *q = names[i]; *q; ++q) *p++ = *q;
        p = t970_key_dec(p, k[i].presses);
        *p++ = '/';
        p = t970_key_dec(p, k[i].releases);
    }
    *p = 0;
    unsigned n = 0;
    while (text[n] && n + 1 < size) { out[n] = text[n]; ++n; }
    out[n] = 0;
}
