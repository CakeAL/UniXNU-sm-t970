// SPDX-License-Identifier: MIT
#pragma once
#include "GmuHfiVersion.h"

#ifdef T970_GPU_GMU_FIRMWARE
#include "A650GmuPower.h"
#include "ArcResources.h"

namespace t970_gpu {

static bool encodeGmuArcVote(const ArcResource &rail, const ArcResource &mx, unsigned level, uint32_t &vote) {
    unsigned primary = 0, secondary = 0;
    while (primary < rail.levels && rail.level[primary] < level) ++primary;
    if (primary == rail.levels || !mx.levels) return false;
    // Legacy KGSL pairs MX with the selected primary corner, clamping to
    // the highest MX selector when the primary corner exceeds it.
    while (secondary + 1 < mx.levels && mx.level[secondary] < rail.level[primary]) ++secondary;
    vote = (uint32_t(rail.level[primary]) << 16) | (secondary << 8) | primary;
    return true;
}

static bool makeGmuHfiPerf(const ArcResource &gx, const ArcResource &cx, const ArcResource &mx,
                           uint32_t (&packet)[59]) {
    // T970 stock gpu-opp-table_v2 and active KGSL frequencies, plus off.
    constexpr uint32_t khz[] = {0, 305000, 400000, 441600, 490000, 525000, 587000, 670000};
    constexpr unsigned levels[] = {0, 64, 128, 144, 192, 224, 256, 320};
    constexpr unsigned cxStart = 3 + 16 * 3;
    bzero(packet, sizeof(packet));
    packet[0] = 0x00203b04; // Sequence 2, 59 words, PERF_TBL (ID 4).
    packet[1] = 8;
    packet[2] = 2;
    for (unsigned i = 0; i < 8; ++i) {
        auto *entry = packet + 3 + i * 3;
        if (!encodeGmuArcVote(gx, mx, levels[i], entry[0])) return false;
        entry[1] = UINT32_MAX; // Legacy probe ACD sentinel.
        entry[2] = khz[i];
    }
    if (!encodeGmuArcVote(cx, mx, 0, packet[cxStart]) ||
        !encodeGmuArcVote(cx, mx, 48, packet[cxStart + 2])) return false;
    packet[cxStart + 3] = 200000; // Qualified SM8250 GMU clock, in kHz.
    return true;
}

template <typename Healthy>
static void probeGmuHfiPerf(IOMemoryMap &gmu, GmuTables &tables, GmuHfiProbe &result, Healthy healthy) {
    result.state = "arc-map";
    auto db = t970_touch::mapMmio(A650_CMD_DB_BASE, A650_CMD_DB_BYTES);
    if (!db || !db->getVirtualAddress()) return;
    result.state = "arc";
    const auto *bytes = reinterpret_cast<const volatile uint8_t *>(db->getVirtualAddress());
    ArcResource gx, cx, mx;
    if (!parseArc(bytes, A650_CMD_DB_BYTES, "gfx.lvl", gx) ||
        !parseArc(bytes, A650_CMD_DB_BYTES, "cx.lvl\0", cx) ||
        !parseArc(bytes, A650_CMD_DB_BYTES, "mx.lvl\0", mx) ||
        gx.address == cx.address || gx.address == mx.address || cx.address == mx.address) return;
    uint32_t packet[59];
    if (!makeGmuHfiPerf(gx, cx, mx, packet)) return;
    exchangeGmuHfi(gmu, tables, {packet, 59, 4, 4}, result, healthy);
}

}
#endif
