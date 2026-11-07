// SPDX-License-Identifier: BSD-2-Clause-Patent
// MAX77705 charger status decode from the pinned stock source. No I/O and no
// configuration write; the caller supplies the 0xb2..0xb4 bytes it read.
#pragma once
#include <stdint.h>

namespace t970_power {

struct t970_charger_state {
    bool valid;
    bool external;
    bool charging;
    bool full;
    bool watchdogExpired;
    unsigned intOk;
    unsigned chginDtls;
    unsigned wcinDtls;
    unsigned chgDtls;
};

// DETAILS_00 bits 6:5 are CHGIN_DTLS, bits 4:3 are WCIN_DTLS and 3 means the
// input is inside its valid range. DETAILS_01 bits 3:0 are CHG_DTLS: 0..2
// charging, 3..4 full, 5..7 not charging, 8/0xa/0xb discharging; the vendor
// watchdog check treats 0xb specifically as the expired charger watchdog.
static inline t970_charger_state t970_charger_decode(const uint8_t raw[3], bool valid) {
    t970_charger_state state = {};
    state.valid = valid;
    if (!valid) return state;
    state.intOk = raw[0];
    state.chginDtls = (raw[1] >> 5) & 3u;
    state.wcinDtls = (raw[1] >> 3) & 3u;
    state.chgDtls = raw[2] & 0x0fu;
    state.external = state.chginDtls == 3 || state.wcinDtls == 3;
    state.charging = state.chgDtls <= 2;
    state.full = state.chgDtls == 3 || state.chgDtls == 4;
    state.watchdogExpired = state.chgDtls == 0x0b;
    return state;
}

} // namespace t970_power
