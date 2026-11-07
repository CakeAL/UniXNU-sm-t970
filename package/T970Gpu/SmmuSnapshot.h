// SPDX-License-Identifier: MIT
#pragma once
#include "A650GmuPower.h"
#include "../T970Touch/BusSnapshot.h"
#ifdef T970_GPU_GMU_TABLES
#include "ArmSmmu4KMmio.h"
#endif

namespace t970_gpu {

constexpr unsigned cbBarChanged = 1u << 3;
constexpr unsigned cbBarMode = 14;
constexpr unsigned cbBarReleaseMode = 15;
constexpr unsigned cbTtbrMode = 16;
constexpr uint32_t cbBarStage1 = 0x1f300;
// Arm IHI 0062D.c: FSR[10:9] describes the translation table format.
constexpr uint32_t cbFsrFormatMask = 0x600;
constexpr uint32_t cbFsrAarch64 = 0x400;

struct CbGuards {
    uint32_t id0 = 0, id1 = 0, gfsr = 0, fsr = 0, bar = 0, scr0 = 0, sctlr = 0;
    unsigned smrs = 0;

    unsigned flags() const {
        return (id0 != 0x4c017e06 || id1 != 0x20000005 ? 1u : 0u) |
               (gfsr ? 2u : 0u) | ((fsr & ~cbFsrFormatMask) ? 4u : 0u) |
               (bar ? cbBarChanged : 0u) |
               (scr0 & (1u << 3) ? 16u : 0u) | (sctlr & 1u ? 32u : 0u) |
               (smrs ? 64u : 0u);
    }
};

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
    CbGuards guard;
    unsigned restoreFlags = 0, restoreDiff = 0;
    bool restoreRead = false;
    const char *barState = "skip";
    uint32_t barActive = 0, barRestored = 0;
    bool barRestoreRead = false;
    unsigned restoreSamples = 0;
    const char *ttbrState = "skip";
    unsigned ttbrRead = 0, ttbrWrite = 0, ttbrRestore = 0;
};

constexpr unsigned cbOffsets[] = {
    0x1000, 0x1800, 0x8000, 0x8010, 0x8020, 0x8024, 0x8028, 0x802c,
    0x8030, 0x8034, 0x8038, 0x803c, 0x8058, 0x8060, 0x8064,
};

static bool branchRunning(uint32_t value) {
    return value != UINT32_MAX && A650GpuCfgAhbIsEnabled(value) && A650GpuClockIsOn(value);
}

static bool coldGmu(IOMemoryMap &gmu) {
    return t970_touch::read(gmu, 0x14000) == 1 && !t970_touch::read(gmu, 0x14070);
}

static uint32_t readSmmu32(IOMemoryMap &smmu, unsigned offset) {
    const auto address = smmu.getVirtualAddress() + offset;
    uint64_t value;
    // Keep a real W register distinct from the address for HYP emulation.
    __asm__ volatile("ldr %w0, [%1]\n\tuxtw %0, %w0"
                     : "=&r"(value) : "r"(address) : "memory");
    return static_cast<uint32_t>(value);
}

static void writeSmmu32(IOMemoryMap &smmu, unsigned offset, uint32_t value) {
    const auto address = smmu.getVirtualAddress() + offset;
    __asm__ volatile("str %w0, [%1]\n\tdsb sy" : "+r"(value) : "r"(address) : "memory");
}

static CbGuards readCbGuards(IOMemoryMap &smmu) {
    CbGuards result;
    result.id0 = readSmmu32(smmu, A650_SMMU_ID0);
    result.id1 = readSmmu32(smmu, A650_SMMU_ID1);
    if (result.id0 != 0x4c017e06 || result.id1 != 0x20000005) return result;
    result.gfsr = readSmmu32(smmu, A650_SMMU_GFSR);
    result.fsr = readSmmu32(smmu, 0x8058);
    result.bar = readSmmu32(smmu, 0x1000);
    result.scr0 = readSmmu32(smmu, A650_SMMU_SCR0);
    result.sctlr = readSmmu32(smmu, 0x8000);
    for (unsigned i = 0; i < 6; ++i) {
        if (readSmmu32(smmu, A650_SMMU_SMR(i))) result.smrs |= 1u << i;
    }
    return result;
}

static bool sameRoutes(IOMemoryMap &smmu, const uint32_t (&routes)[6]) {
    for (unsigned i = 0; i < 6; ++i) {
        if (readSmmu32(smmu, A650_SMMU_S2CR(i)) != routes[i]) return false;
    }
    return true;
}

static bool barViewIdle(IOMemoryMap &smmu, IOMemoryMap &gmu, const SmmuSnapshot &result,
                        const uint32_t (&routes)[6], const CbGuards &guards) {
    return !(guards.flags() & ~cbBarChanged) && guards.fsr == cbFsrAarch64 &&
        guards.scr0 == result.scr0 && readSmmu32(smmu, 0x1800) == 1 &&
        sameRoutes(smmu, routes) && coldGmu(gmu);
}

#ifdef T970_GPU_GMU_TABLES
static uint64_t readTtbrWords(IOMemoryMap &smmu, unsigned offset) {
    const uint64_t low = readSmmu32(smmu, offset);
    return low | (static_cast<uint64_t>(readSmmu32(smmu, offset + 4)) << 32);
}

static bool pulseTtbr(IOMemoryMap &smmu, IOMemoryMap &gmu, SmmuSnapshot &result,
                      const uint32_t (&routes)[6]) {
    ArmSmmu4KMmio mmio = {reinterpret_cast<volatile unsigned char *>(smmu.getVirtualAddress()), 0x10000};
    ArmSmmu4KIo io = {};
    result.ttbrState = "bind";
    if (ArmSmmu4KBindMmio(&mmio, &io)) return true;
    constexpr unsigned offsets[] = {0x8020, 0x8028};
    constexpr uint64_t asidBit = UINT64_C(1) << 48;
    uint64_t saved[2] = {};
    result.ttbrState = "width";
    for (unsigned i = 0; i < 2; ++i) {
        const auto offset = offsets[i];
        saved[i] = readTtbrWords(smmu, offset);
        uint64_t wide = 0;
        if (!io.read64(io.cookie, offset, &wide) && wide != UINT64_MAX &&
            wide == saved[i] && readTtbrWords(smmu, offset) == saved[i]) result.ttbrRead |= 1u << i;
    }
    if (result.ttbrRead != 3) return true;
    result.ttbrState = "hold";
    for (unsigned i = 0; i < 2; ++i) {
        const auto offset = offsets[i];
        const auto before = readCbGuards(smmu);
        if (before.bar != cbBarStage1 || !barViewIdle(smmu, gmu, result, routes, before) ||
            readTtbrWords(smmu, offsets[0]) != saved[0] ||
            readTtbrWords(smmu, offsets[1]) != saved[1]) return false;
        // Toggle an ASID bit in the high word so an emulated low-word-only
        // access cannot pass. The table base stays intact and M stays clear.
        const uint64_t requested = saved[i] ^ asidBit;
        if (io.write64(io.cookie, offset, requested) || io.barrier(io.cookie)) return false;
        const auto active = readCbGuards(smmu);
        if (active.bar != cbBarStage1 || !barViewIdle(smmu, gmu, result, routes, active)) return false;
        uint64_t wide = 0;
        if (!io.read64(io.cookie, offset, &wide) && wide == requested &&
            readTtbrWords(smmu, offset) == requested) result.ttbrWrite |= 1u << i;
        if (io.write64(io.cookie, offset, saved[i]) || io.barrier(io.cookie) ||
            io.read64(io.cookie, offset, &wide) || wide != saved[i] ||
            readTtbrWords(smmu, offsets[0]) != saved[0] ||
            readTtbrWords(smmu, offsets[1]) != saved[1]) return false;
        result.ttbrRestore |= 1u << i;
    }
    result.ttbrState = result.ttbrWrite == 3 ? "ok" : "width";
    return true;
}
#endif

static bool pulseCbBar(IOMemoryMap &smmu, IOMemoryMap &gmu, SmmuSnapshot &result,
                       const uint32_t (&routes)[6], [[maybe_unused]] unsigned power) {
    result.barState = "pre";
    if (result.guard.bar || !barViewIdle(smmu, gmu, result, routes, result.guard))
        return false;
    // lmi mode 27 uses this stage-1/stage-2-bypass value with CM3 in reset.
    // Leave SCTLR.M and stream routing untouched.
    writeSmmu32(smmu, 0x1000, cbBarStage1);
    const CbGuards active = readCbGuards(smmu);
    result.barActive = active.bar;
    result.barState = "busy-hold";
    if ((active.bar && active.bar != cbBarStage1) ||
        !barViewIdle(smmu, gmu, result, routes, active)) return false;
#ifdef T970_GPU_GMU_TABLES
    if (power == cbTtbrMode && active.bar == cbBarStage1) {
        if (!pulseTtbr(smmu, gmu, result, routes)) return false;
        const auto after = readCbGuards(smmu);
        if (after.bar != cbBarStage1 || !barViewIdle(smmu, gmu, result, routes, after)) return false;
    }
#endif
    if (active.bar) writeSmmu32(smmu, 0x1000, 0);
    const CbGuards restored = readCbGuards(smmu);
    result.barRestored = restored.bar;
    result.barRestoreRead = true;
    if ((restored.bar && restored.bar != cbBarStage1) ||
        !barViewIdle(smmu, gmu, result, routes, restored)) return false;
    result.barState = restored.bar ? "latched" : active.bar ? "ok" : "filtered";
    return true;
}

static void pulseCbFormat(IOMemoryMap &smmu, SmmuSnapshot &result, IOMemoryMap *barGmu,
                          unsigned power) {
    result.format = "refuse";
    result.va64Before = readSmmu32(smmu, 0x1800);
    result.guard = readCbGuards(smmu);
    if (result.changed || result.va64Before || result.guard.flags() || result.guard.fsr) return;
    uint32_t routes[6] = {};
    if (barGmu) {
        for (unsigned i = 0; i < 6; ++i) {
            routes[i] = readSmmu32(smmu, A650_SMMU_S2CR(i));
            if (routes[i] == UINT32_MAX) return;
        }
        if (routes[0] != result.firstS2cr || !sameRoutes(smmu, routes) ||
            result.guard.scr0 != result.scr0 || !coldGmu(*barGmu)) return;
    }
    writeSmmu32(smmu, 0x1800, 1);
    result.va64Active = readSmmu32(smmu, 0x1800);
    result.guard = readCbGuards(smmu);
    result.holdParents = true;
    result.format = "busy-hold";
    // A CBAR view change alone grants no route. Permit restoring VA64 with
    // all six SMRs zero, translation disabled and fault state clear.
    if (result.va64Active == UINT32_MAX || result.guard.bar == UINT32_MAX ||
        (result.guard.flags() & ~cbBarChanged)) return;
    if (barGmu) {
        if (result.va64Active == 1 && result.guard.fsr == cbFsrAarch64 &&
            !pulseCbBar(smmu, *barGmu, result, routes, power) && strcmp(result.barState, "pre")) return;
        const CbGuards beforeRestore = readCbGuards(smmu);
        if ((beforeRestore.flags() & ~cbBarChanged) || beforeRestore.bar == UINT32_MAX ||
            beforeRestore.scr0 != result.scr0 || !sameRoutes(smmu, routes) || !coldGmu(*barGmu)) return;
    }
    writeSmmu32(smmu, 0x1800, result.va64Before);
    result.va64After = readSmmu32(smmu, 0x1800);
    result.restoreRead = true;
    result.format = "restore-hold";
    // A stage-1 selector can persist without an installed root or a route.
    // Accept precisely the observed selector in the dedicated release probe.
    const bool allowLatched = power >= cbBarReleaseMode;
    const bool latched = result.barRestoreRead && result.barRestored == cbBarStage1;
    const bool releaseLatched = allowLatched && latched && result.barActive == cbBarStage1;
    const uint32_t expectedBar = releaseLatched ? cbBarStage1 : result.cb[0];
    const unsigned expectedFlags = releaseLatched ? cbBarChanged : 0;
    const unsigned samples = allowLatched ? 2 : 1;
    for (unsigned pass = 0; pass < samples; ++pass) {
        if (pass) IODelay(1000);
        const CbGuards restored = readCbGuards(smmu);
        result.restoreFlags = restored.flags();
        if (readSmmu32(smmu, A650_SMMU_S2CR(0)) != result.firstS2cr) result.restoreFlags |= 1u << 7;
        if (barGmu && (!sameRoutes(smmu, routes) || !coldGmu(*barGmu) ||
                       restored.scr0 != result.scr0 ||
                       readSmmu32(smmu, A650_SMMU_ID2) != result.id2)) result.restoreFlags |= 1u << 8;
        if (result.va64After != result.va64Before || result.restoreFlags != expectedFlags ||
            (releaseLatched && restored.bar != expectedBar)) return;
        for (unsigned i = 0; i < 15; ++i) {
            const uint32_t expected = i == 0 ? expectedBar : result.cb[i];
            if (readSmmu32(smmu, cbOffsets[i]) != expected) result.restoreDiff |= 1u << i;
        }
        if (result.restoreDiff) return;
        ++result.restoreSamples;
    }
    if (latched && !releaseLatched) return;
    result.holdParents = false;
    result.format = releaseLatched ? "inert" :
        result.va64Active == 1 && result.guard.fsr == cbFsrAarch64 ? "ok" : "readback";
}

static void sampleSmmu(SmmuSnapshot &result, IOMemoryMap &gmu, unsigned power) {
    using namespace t970_touch;
    const bool format = power >= 10;
    auto *barGmu = power >= cbBarMode ? &gmu : nullptr;
    auto smmu = mapMmio(A650_GPU_BASE_SMMU_GR0, 0x10000, format ? 0 : kIOMapReadOnly);
    if (!smmu || !smmu->getVirtualAddress()) {
        result.state = "map-fail";
        return;
    }
    result.id0 = readSmmu32(*smmu, A650_SMMU_ID0);
    result.id1 = readSmmu32(*smmu, A650_SMMU_ID1);
    result.id2 = readSmmu32(*smmu, A650_SMMU_ID2);
    result.scr0 = readSmmu32(*smmu, A650_SMMU_SCR0);
    result.gfsr = readSmmu32(*smmu, A650_SMMU_GFSR);
    // lmi mode 8 and mode 27: six SMRs, five 4 KiB context banks
    // beginning at +0x8000, no extended stream IDs.
    if (result.id0 != 0x4c017e06 || result.id1 != 0x20000005 || (barGmu && result.id2 != 0x5511)) {
        result.state = "layout";
        return;
    }
    const unsigned streams = A650GpuSmmuNumSmrs(result.id0);
    result.firstS2cr = readSmmu32(*smmu, A650_SMMU_S2CR(0));
    for (unsigned i = 0; i < streams; ++i) {
        const uint32_t smr = readSmmu32(*smmu, A650_SMMU_SMR(i));
        result.valid += smr >> 31;
        result.nonzero += smr != 0;
    }
    if (result.nonzero || result.gfsr || (result.scr0 & (1u << 3))) {
        result.state = "in-use";
        return;
    }
    for (unsigned i = 0; i < 15; ++i) result.cb[i] = readSmmu32(*smmu, cbOffsets[i]);
    for (unsigned pass = 0; pass < 2; ++pass) {
        IODelay(1000);
        for (unsigned i = 0; i < 15; ++i) result.changed += result.cb[i] != readSmmu32(*smmu, cbOffsets[i]);
    }
    result.contextRead = true;
    result.state = "read";
    if (format) pulseCbFormat(*smmu, result, barGmu, power);
}

// The T970 stock SMMU DT names MEMNOC, SNOC DVM and GPUCC AHB.
// The caller already holds GPUCC AHB, CX and the GMU source.
static SmmuSnapshot pulseSmmuBus(IOMemoryMap &gcc, IOMemoryMap &gmu, unsigned power) {
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
    if (result.ready == 3) sampleSmmu(result, gmu, power);
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
