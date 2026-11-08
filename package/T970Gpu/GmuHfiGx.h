// SPDX-License-Identifier: MIT
#pragma once
#include "GmuHfiCore.h"

namespace t970_gpu {

struct GmuHfiGxProbe {
    GmuHfiProbe start, dcvs;
    const char *state = "skip";
    uint32_t before = 0, after = 0, ack = 0, irqAfter = 0, fence = 0;
};

}

#ifdef T970_GPU_GMU_FIRMWARE
namespace t970_gpu {

template <typename Healthy>
static void probeGmuHfiGx(IOMemoryMap &gmu, GmuTables &tables, GmuHfiGxProbe &result, Healthy healthy) {
    using t970_touch::read;
    using t970_touch::write;
    constexpr unsigned irqClear = 0x14644, irqInfo = 0x14648, doorbell = 0x14650;
    constexpr unsigned powerStatus = 0x14340, fenceStatus = 0x24c4c;
    constexpr uint32_t gxOff = 0xc0, request = 1u << 30, ack = 1u << 31;

    constexpr uint32_t start[] = {0x0050010a};
    exchangeGmuHfi(gmu, tables, {start, 1, 228, 16}, result.start, healthy);
    if (strcmp(result.start.state, "ok")) return;
    // Index 1 is the lowest active T970 OPP (305 MHz); leave bandwidth unchanged.
    constexpr uint32_t dcvs[] = {0x0060041e, 1, 1, 0xff};
    exchangeGmuHfi(gmu, tables, {dcvs, 4, 232, 20}, result.dcvs, healthy);
    if (strcmp(result.dcvs.state, "ok")) return;

    result.state = "guard";
    result.before = read(gmu, powerStatus);
    result.fence = read(gmu, fenceStatus);
    result.ack = read(gmu, irqInfo);
    if (result.before == UINT32_MAX || result.fence || result.ack || !healthy()) return;

    result.state = "oob";
    write(gmu, doorbell, request);
    for (unsigned i = 0; i < 1000; ++i) {
        result.ack = read(gmu, irqInfo);
        if (!healthy()) return;
        if (result.ack == ack) {
            // Clear only the response IRQ. Keep the GPU request and backing live.
            write(gmu, irqClear, ack);
            result.irqAfter = read(gmu, irqInfo);
            result.after = read(gmu, powerStatus);
            result.fence = read(gmu, fenceStatus);
            result.state = "power";
            if (!result.irqAfter && !(result.after & gxOff) && !result.fence && healthy())
                result.state = "ok";
            return;
        }
        if (result.ack) return;
        IODelay(100);
    }
}

}
#endif
