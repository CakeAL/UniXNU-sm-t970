// SPDX-License-Identifier: MIT
#pragma once
#include "A650GmuPower.h"
#include "../T970Touch/BusSnapshot.h"

namespace t970_gpu {

struct RscSnapshot {
    const char *state = "skip";
    uint32_t gmuBusy = 0;
    uint32_t config = 0, status = 0, busy = 0, irqEnable = 0, irqStatus = 0;
    unsigned idle = 0;
    uint32_t hidden[6] = {}, route[5] = {}, seq[5] = {};
    uint32_t pdcStart = 0, pdcEnable = 0;
    bool tablesRead = false;
};

// The caller holds CX and all three XO clock branches with CM3 in reset.
static RscSnapshot sampleRsc(IOMemoryMap &gmu) {
    using namespace t970_touch;
    RscSnapshot result;
    // RPMH_CTRL, RSCC_CONTROL_REQ and RSCC_CONTROL_ACK in the GMU window.
    result.gmuBusy = read(gmu, 0x143a0) | read(gmu, 0x24c1c) | read(gmu, 0x24c20);
    if (result.gmuBusy) {
        result.state = "gmu-busy";
        return result;
    }
    auto rscc = mapMmio(A650_GPU_BASE_RSCC, 0x10000, kIOMapReadOnly);
    if (!rscc || !rscc->getVirtualAddress()) {
        result.state = "rscc-map";
        return result;
    }
    result.config = read(*rscc, 0xc);
    result.status = read(*rscc, 0x10);
    result.busy = read(*rscc, 0x404);
    if (result.config != 0x4000000a) {
        result.state = "layout";
        return result;
    }

    // lmi DRV0 has ten slots of eight commands. Inspect the same status,
    // control, wait and enable registers without reading or issuing commands.
    result.irqEnable = read(*rscc, 0xd00);
    result.irqStatus = read(*rscc, 0xd04);
    for (unsigned slot = 0; slot < 10; ++slot) {
        const unsigned base = 0xd00 + slot * 0x2a0;
        const uint32_t pending = read(*rscc, base + 0x10) |
                                 read(*rscc, base + 0x14) | read(*rscc, base + 0x1c);
        if (read(*rscc, base + 0x18) == 1 && !pending) result.idle |= 1u << slot;
    }
    if ((result.status & 0x10000) || result.busy || result.irqStatus || result.idle != 0x3ff) {
        result.state = "busy";
        return result;
    }
    constexpr unsigned routing[] = {0x2c, 0x400, 0x20, 0x24, 0x28};
    for (unsigned i = 0; i < 6; ++i) result.hidden[i] = read(*rscc, 0x34 + i * 4);
    for (unsigned i = 0; i < 5; ++i) {
        result.route[i] = read(*rscc, routing[i]);
        result.seq[i] = read(*rscc, 0x600 + i * 4);
    }
    result.tablesRead = true;

    // T970 stock kgsl_gmu_pdc_cfg. The PDC sequencer is a separate resource.
    auto pdc = mapMmio(0x0b290000, 0x10000, kIOMapReadOnly);
    if (!pdc || !pdc->getVirtualAddress()) {
        result.state = "pdc-map";
        return result;
    }
    result.pdcStart = read(*pdc, 0x4520);
    result.pdcEnable = read(*pdc, 0x4500);
    result.state = "read";
    return result;
}

static void reportRsc(char *out, unsigned length, const RscSnapshot &rsc, bool restored) {
    const int used = snprintf(out, length,
        "\nGPU rsc %s cfg/st/busy=%x/%x/%x g=%x irq=%x/%x idle=%x xo=7/7 cx=1/%u",
        rsc.state, rsc.config, rsc.status, rsc.busy, rsc.gmuBusy,
        rsc.irqEnable, rsc.irqStatus, rsc.idle, restored ? 1u : 0u);
    if (!rsc.tablesRead || used < 0 || static_cast<unsigned>(used) >= length) return;
    const auto &h = rsc.hidden;
    const auto &r = rsc.route;
    const auto &s = rsc.seq;
    snprintf(out + used, length - used,
        "\nRSC hidden=%x/%x/%x/%x/%x/%x route=%x/%x/%x/%x/%x seq=%x/%x/%x/%x/%x pdc=%x/%x",
        h[0], h[1], h[2], h[3], h[4], h[5], r[0], r[1], r[2], r[3], r[4],
        s[0], s[1], s[2], s[3], s[4], rsc.pdcStart, rsc.pdcEnable);
}

} // namespace t970_gpu
