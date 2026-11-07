// SPDX-License-Identifier: BSD-2-Clause-Patent
// Measurement encoding from the pinned stock sources in docs/peripherals.md.
// This decoder performs no I/O and never writes charger/gauge configuration.
#pragma once
#include <stdint.h>

enum {
    T970_GAUGE_ADDRESS = 0x36,
    T970_CHARGER_ADDRESS = 0x69,
    T970_BAT_PRESENT = 1u << 0,
    T970_BAT_SOC = 1u << 1,
    T970_BAT_VOLTAGE = 1u << 2,
    T970_BAT_CURRENT = 1u << 3,
    T970_BAT_TEMPERATURE = 1u << 4,
    T970_BAT_REMAINING = 1u << 5,
    T970_BAT_FULL = 1u << 6,
};

struct t970_battery_measurements {
    uint32_t valid;
    uint32_t present, percent_x100, voltage_uv;
    int32_t current_ua, temperature_mc;
    uint32_t remaining_mah, full_mah;
};

// A new refresh starts with valid=0; only successfully read words become valid.
// The board's vendor fg_resistor parameter is 5 (not a resistance in milliohms).
static inline int t970_battery_word(struct t970_battery_measurements *out,
                                   uint8_t reg, const uint8_t *data, unsigned length)
{
    if (!out || !data || length != 2) return 0;
    uint32_t raw = (uint32_t)data[0] | ((uint32_t)data[1] << 8);
    int32_t signed_raw = raw < 0x8000 ? (int32_t)raw : (int32_t)raw - 65536;
    switch (reg) {
    case 0x00:
        out->present = (raw & (1u << 3)) == 0;
        out->valid |= T970_BAT_PRESENT;
        break;
    case 0x06:
        out->percent_x100 = raw * 100 / 256;
        if (out->percent_x100 > 10000) out->percent_x100 = 10000;
        out->valid |= T970_BAT_SOC;
        break;
    case 0x09:
        out->voltage_uv = (uint32_t)((uint64_t)raw * 78125 / 1000);
        out->valid |= T970_BAT_VOLTAGE;
        break;
    case 0x0a:
        out->current_ua = (int32_t)((int64_t)signed_raw * 15625 * 5 / 100);
        out->valid |= T970_BAT_CURRENT;
        break;
    case 0x08:
        out->temperature_mc = signed_raw * 1000 / 256;
        out->valid |= T970_BAT_TEMPERATURE;
        break;
    case 0x05:
        out->remaining_mah = raw * 5 / 2;
        out->valid |= T970_BAT_REMAINING;
        break;
    case 0x10:
        out->full_mah = raw * 5 / 2;
        out->valid |= T970_BAT_FULL;
        break;
    default:
        return 0;
    }
    return 1;
}
