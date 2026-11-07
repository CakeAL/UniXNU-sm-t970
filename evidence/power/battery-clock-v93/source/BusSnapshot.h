// SPDX-License-Identifier: BSD-2-Clause-Patent
// Board-only QUP0/NORTH GPIO28/29 handoff snapshot. Reuses the board's MMIO helpers.
#pragma once
#include "../T970Touch/BusSnapshot.h"

namespace t970_power {
static void reportClockProbe(IOMemoryMap &gcc, char *out, unsigned length) {
    using namespace t970_touch;
    uint32_t votes = read(gcc, 0x52008);
    constexpr uint32_t required = (1u << 10) | (1u << 6) | (1u << 7);
    uint32_t before = read(gcc, 0x17008);
    if ((votes & required) != required ||
        ((read(gcc, 0x1700c) | read(gcc, 0x17004)) & (1u << 31))) {
        snprintf(out, length, "\nBattery CLK refused votes=%x", votes);
        return;
    }
    bool borrowed = (before & ((1u << 31) | 2u)) == ((1u << 31) | 2u);
    if (borrowed) writeMasked(gcc, 0x17008, 2, 0);
    for (unsigned us = 0; us < 250 && (read(gcc, 0x17008) & (1u << 31)); ++us) IODelay(1);
    uint32_t during = read(gcc, 0x17008);
    EngineSnapshot sample;
    if (!(during & (1u << 31))) {
        auto engine = mapMmio(0x980000, 0x4000);
        if (engine) sample = {"read", read(*engine, 0x68), read(*engine, 0x64) & 1u, read(*engine, 0x40)};
        else sample.state = "map-fail";
    }
    if (borrowed) writeMasked(gcc, 0x17008, 2, before);
    bool restored = (read(gcc, 0x17008) & 2u) == (before & 2u);
    snprintf(out, length, "\nBattery CLK slave=%x/%x restore=%u SE=%s fw=%x fifoOff=%u st=%x",
             before, during, restored, sample.state, sample.firmware, sample.fifoOff, sample.status);
}

static void reportBus(char *out, unsigned length) {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-battery-ro", &enabled, sizeof(enabled)) || (enabled != 1 && enabled != 2)) return;
    if (!out || !length) return;
    auto gcc = t970_touch::mapMmio(0x100000, 0x53000);
    auto pins = t970_touch::mapMmio(0x0f91c000, 0x2000);
    if (!gcc || !pins) {
        snprintf(out, length, "\nBattery RO mapping failed");
        return;
    }
    if (enabled == 2) {
        // Only slave AHB HWCG is borrowed; SE0's existing vote and pins are retained.
        gcc = t970_touch::mapMmio(0x100000, 0x53000, 0);
        if (gcc) reportClockProbe(*gcc, out, length);
        else snprintf(out, length, "\nBattery CLK mapping failed");
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
