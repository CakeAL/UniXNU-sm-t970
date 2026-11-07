// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>

namespace t970_gpu {

struct GmuBootProbe {
    const char *state = "skip";
    uint32_t fwInit = 0, hfiStatus = 0, hfiVersion = 0, reset = 0;
    uint32_t globalFault = 0, contextFault = 0, aoStatus = 0, gmuStatus = 0;
    unsigned offset = 0;
    bool keepRoute = false;
};

}

#ifdef T970_GPU_GMU_FIRMWARE
#include "GmuFirmware.h"

namespace t970_gpu {

static bool prepareGmuBootHfi(GmuTables &tables) {
    // Vendor A650 layout from lmi mode 28: four headers and four rings in
    // five 4 KiB pages. This probe only publishes the cold queue table.
    constexpr uint32_t iova = 0x60001000;
    constexpr unsigned bytes = 5 * 4096;
    for (const auto &range : tables.ranges) {
        if (range.iova != iova || range.bytes != bytes) continue;
        auto *shared = reinterpret_cast<uint32_t *>(reinterpret_cast<uint8_t *>(tables.tables) +
            (range.physical - tables.config.table_physical));
        bzero(shared, bytes);
        const uint32_t table[] = {0, 54, 6, 12, 4, 4};
        memcpy(shared, table, sizeof(table));
        constexpr unsigned priorities[] = {10, 10, 40, 20};
        for (unsigned i = 0; i < 4; ++i) {
            auto *queue = shared + 6 + i * 12;
            queue[0] = i < 3;
            queue[1] = iova + 256 + i * 4096;
            queue[2] = i | (priorities[i] << 8);
            queue[3] = 1024;
        }
        return true;
    }
    return false;
}

// Board first-boot probe using the lmi A650 boot values with the T970 RSC
// sequence already in place. The caller retains the live SID5 context.
template <typename CheckRoute>
static void startGmuBoot(IOMemoryMap &gmu, GmuTables &tables, GmuBootProbe &result, CheckRoute checkRoute) {
    using t970_touch::read;
    using t970_touch::write;
    constexpr unsigned reset = 0x14000, fwInit = 0x14070;
    constexpr unsigned hfiInit = 0x14618, hfiStatus = 0x14600, hfiVersion = 0x14604;
    constexpr unsigned aoMask = 0x24c18, gmuMask = 0x1464c;
    constexpr uint32_t aoFatal = 0x29, cm3Fatal = 0x00800000;
    const auto healthy = [&]() {
        result.aoStatus = read(gmu, 0x24c14);
        result.gmuStatus = read(gmu, 0x14648);
        return checkRoute() && !(result.aoStatus & aoFatal) && !(result.gmuStatus & cm3Fatal);
    };
    const auto cold = [&]() {
        return read(gmu, reset) == 1 && read(gmu, fwInit) == 0 &&
            read(gmu, hfiInit) == 0 && read(gmu, hfiStatus) == 0;
    };
    result.state = "cold";
    result.reset = read(gmu, reset);
    if (!cold() || !healthy()) return;
    result.state = "queue";
    if (!prepareGmuBootHfi(tables)) return;
    publishGmuTables(tables);

    // Poll faults directly. The GMU/HFI interrupt handlers are not installed
    // in this diagnostic image.
    result.state = "mask";
    write(gmu, aoMask, UINT32_MAX);
    write(gmu, gmuMask, UINT32_MAX);
    if ((read(gmu, aoMask) & aoFatal) != aoFatal ||
        (read(gmu, gmuMask) & (cm3Fatal | 1)) != (cm3Fatal | 1)) return;

    const struct { unsigned offset; uint32_t value; } settings[] = {
        {0x14004, 2},          // CM3_BOOT_CONFIG
        {0x14614, 0x60001000}, // HFI_QTBL_ADDR
        {0x14610, 1},          // HFI_QTBL_INFO
        {0x24c44, 0x80a008a0}, // AHB_FENCE_RANGE_0
        {0x14608, 0x06050200}, // HFI_SFR_ADDR
        {0x14400, 0x60000000}, // PWR_COL_CP_MSG (one-page log)
        {0x1303c, 1},          // SYS_BUS_CONFIG
        {0x13000, 1},          // ICACHE_CONFIG
        {0x13004, 1},          // DCACHE_CONFIG
        {0x14300, 0x09c40400}, // PWR_COL_INTER_FRAME_CTRL
        {0x143a0, 0x00000f11}, // RPMH_CTRL
        {0x14404, 0},          // PWR_COL_CP_RESP
    };
    result.state = "reg";
    for (const auto &setting : settings) {
        result.offset = setting.offset;
        if (!cold() || !healthy()) return;
        write(gmu, setting.offset, setting.value);
        if (read(gmu, setting.offset) != setting.value) return;
    }
    result.offset = 0;
    result.state = "release";
    if (!cold() || !healthy()) return;
    write(gmu, reset, 0);
    const auto poll = [&](unsigned offset, uint32_t mask, uint32_t expected, uint32_t &last) {
        for (unsigned attempt = 0; attempt < 1000; ++attempt) {
            last = read(gmu, offset);
            if (!healthy() || read(gmu, reset) != 0) return false;
            if ((last & mask) == expected) return true;
            IODelay(100);
        }
        return false;
    };
    result.state = "fw";
    if (poll(fwInit, 0x1ff, 0x100, result.fwInit)) {
        result.state = "hfi";
        write(gmu, hfiInit, 1);
        if (poll(hfiStatus, 1, 1, result.hfiStatus)) {
            result.hfiVersion = read(gmu, hfiVersion);
            if (result.hfiVersion == 0x20000001 && healthy()) {
                result.reset = read(gmu, reset);
                if (!result.reset) {
                    result.state = "ready";
                    return;
                }
            }
        }
    }
    // Stop a failed first release, but retain the route and backing because
    // observing reset does not prove that bus transactions have drained.
    write(gmu, reset, 1);
    result.reset = read(gmu, reset);
}

} // namespace t970_gpu
#endif
