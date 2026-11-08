// SPDX-License-Identifier: MIT
#pragma once
#include "GmuHfiPerf.h"

namespace t970_gpu {

struct GmuHfiCoreProbe {
    GmuHfiProbe bandwidth, start;
    uint32_t bcm[4] = {};
};

}

#ifdef T970_GPU_GMU_FIRMWARE
namespace t970_gpu {

static bool makeGmuHfiBandwidth(const volatile uint8_t *db, GmuHfiCoreProbe &result,
                                uint32_t (&packet)[160]) {
    constexpr unsigned bcmSlave = 5;
    const char *const names[] = {"MC0\0\0\0\0", "SH0\0\0\0\0", "ACV\0\0\0\0", "CN0\0\0\0\0"};
    for (unsigned i = 0; i < 4; ++i) {
        const auto resource = findCmdDbResource(db, A650_CMD_DB_BYTES, bcmSlave, names[i]);
        if (!resource.entry) return false;
        const uint32_t address = arcLe32(resource.entry + 16);
        if ((address & 3) || ((address >> 16) & 7) != bcmSlave) return false;
        for (unsigned j = 0; j < i; ++j) if (result.bcm[j] == address) return false;
        result.bcm[i] = address;
    }

    // Legacy A650 BW_TBL: 6 CNOC addresses and 2 rows, then 8 DDR
    // addresses and 16 rows. Expose only the off DDR level for core start.
    constexpr unsigned cnocAddress = 6, cnocData = cnocAddress + 6;
    constexpr unsigned ddrAddress = cnocData + 2 * 6, ddrData = ddrAddress + 8;
    bzero(packet, sizeof(packet));
    packet[0] = 0x0030a003;
    packet[1] = 1; // DDR level count.
    packet[2] = 1; // CNOC command count.
    packet[3] = 3; // DDR command count.
    packet[4] = packet[5] = 1; // Wait masks.
    packet[cnocAddress] = result.bcm[3];
    packet[cnocData] = 0x40000000;
    packet[cnocData + 6] = 0x60000001;
    for (unsigned i = 0; i < 3; ++i) {
        packet[ddrAddress + i] = result.bcm[i];
        packet[ddrData + i] = 0x40000000;
    }
    return true;
}

template <typename Healthy>
static void probeGmuHfiCore(IOMemoryMap &gmu, GmuTables &tables, GmuHfiCoreProbe &result, Healthy healthy) {
    result.bandwidth.state = "bcm-map";
    auto db = t970_touch::mapMmio(A650_CMD_DB_BASE, A650_CMD_DB_BYTES);
    if (!db || !db->getVirtualAddress()) return;
    result.bandwidth.state = "bcm";
    uint32_t packet[160];
    const auto *bytes = reinterpret_cast<const volatile uint8_t *>(db->getVirtualAddress());
    if (!makeGmuHfiBandwidth(bytes, result, packet)) return;
    exchangeGmuHfi(gmu, tables, {packet, 160, 64, 8}, result.bandwidth, healthy);
    if (strcmp(result.bandwidth.state, "ok")) return;
    constexpr uint32_t request[] = {0x0040020e, 0};
    exchangeGmuHfi(gmu, tables, {request, 2, 224, 12}, result.start, healthy);
}

}
#endif
