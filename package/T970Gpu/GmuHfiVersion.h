// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>

namespace t970_gpu {

struct GmuHfiVersionProbe {
    const char *state = "skip";
    uint32_t cmdRead = 0, cmdWrite = 0, msgRead = 0, msgWrite = 0, irq = 0, irqAfter = 0;
    uint32_t reply[4] = {};
};

}

#ifdef T970_GPU_GMU_FIRMWARE
#include "GmuFirmware.h"

namespace t970_gpu {

constexpr uint32_t gmuHfiIova = 0x60001000;
constexpr unsigned gmuHfiBytes = 5 * 4096;

static uint32_t *gmuHfiMemory(GmuTables &tables) {
    for (const auto &range : tables.ranges) {
        if (range.iova == gmuHfiIova && range.bytes == gmuHfiBytes)
            return reinterpret_cast<uint32_t *>(reinterpret_cast<uint8_t *>(tables.tables) +
                (range.physical - tables.config.table_physical));
    }
    return nullptr;
}

static void syncGmuHfi(uintptr_t address, unsigned bytes, unsigned line, bool publish) {
    __asm__ volatile("dsb sy" ::: "memory");
    for (uintptr_t at = address & ~(static_cast<uintptr_t>(line) - 1); at < address + bytes; at += line) {
        if (publish) __asm__ volatile("dc cvac, %0" :: "r"(at) : "memory");
        else __asm__ volatile("dc ivac, %0" :: "r"(at) : "memory");
    }
    __asm__ volatile("dsb sy" ::: "memory");
}

// One legacy A650 FW_VER exchange using the four-queue layout and wire
// format qualified by lmi mode 29. The caller holds the route through reboot.
template <typename Healthy>
static void probeGmuHfiVersion(IOMemoryMap &gmu, GmuTables &tables, GmuHfiVersionProbe &result, Healthy healthy) {
    using t970_touch::read;
    using t970_touch::write;
    constexpr unsigned irqClear = 0x14644, irqInfo = 0x14648, doorbell = 0x14650;
    constexpr unsigned command = 256, response = command + 4096;
    constexpr unsigned cmdRead = 16, cmdWrite = 17, msgRead = 28, msgWrite = 29;
    constexpr uint32_t request[] = {0x00100201, 0x20000000, 0xfafafafa, 0xfafafafa};
    constexpr unsigned words = sizeof(request) / sizeof(request[0]);
    result.state = "health";
    if (!healthy()) return;
    result.state = "versions";
    if (read(gmu, 0xafe0) != 0x20010008 || read(gmu, 0xaff0) != 0x20000001) return;

    result.state = "layout";
    volatile uint32_t *shared = gmuHfiMemory(tables);
    if (!shared) return;
    const auto base = reinterpret_cast<uintptr_t>(shared);
    uint64_t ctr;
    __asm__ volatile("mrs %0, ctr_el0" : "=r"(ctr));
    const unsigned line = 4u << ((ctr >> 16) & 15);
    if ((line != 64 && line != 128) || (base & (line - 1))) return;
    syncGmuHfi(base, 128, line, false);
    const uint32_t header[] = {0, 54, 6, 12, 4, 4, 1, gmuHfiIova + command, 0xa00, 1024};
    for (unsigned i = 0; i < sizeof(header) / sizeof(header[0]); ++i)
        if (shared[i] != header[i]) return;
    if (shared[18] != 1 || shared[19] != gmuHfiIova + response ||
        shared[20] != 0xa01 || shared[21] != 1024) return;

    const auto sample = [&] {
        result.irq = read(gmu, irqInfo);
        syncGmuHfi(base, 128, line, false);
        result.cmdRead = shared[cmdRead];
        result.cmdWrite = shared[cmdWrite];
        result.msgRead = shared[msgRead];
        result.msgWrite = shared[msgWrite];
    };
    result.state = "busy";
    sample();
    if (result.irq || result.cmdRead || result.cmdWrite || result.msgRead || result.msgWrite) return;

    // Publish payload first and its producer cursor last. CMD and MSG
    // indices can share a line, so clean that line only before the request
    // and once after firmware has consumed it and posted the complete reply.
    for (unsigned i = 0; i < words; ++i) shared[command / 4 + i] = request[i];
    syncGmuHfi(base + command, sizeof(request), line, true);
    shared[cmdWrite] = words;
    syncGmuHfi(base + cmdWrite * 4, 4, line, true);
    write(gmu, doorbell, 1);

    result.state = "wait";
    for (unsigned i = 0; i < 1000; ++i) {
        sample();
        if (!healthy()) {
            result.state = "health";
            return;
        }
        if (result.irq & ~1u || result.cmdRead > words || result.cmdWrite != words ||
            result.msgRead || result.msgWrite > words) {
            result.state = "cursor";
            return;
        }
        if (result.cmdRead == words && result.msgWrite == words && result.irq == 1) {
            result.state = "reply";
            syncGmuHfi(base + response, sizeof(result.reply), line, false);
            for (unsigned j = 0; j < words; ++j) result.reply[j] = shared[response / 4 + j];
            if ((result.reply[0] & 0xfff00u) != 0x10400 || result.reply[1] != request[0] ||
                result.reply[2] || result.reply[3] != 0x20010008) return;
            shared[msgRead] = words;
            syncGmuHfi(base + msgRead * 4, 4, line, true);
            write(gmu, irqClear, 1);
            result.state = "irq";
            result.irqAfter = read(gmu, irqInfo);
            if (!result.irqAfter) result.state = "ok";
            return;
        }
        IODelay(100);
    }
}

}
#endif
