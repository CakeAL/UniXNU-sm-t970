// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include "../T970Touch/BusSnapshot.h"
#include "Max77705Charger.h"
#include "Max77705Measurements.h"

namespace t970_power {
// One bounded read of PMIC 0x66, gauge 0x36 and (after a complete gauge
// sample) charger 0x69. The sample keeps the raw words so the terminal report
// and the periodic service can print or publish exactly what was read.
struct GaugeSample {
    bool mapped = false;
    bool pinsAccepted = false;
    uint32_t pinConfig[2] = {};
    uint8_t id[2] = {};
    uint8_t charger[3] = {};
    uint8_t config[5] = {};
    uint16_t raw[7] = {};
    t970_battery_measurements values = {};
    bool identified = false;
    bool chargerValid = false;
    bool configValid = false;
    bool restored = false;
    const char *stage = "lines-low";
    const char *fault = "none";
    unsigned failedRegister = 0;
};

// Caller must first qualify an idle I2C SE0 and restore its AHB clock control.
// Returns true only when the PMIC identity matched and all seven gauge words
// were read; a partially valid sample still carries the bytes it did read.
static bool readGaugeSample(GaugeSample &sample) {
    using namespace t970_touch;
    sample = GaugeSample{};
    auto pins = mapMmio(0x0f91c000, 0x2000, 0);
    if (!pins) { sample.stage = "map"; return false; }
    sample.mapped = true;
    uint32_t saved[2] = {read(*pins, 0), read(*pins, 0x1000)};
    sample.pinConfig[0] = saved[0];
    sample.pinConfig[1] = saved[1];
    if (saved[0] != 7 || saved[1] != 7) {
        sample.stage = "pins";
        return false;
    }
    sample.pinsAccepted = true;
    uint32_t latches[2] = {read(*pins, 4) & 2u, read(*pins, 0x1004) & 2u};
    constexpr uint32_t control = (1u << 9) | (15u << 2);
    // Release both lines, retain the existing pull-ups, then select GPIO mode.
    for (unsigned i = 0; i < 2; ++i) {
        unsigned pin = i * 0x1000;
        writeMasked(*pins, pin + 4, 2, 0);
        writeMasked(*pins, pin, control, 0);
    }
    IODelay(100);
    bool identified = false;
    const uint8_t registers[] = {0x00, 0x06, 0x09, 0x0a, 0x08, 0x05, 0x10};
    if ((read(*pins, 4) & 1u) && (read(*pins, 0x1004) & 1u)) {
        ProbeBus pmic(*pins, 0x66);
        uint8_t reg = 0;
        identified = pmic.transfer(&reg, 1, sample.id, sizeof(sample.id));
        sample.fault = pmic.fault;
        sample.stage = "pmic-read";
        if (identified) {
            unsigned revision = sample.id[1] & 7u;
            identified = (sample.id[0] == 5 && (revision == 3 || revision == 4)) ||
                         (sample.id[0] == 0x15 && revision == 2);
            sample.stage = "pmic-id";
        }
        if (identified) {
            ProbeBus gauge(*pins, T970_GAUGE_ADDRESS);
            sample.stage = "done";            for (unsigned i = 0; i < sizeof(registers); ++i) {
                uint8_t bytes[2] = {};
                if (!gauge.transfer(&registers[i], 1, bytes, sizeof(bytes))) {
                    sample.stage = "gauge-read";
                    sample.fault = gauge.fault;
                    sample.failedRegister = registers[i];
                    break;
                }
                sample.raw[i] = static_cast<uint16_t>(bytes[0] | (unsigned(bytes[1]) << 8));
                t970_battery_word(&sample.values, registers[i], bytes, sizeof(bytes));
            }
            if (sample.values.valid == 0x7f) {
                ProbeBus charge(*pins, T970_CHARGER_ADDRESS);
                // INT_OK and DETAILS_00/01 only. Avoid the read-to-clear INT register.
                uint8_t chargeReg = 0xb2;
                sample.chargerValid = charge.transfer(&chargeReg, 1, sample.charger,
                                                      sizeof(sample.charger));
                if (!sample.chargerValid) {
                    sample.stage = "charger-read";
                    sample.fault = charge.fault;
                } else {
                    // Read-only configuration snapshot: CNFG_00/02/04/06/09.
                    const uint8_t configRegisters[] = {0xb7, 0xb9, 0xbb, 0xbd, 0xc0};
                    ProbeBus config(*pins, T970_CHARGER_ADDRESS);
                    sample.configValid = true;
                    for (unsigned i = 0; i < sizeof(configRegisters); ++i) {
                        if (!config.transfer(&configRegisters[i], 1, &sample.config[i], 1)) {
                            sample.configValid = false;
                            sample.stage = "charger-config";
                            sample.fault = config.fault;
                            break;
                        }
                    }
                }
            }
        }
    }
    for (unsigned i = 0; i < 2; ++i) {
        unsigned pin = i * 0x1000;
        writeMasked(*pins, pin, control, 0);
        writeMasked(*pins, pin + 4, 2, latches[i]);
        writeMasked(*pins, pin, control, saved[i]);
    }
    sample.identified = identified;
    sample.restored = read(*pins, 0) == saved[0] && read(*pins, 0x1000) == saved[1] &&
                      (read(*pins, 4) & 2u) == latches[0] && (read(*pins, 0x1004) & 2u) == latches[1];
    return sample.values.valid == 0x7f;
}

static void formatGaugeSample(const GaugeSample &sample, char *out, unsigned length) {
    if (!sample.mapped) {
        snprintf(out, length, "\nGauge: TLMM map failed");
        return;
    }
    if (!sample.pinsAccepted) {
        snprintf(out, length, "\nGauge: refused pins=%x/%x", sample.pinConfig[0], sample.pinConfig[1]);
        return;
    }
    snprintf(out, length,
        "\nGauge id=%02x/%02x valid=%x raw=%x/%x/%x/%x/%x/%x/%x"
        "\nBat present=%u soc100=%u uV=%u uA=%d mC=%d cap=%u/%u chg=%u:%02x/%02x/%02x restore=%u %s/%s reg=%x",
        sample.id[0], sample.id[1], sample.values.valid,
        sample.raw[0], sample.raw[1], sample.raw[2], sample.raw[3],
        sample.raw[4], sample.raw[5], sample.raw[6],
        sample.values.present, sample.values.percent_x100, sample.values.voltage_uv,
        sample.values.current_ua, sample.values.temperature_mc,
        sample.values.remaining_mah, sample.values.full_mah, sample.chargerValid,
        sample.charger[0], sample.charger[1], sample.charger[2],
        sample.restored, sample.stage, sample.fault, sample.failedRegister);
    size_t used = strlen(out);
    if (used < length && sample.chargerValid) {
        t970_power::t970_charger_config config = t970_power::t970_charger_config_decode(sample.config, sample.configValid);
        snprintf(out + used, length - used,
            "\nCharger cfg=%02x/%02x/%02x/%02x/%02x wdtEn=%u chgEn=%u ichg=%umA iin=%umA cv=%02x%s",
            sample.config[0], sample.config[1], sample.config[2], sample.config[3], sample.config[4],
            unsigned(config.watchdogEnabled), unsigned(config.chargeEnabled),
            config.chargeCurrentMa, config.inputCurrentMa, config.floatVoltageCode,
            config.valid ? "" : " partial");
    }
}

static void reportGauge(char *out, unsigned length) {
    GaugeSample sample;
    readGaugeSample(sample);
    formatGaugeSample(sample, out, length);
}
}
