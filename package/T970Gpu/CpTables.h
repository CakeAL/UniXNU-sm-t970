// SPDX-License-Identifier: MIT
#pragma once
#include "GmuTables.h"
#include "T970A650Sqe.h"

namespace t970_gpu {

using CpTables = T970GpuTables<17, 3>;

static bool prepareCpTables(CpTables &tables, uint32_t id0, uint32_t id2, unsigned &sqeBytes) {
    if (!allocateGpuTables(tables)) return false;
    constexpr unsigned rw = ArmSmmu4KRead | ArmSmmu4KWrite;
    constexpr unsigned rx = ArmSmmu4KRead | ArmSmmu4KExecute;
    const uint64_t payload = tables.config.table_physical + CpTables::poolPages * CpTables::pageBytes;
    const ArmSmmu4KRange ranges[] = {
        {0x01000000, payload,            0x8000, rw, 0, 3}, // Ring.
        {0x01008000, payload + 0x8000,   0x8000, rx, 0, 3}, // SQE.
        {0x01010000, payload + 0x10000,  0x1000, rw, 0, 3}, // Readback.
    };
    static_assert(sizeof(ranges) == sizeof(tables.ranges));
    memcpy(tables.ranges, ranges, sizeof(ranges));
    if (!buildGpuTables(tables, id0, id2, 2)) return false;

    // The A650 SQE instruction image excludes the file's leading word.
    constexpr unsigned header = 4, bytes = sizeof(t970SqeFirmware) - header;
    static_assert(bytes == 31628);
    auto *target = reinterpret_cast<uint8_t *>(tables.tables) + (ranges[1].physical - tables.config.table_physical);
    tables.stage = "sqe";
    memcpy(target, t970SqeFirmware + header, bytes);
    if (memcmp(target, t970SqeFirmware + header, bytes)) return false;
    sqeBytes = bytes;
    tables.stage = "ok";
    return true;
}

}
