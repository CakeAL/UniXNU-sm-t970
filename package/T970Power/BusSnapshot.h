// SPDX-License-Identifier: BSD-2-Clause-Patent
// Board-only QUP0/NORTH GPIO28/29 handoff snapshot. Reuses the board's MMIO helpers.
#pragma once
#include "../T970Touch/BusSnapshot.h"

namespace t970_power {
static void reportBus(char *out, unsigned length) {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-battery-ro", &enabled, sizeof(enabled)) || enabled != 1) return;
    if (!out || !length) return;
    auto gcc = t970_touch::mapMmio(0x100000, 0x53000);
    auto pins = t970_touch::mapMmio(0x0f91c000, 0x2000);
    if (!gcc || !pins) {
        snprintf(out, length, "\nBattery RO mapping failed");
        return;
    }
    uint32_t votes = t970_touch::read(*gcc, 0x52008);
    uint32_t se = t970_touch::read(*gcc, 0x1700c);
    uint32_t master = t970_touch::read(*gcc, 0x17004);
    uint32_t slave = t970_touch::read(*gcc, 0x17008);
    // Never touch the serial engine if any AHB/SE branch reports CLK_OFF.
    bool live = (votes & ((1u << 10) | (1u << 6) | (1u << 7))) ==
                           ((1u << 10) | (1u << 6) | (1u << 7)) &&
                !((se | master | slave) & (1u << 31));
    uint32_t firmware = 0, state = 0;
    const char *engineState = "gated";
    if (live) {
        auto engine = t970_touch::mapMmio(0x980000, 0x4000);
        engineState = "mapping-failed";
        if (engine) {
            firmware = t970_touch::read(*engine, 0x68);
            state = t970_touch::read(*engine, 0x40);
            engineState = "sampled";
        }
    }
    snprintf(out, length, "\nBattery RO vote=%x clk=%x/%x/%x gpio28/29=%x/%x io=%x/%x SE=%s fw=%x st=%x",
        votes, se, master, slave,
        t970_touch::read(*pins, 0), t970_touch::read(*pins, 0x1000),
        t970_touch::read(*pins, 4), t970_touch::read(*pins, 0x1004),
        engineState, firmware, state);
}
}
