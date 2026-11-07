// SPDX-License-Identifier: MIT
#pragma once
#include "A650GmuPower.h"
#include "../T970Touch/BusSnapshot.h"

namespace t970_gpu {

struct SmmuSnapshot {
    const char *state = "skip";
    uint32_t id0 = 0, id1 = 0, id2 = 0, scr0 = 0, gfsr = 0;
    unsigned valid = 0, nonzero = 0, changed = 0;
    uint32_t firstS2cr = 0;
    uint32_t cb[15] = {};
    bool contextRead = false;
    uint32_t clock[2] = {};
    unsigned ready = 0, restored = 0;
    bool holdParents = false;
    const char *format = "skip";
    uint32_t va64Before = 0, va64Active = 0, va64After = 0;
};

constexpr unsigned cbOffsets[] = {
    0x1000, 0x1800, 0x8000, 0x8010, 0x8020, 0x8024, 0x8028, 0x802c,
    0x8030, 0x8034, 0x8038, 0x803c, 0x8058, 0x8060, 0x8064,
};

static bool branchRunning(uint32_t value) {
    return value != UINT32_MAX && A650GpuCfgAhbIsEnabled(value) && A650GpuClockIsOn(value);
}

static uint32_t readCbFormat(IOMemoryMap &smmu) {
    const auto address = smmu.getVirtualAddress() + 0x1800;
    uint64_t value;
    // Keep a real W register distinct from the address for HYP emulation.
    __asm__ volatile("ldr %w0, [%1]\n\tuxtw %0, %w0"
                     : "=&r"(value) : "r"(address) : "memory");
    return static_cast<uint32_t>(value);
}

static void writeCbFormat(IOMemoryMap &smmu, uint32_t value) {
    const auto address = smmu.getVirtualAddress() + 0x1800;
    __asm__ volatile("str %w0, [%1]\n\tdsb sy" : "+r"(value) : "r"(address) : "memory");
}

static bool cbIdle(IOMemoryMap &smmu) {
    using namespace t970_touch;
    if (read(smmu, A650_SMMU_ID0) != 0x4c017e06 || read(smmu, A650_SMMU_ID1) != 0x20000005 ||
        read(smmu, A650_SMMU_GFSR) || read(smmu, 0x8058) || read(smmu, 0x1000) ||
        (read(smmu, A650_SMMU_SCR0) & (1u << 3)) || (read(smmu, 0x8000) & 1u)) return false;
    for (unsigned i = 0; i < 6; ++i) {
        if (read(smmu, A650_SMMU_SMR(i))) return false;
    }
    return true;
}

static void pulseCbFormat(IOMemoryMap &smmu, SmmuSnapshot &result) {
    using namespace t970_touch;
    result.format = "refuse";
    result.va64Before = readCbFormat(smmu);
    if (result.changed || result.va64Before || !cbIdle(smmu)) return;
    writeCbFormat(smmu, 1);
    result.va64Active = readCbFormat(smmu);
    result.holdParents = true;
    result.format = "busy-hold";
    if (result.va64Active == UINT32_MAX || !cbIdle(smmu)) return;
    writeCbFormat(smmu, result.va64Before);
    result.va64After = readCbFormat(smmu);
    result.format = "restore-hold";
    if (result.va64After != result.va64Before || !cbIdle(smmu) ||
        read(smmu, A650_SMMU_S2CR(0)) != result.firstS2cr) return;
    for (unsigned i = 0; i < 15; ++i) {
        if (read(smmu, cbOffsets[i]) != result.cb[i]) return;
    }
    result.holdParents = false;
    result.format = result.va64Active == 1 ? "ok" : "readback";
}

static void sampleSmmu(SmmuSnapshot &result, bool format) {
    using namespace t970_touch;
    auto smmu = mapMmio(A650_GPU_BASE_SMMU_GR0, 0x10000, format ? 0 : kIOMapReadOnly);
    if (!smmu || !smmu->getVirtualAddress()) {
        result.state = "map-fail";
        return;
    }
    result.id0 = read(*smmu, A650_SMMU_ID0);
    result.id1 = read(*smmu, A650_SMMU_ID1);
    result.id2 = read(*smmu, A650_SMMU_ID2);
    result.scr0 = read(*smmu, A650_SMMU_SCR0);
    result.gfsr = read(*smmu, A650_SMMU_GFSR);
    // lmi mode 8 and mode 27: six SMRs, five 4 KiB context banks
    // beginning at +0x8000, no extended stream IDs.
    if (result.id0 != 0x4c017e06 || result.id1 != 0x20000005) {
        result.state = "layout";
        return;
    }
    const unsigned streams = A650GpuSmmuNumSmrs(result.id0);
    result.firstS2cr = read(*smmu, A650_SMMU_S2CR(0));
    for (unsigned i = 0; i < streams; ++i) {
        const uint32_t smr = read(*smmu, A650_SMMU_SMR(i));
        result.valid += smr >> 31;
        result.nonzero += smr != 0;
    }
    if (result.nonzero || result.gfsr || (result.scr0 & (1u << 3))) {
        result.state = "in-use";
        return;
    }
    for (unsigned i = 0; i < 15; ++i) result.cb[i] = read(*smmu, cbOffsets[i]);
    for (unsigned pass = 0; pass < 2; ++pass) {
        IODelay(1000);
        for (unsigned i = 0; i < 15; ++i) result.changed += result.cb[i] != read(*smmu, cbOffsets[i]);
    }
    result.contextRead = true;
    result.state = "read";
    if (format) pulseCbFormat(*smmu, result);
}

// The T970 stock SMMU DT names MEMNOC, SNOC DVM and GPUCC AHB.
// The caller already holds GPUCC AHB, CX and the GMU source.
static SmmuSnapshot pulseSmmuBus(IOMemoryMap &gcc, bool format) {
    using namespace t970_touch;
    constexpr unsigned gpu = A650_GPU_BASE_GCC_GPU - 0x100000;
    constexpr unsigned clocks[] = {gpu + A650_GCC_GPU_MEMNOC_GFX, gpu + A650_GCC_GPU_SNOC_DVM_GFX};
    constexpr uint32_t enable = A650_CBCR_ENABLE;
    SmmuSnapshot result;
    result.state = "clock";
    uint32_t before[2] = {};
    unsigned visited = 0;
    for (unsigned i = 0; i < 2; ++i) {
        before[i] = read(gcc, clocks[i]);
        if (before[i] == UINT32_MAX) break;
        visited |= 1u << i;
        if (!branchRunning(before[i])) write(gcc, clocks[i], before[i] | enable);
        uint32_t value = read(gcc, clocks[i]);
        for (unsigned us = 0; us < 200 && value != UINT32_MAX && !branchRunning(value); ++us) {
            IODelay(1);
            value = read(gcc, clocks[i]);
        }
        result.clock[i] = value;
        if (!branchRunning(value)) break;
        result.ready |= 1u << i;
    }
    if (result.ready == 3) sampleSmmu(result, format);
    if (result.holdParents) return result;
    for (unsigned i = 2; i-- > 0;) {
        const unsigned bit = 1u << i;
        if (!(visited & bit)) continue;
        uint32_t value = read(gcc, clocks[i]);
        if (value == UINT32_MAX) break;
        if (!(before[i] & enable) && (value & enable)) {
            write(gcc, clocks[i], value & ~enable);
            IODelay(10);
            value = read(gcc, clocks[i]);
        }
        if (value == UINT32_MAX || ((value ^ before[i]) & enable)) break;
        result.restored |= bit;
    }
    result.holdParents = result.restored != visited;
    if (result.holdParents) result.state = "bus-hold";
    return result;
}

} // namespace t970_gpu
