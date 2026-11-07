// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include "../T970Touch/BusSnapshot.h"
#include "Max77705Measurements.h"

namespace t970_power {
// Caller must first qualify an idle I2C SE0 and restore its AHB clock control.
static void reportGauge(char *out, unsigned length) {
    using namespace t970_touch;
    auto pins = mapMmio(0x0f91c000, 0x2000, 0);
    if (!pins) { snprintf(out, length, "\nGauge: TLMM map failed"); return; }
    uint32_t saved[2] = {read(*pins, 0), read(*pins, 0x1000)};
    if (saved[0] != 7 || saved[1] != 7) {
        snprintf(out, length, "\nGauge: refused pins=%x/%x", saved[0], saved[1]);
        return;
    }
    uint32_t latches[2] = {read(*pins, 4) & 2u, read(*pins, 0x1004) & 2u};
    constexpr uint32_t control = (1u << 9) | (15u << 2);
    // Release both lines, retain the existing pull-ups, then select GPIO mode.
    for (unsigned i = 0; i < 2; ++i) {
        unsigned pin = i * 0x1000;
        writeMasked(*pins, pin + 4, 2, 0);
        writeMasked(*pins, pin, control, 0);
    }
    IODelay(100);
    t970_battery_measurements values = {};
    uint8_t id[2] = {}, charger[3] = {};
    uint16_t raw[7] = {};
    const uint8_t registers[] = {0x00, 0x06, 0x09, 0x0a, 0x08, 0x05, 0x10};
    const char *stage = "lines-low", *fault = "none";
    unsigned failedRegister = 0, chargerValid = 0;
    if ((read(*pins, 4) & 1u) && (read(*pins, 0x1004) & 1u)) {
        ProbeBus pmic(*pins, 0x66);
        uint8_t reg = 0;
        bool identified = pmic.transfer(&reg, 1, id, sizeof(id));
        fault = pmic.fault;
        stage = "pmic-read";
        if (identified) {
            unsigned revision = id[1] & 7u;
            identified = (id[0] == 5 && (revision == 3 || revision == 4)) ||
                         (id[0] == 0x15 && revision == 2);
            stage = "pmic-id";
        }
        if (identified) {
            ProbeBus gauge(*pins, T970_GAUGE_ADDRESS);
            stage = "done";
            for (unsigned i = 0; i < sizeof(registers); ++i) {
                uint8_t bytes[2] = {};
                if (!gauge.transfer(&registers[i], 1, bytes, sizeof(bytes))) {
                    stage = "gauge-read"; fault = gauge.fault; failedRegister = registers[i]; break;
                }
                raw[i] = static_cast<uint16_t>(bytes[0] | (unsigned(bytes[1]) << 8));
                t970_battery_word(&values, registers[i], bytes, sizeof(bytes));
            }
            if (values.valid == 0x7f) {
                ProbeBus charge(*pins, T970_CHARGER_ADDRESS);
                // INT_OK and DETAILS_00/01 only. Avoid the read-to-clear INT register.
                uint8_t chargeReg = 0xb2;
                chargerValid = charge.transfer(&chargeReg, 1, charger, sizeof(charger));
                if (!chargerValid) { stage = "charger-read"; fault = charge.fault; }
            }
        }
    }
    for (unsigned i = 0; i < 2; ++i) {
        unsigned pin = i * 0x1000;
        writeMasked(*pins, pin, control, 0);
        writeMasked(*pins, pin + 4, 2, latches[i]);
        writeMasked(*pins, pin, control, saved[i]);
    }
    bool restored = read(*pins, 0) == saved[0] && read(*pins, 0x1000) == saved[1] &&
                    (read(*pins, 4) & 2u) == latches[0] && (read(*pins, 0x1004) & 2u) == latches[1];
    snprintf(out, length,
        "\nGauge id=%02x/%02x valid=%x raw=%x/%x/%x/%x/%x/%x/%x"
        "\nBat present=%u soc100=%u uV=%u uA=%d mC=%d cap=%u/%u chg=%u:%02x/%02x/%02x restore=%u %s/%s reg=%x",
        id[0], id[1], values.valid, raw[0], raw[1], raw[2], raw[3], raw[4], raw[5], raw[6],
        values.present, values.percent_x100, values.voltage_uv, values.current_ua, values.temperature_mc,
        values.remaining_mah, values.full_mah, chargerValid, charger[0], charger[1], charger[2],
        restored, stage, fault, failedRegister);
}
}
