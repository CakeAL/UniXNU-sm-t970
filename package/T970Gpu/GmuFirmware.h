// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>

namespace t970_gpu {
struct GmuFirmwareProbe {
    const char *state = "skip";
    unsigned tcmBytes = 0, ramBytes = 0, mismatches = 0, restoreMismatches = 0;
    uint32_t version = 0;
};
}

#ifdef T970_GPU_GMU_FIRMWARE
#include "../T970Touch/BusSnapshot.h"
#include "A650GmuRegions.h"
#include "GmuTables.h"
#include "T970A650Firmware.h"

namespace t970_gpu {

static bool stageGmuFirmware(IOMemoryMap &gmu, GmuTables &tables, GmuFirmwareProbe &result) {
    using t970_touch::read;
    using t970_touch::write;
    constexpr uint32_t tcmSize = 0x4000, dtcmBase = 0x10004000;
    constexpr unsigned itcmWindow = 0x3000, dtcmWindow = 0x7000;
    constexpr unsigned retention = 0x14730, dtcmVersion = 0xafe0;
    constexpr unsigned snapshotBytes = 18404, externalBytes = 22888;
    AdrenoFirmwareRegion regions[16];
    AdrenoFirmwareBlock blocks[16];
    size_t regionCount = 0, blockCount = 0;
    result.state = "plan";
    if (A650GmuBuildRegions(t970GmuFirmware, sizeof(t970GmuFirmware), regions, 16, &regionCount) ||
        AdrenoFirmwarePlanGmu(t970GmuFirmware, sizeof(t970GmuFirmware), regions, regionCount,
                             blocks, 16, &blockCount)) return true;

    struct Destination {
        uint8_t *ram;
        unsigned tcm;
    };
    Destination targets[16] = {};
    auto *bytes = reinterpret_cast<uint8_t *>(tables.tables);
    for (size_t i = 0; i < blockCount; ++i) {
        const auto &block = blocks[i];
        if (!block.bytes) continue;
        const uint64_t end = static_cast<uint64_t>(block.address) + block.bytes;
        if (end <= tcmSize) targets[i].tcm = itcmWindow + block.address;
        else if (block.address >= dtcmBase && end <= dtcmBase + tcmSize)
            targets[i].tcm = dtcmWindow + block.address - dtcmBase;
        if (targets[i].tcm) {
            result.tcmBytes += block.bytes;
            continue;
        }
        for (const auto &range : tables.ranges) {
            if (block.address >= range.iova && end <= range.iova + range.bytes) {
                targets[i].ram = bytes + (range.physical - tables.config.table_physical) +
                                 (block.address - range.iova);
                break;
            }
        }
        if (!targets[i].ram) return true;
        result.ramBytes += block.bytes;
    }
    if (result.tcmBytes != snapshotBytes || result.ramBytes != externalBytes) return true;

    for (size_t i = 0; i < blockCount; ++i) {
        if (!targets[i].ram) continue;
        const auto *payload = t970GmuFirmware + blocks[i].payload_offset;
        memcpy(targets[i].ram, payload, blocks[i].bytes);
        result.mismatches += memcmp(targets[i].ram, payload, blocks[i].bytes) != 0;
    }

    result.state = "alloc";
    auto *saved = static_cast<uint32_t *>(IOMallocData(snapshotBytes));
    if (!saved) return true;
    const auto stillReset = [&]() { return read(gmu, 0x14000) == 1 && read(gmu, 0x14070) == 0; };
    const auto visitTcm = [&](auto visit) {
        unsigned word = 0;
        for (size_t i = 0; i < blockCount; ++i) {
            if (!targets[i].tcm) continue;
            if (!stillReset()) return false;
            const auto *payload = t970GmuFirmware + blocks[i].payload_offset;
            for (unsigned offset = 0; offset < blocks[i].bytes; offset += 4, ++word)
                visit(targets[i].tcm + offset, word, payload + offset);
        }
        return stillReset();
    };
    const bool safe = [&]() {
        result.state = "cold";
        if (!stillReset()) return false;
        if (read(gmu, 0x14600) || read(gmu, 0x14618)) return true;
        const uint32_t original = read(gmu, retention);
        if (original > 1) return true;
        if (!visitTcm([&](unsigned at, unsigned i, const uint8_t *) { saved[i] = read(gmu, at); }))
            return false;
        bool stable = true;
        if (!visitTcm([&](unsigned at, unsigned i, const uint8_t *) { stable &= read(gmu, at) == saved[i]; }))
            return false;
        if (!stable) return true;
        result.state = "retention";
        if (!original) write(gmu, retention, 1);
        if (read(gmu, retention) != 1) return stillReset() && read(gmu, retention) == original;

        result.state = "tcm-hold";
        const auto firmwareWord = [](const uint8_t *data) {
            uint32_t word;
            memcpy(&word, data, sizeof(word));
            return word;
        };
        if (!visitTcm([&](unsigned at, unsigned, const uint8_t *data) { write(gmu, at, firmwareWord(data)); }) ||
            !visitTcm([&](unsigned at, unsigned, const uint8_t *data) {
                result.mismatches += read(gmu, at) != firmwareWord(data);
            })) return false;
        result.version = read(gmu, dtcmVersion);
        if (!visitTcm([&](unsigned at, unsigned i, const uint8_t *) { write(gmu, at, saved[i]); }) ||
            !visitTcm([&](unsigned at, unsigned i, const uint8_t *) {
                result.restoreMismatches += read(gmu, at) != saved[i];
            })) return false;
        if (!original) write(gmu, retention, original);
        if (!stillReset() || read(gmu, retention) != original || result.restoreMismatches) return false;
        result.state = !result.mismatches && result.version == 0x20010008 ? "ok" : "readback";
        return true;
    }();
    IOFreeData(saved, snapshotBytes);
    return safe;
}

} // namespace t970_gpu
#endif
