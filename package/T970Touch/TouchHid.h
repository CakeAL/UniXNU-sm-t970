// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once

#include <stdint.h>

constexpr unsigned t970TouchSlots = 10;
constexpr unsigned t970TouchMaxX = 1751;
constexpr unsigned t970TouchMaxY = 2799;

struct T970TouchFrame {
    uint16_t active = 0;
    uint16_t down = 0;
    uint16_t x[t970TouchSlots] = {};
    uint16_t y[t970TouchSlots] = {};

    bool apply(const uint8_t *record) {
        const unsigned action = record[0] >> 6;
        const unsigned id = (record[0] >> 2) & 15u;
        if ((record[0] & 3u) || !action || id >= t970TouchSlots) return false;
        const auto mask = static_cast<uint16_t>(1u << id);
        if (action == 3) {
            if (!(active & mask)) return false;
            down = 0;
            active = static_cast<uint16_t>(active & ~mask);
            return true;
        }
        const unsigned rawX = (unsigned{record[1]} << 4) | (unsigned{record[3]} >> 4);
        const unsigned rawY = (unsigned{record[2]} << 4) | (unsigned{record[3]} & 15u);
        if (rawX > t970TouchMaxX || rawY > t970TouchMaxY) return false;
        if (action == 2 && !(active & mask)) return false;
        down = action == 1 ? mask : 0;
        active |= mask;
        x[id] = static_cast<uint16_t>(rawX);
        y[id] = static_cast<uint16_t>(rawY);
        return true;
    }
};

bool t970_touch_hid_start();
bool t970_touch_hid_frame(const T970TouchFrame &frame);
