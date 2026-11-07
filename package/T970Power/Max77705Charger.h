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

// Charger configuration snapshot (read-only). Register meanings follow the
// pinned vendor header: CNFG_00 bit4 WDTEN, CNFG_02 bits5:0 CHG_CC in 50 mA
// steps, CNFG_04 bits5:0 float-voltage code, CNFG_09 bit7 CHG_EN and bits6:0
// CHGIN_LIM in 25 mA steps (code = mA/25 - 1, zero disables the limit).
struct t970_charger_config {
    bool valid;
    uint8_t cnfg00;
    uint8_t cnfg02;
    uint8_t cnfg04;
    uint8_t cnfg06;
    uint8_t cnfg09;
    bool watchdogEnabled;
    bool chargeEnabled;
    unsigned chargeCurrentMa;
    unsigned inputCurrentMa;
    unsigned floatVoltageCode;
};

static inline t970_charger_config t970_charger_config_decode(const uint8_t raw[5], bool valid) {
    t970_charger_config cfg = {};
    cfg.valid = valid;
    if (!valid) return cfg;
    cfg.cnfg00 = raw[0];
    cfg.cnfg02 = raw[1];
    cfg.cnfg04 = raw[2];
    cfg.cnfg06 = raw[3];
    cfg.cnfg09 = raw[4];
    cfg.watchdogEnabled = ((cfg.cnfg00 >> 4) & 1u) != 0;
    cfg.chargeEnabled = ((cfg.cnfg09 >> 7) & 1u) != 0;
    cfg.chargeCurrentMa = (cfg.cnfg02 & 0x3fu) * 50u;
    const unsigned inputCode = cfg.cnfg09 & 0x7fu;
    cfg.inputCurrentMa = inputCode ? (inputCode + 1u) * 25u : 0;
    cfg.floatVoltageCode = cfg.cnfg04 & 0x3fu;
    return cfg;
}

} // namespace t970_power
