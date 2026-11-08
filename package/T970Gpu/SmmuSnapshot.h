// SPDX-License-Identifier: MIT
#pragma once
#include "A650GmuPower.h"
#include "../T970Touch/BusSnapshot.h"
#ifdef T970_GPU_GMU_TABLES
#include "ArmSmmu4KMmio.h"
#include "GmuTables.h"
#endif
#ifdef T970_GPU_SQE_FIRMWARE
#include "CpTables.h"
#endif
#include "GmuFirmware.h"
#include "GmuBoot.h"

class IOBufferMemoryDescriptor;

namespace t970_gpu {

constexpr unsigned cbBarChanged = 1u << 3;
constexpr unsigned cbTranslationEnabled = 1u << 5;
constexpr unsigned cbBarMode = 14;
constexpr unsigned cbBarReleaseMode = 15;
constexpr unsigned cbTtbrMode = 16;
constexpr unsigned cbRootMode = 17;
constexpr unsigned cbActivateMode = 18;
constexpr unsigned cbSid5Mode = 19;
constexpr unsigned cbFirmwareMode = 20;
constexpr unsigned cbBootMode = 22;
constexpr unsigned cbBootRepairMode = 23;
constexpr unsigned cbBootScratchExecMode = 24;
constexpr unsigned cbBootDefaultInstMode = 25;
constexpr unsigned cbBootHfiVersionMode = 26;
constexpr unsigned cbBootHfiPerfMode = 27;
constexpr unsigned cbBootHfiCoreMode = 28;
constexpr unsigned cbBootHfiGxMode = 29;
constexpr unsigned cbBootCpReadMode = 30;
constexpr unsigned cbBootCb1FormatMode = 31;
constexpr unsigned cbBootCb1RootMode = 32;
constexpr unsigned cbBootCb1ActivateMode = 33;
static constexpr bool isBootMode(unsigned power) {
    return power >= cbBootMode && power <= cbBootCb1ActivateMode;
}
constexpr unsigned ddrAxiIndex = 2;
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
               (scr0 & (1u << 3) ? 16u : 0u) | (sctlr & 1u ? cbTranslationEnabled : 0u) |
               (smrs ? 64u : 0u);
    }
};

struct GpuCpSnapshot {
    const char *state = "skip";
    uint32_t rbbm = 0, irq = 0, rbCntl = 0, rp = 0, wp = 0, sqe = 0, fault = 0, cpIrq = 0;
    uint64_t rbBase = 0;
    uint32_t cbFormat = 0, cbBar = 0, cbCtl = 0, cbFsr = 0, cbTcr = 0, slot = 0;
    uint64_t cbTtbr0 = 0;
    const char *formatState = "skip";
    uint32_t vaDuring = 0, vaAfter = 0, barDuring = 0, fsrDuring = 0, ctlDuring = 0;
    unsigned formatDiff = 0;
    const char *rootState = "skip";
    unsigned sqeBytes = 0, rootFields = 0, leaves = 0;
    uint64_t liveRoot = 0;
    bool rootHeld = false;
    const char *activation = "skip";
    unsigned tlbSynced = 0, tlbReads = 0;
    uint32_t ctlOn = 0, ctlOff = 0, fsrOn = 0, fsrOff = 0;
};

struct SmmuSnapshot {
    const char *state = "skip";
    uint32_t id0 = 0, id1 = 0, id2 = 0, scr0 = 0, gfsr = 0;
    unsigned valid = 0, nonzero = 0, changed = 0;
    uint32_t firstS2cr = 0;
    uint32_t cb[15] = {};
    bool contextRead = false;
    uint32_t clock[3] = {};
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
    const char *rootState = "skip";
    unsigned rootInstalled = 0, rootRestored = 0, rootLeaves = 0;
    bool rootHeld = false;
    const char *activation = "skip";
    unsigned tlbSynced = 0, tlbReads = 0;
    uint32_t ctlOn = 0, ctlOff = 0;
    const char *sid5State = "skip";
    uint32_t sid5Smr = 0, sid5S2cr = 0, sid5SmrAfter = 0, sid5S2crAfter = 0;
    GmuFirmwareProbe firmware;
    GmuBootProbe boot;
    GpuCpSnapshot cp;
    uint32_t ddrAxiBefore = 0, ddrAxiAfter = 0;
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

static bool barViewMatches(IOMemoryMap &smmu, const SmmuSnapshot &result,
                           const uint32_t (&routes)[6], const CbGuards &guards, bool translation) {
    const unsigned expected = translation ? cbTranslationEnabled : 0;
    return (guards.flags() & ~cbBarChanged) == expected && guards.fsr == cbFsrAarch64 &&
        guards.scr0 == result.scr0 && readSmmu32(smmu, 0x1800) == 1 &&
        sameRoutes(smmu, routes);
}

static bool barViewIdle(IOMemoryMap &smmu, IOMemoryMap &gmu, const SmmuSnapshot &result,
                        const uint32_t (&routes)[6], const CbGuards &guards, bool translation = false) {
    return barViewMatches(smmu, result, routes, guards, translation) && coldGmu(gmu);
}

#ifdef T970_GPU_GMU_TABLES
static uint64_t readTtbrWords(IOMemoryMap &smmu, unsigned offset) {
    const uint64_t low = readSmmu32(smmu, offset);
    return low | (static_cast<uint64_t>(readSmmu32(smmu, offset + 4)) << 32);
}

static ArmSmmu4KIo contextTlbIo(IOMemoryMap &smmu) {
    return {
        &smmu, 0x10000,
        [](void *cookie, size_t offset, uint32_t *value) {
            *value = readSmmu32(*static_cast<IOMemoryMap *>(cookie), static_cast<unsigned>(offset));
            return 0;
        },
        nullptr,
        [](void *cookie, size_t offset, uint32_t value) {
            writeSmmu32(*static_cast<IOMemoryMap *>(cookie), static_cast<unsigned>(offset), value);
            return 0;
        },
        nullptr,
        [](void *) {
            __asm__ volatile("dsb sy" ::: "memory");
            return 0;
        },
    };
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

#ifdef T970_GPU_GMU_FIRMWARE
#ifdef T970_GPU_SQE_FIRMWARE
template <typename Live>
static void pulseCpContext(IOMemoryMap &smmu, GpuCpSnapshot &result,
                           const ArmSmmu4KContextImage &image, Live live) {
    constexpr unsigned ctl = 0x9000, fsr = 0x9058, tlbStatus = 0x97f4;
    constexpr uint32_t enable = 1, faultInterrupt = 1u << 6, policyMask = 0x1f7;
    const auto io = contextTlbIo(smmu);
    const auto ownsBank = [&] {
        return readSmmu32(smmu, A650_SMMU_ID0) == 0x4c017e06 &&
            readSmmu32(smmu, A650_SMMU_ID1) == 0x20000005 &&
            readSmmu32(smmu, 0x1804) == image.cba2r &&
            readSmmu32(smmu, 0x1004) == image.cbar &&
            readTtbrWords(smmu, 0x9020) == image.ttbr0;
    };
    const auto inactive = [&] {
        return live() && ownsBank() && readSmmu32(smmu, fsr) == cbFsrAarch64 &&
            !(readSmmu32(smmu, ctl) & enable);
    };
    const auto sync = [&](unsigned bit) {
        ArmSmmu4KProgramResult syncResult = {};
        const auto status = ArmSmmu4KSyncContextTlb(&io, ctl, static_cast<unsigned>(image.ttbr0 >> 48),
                                                   0, 1000, &syncResult);
        result.tlbReads += syncResult.poll_reads;
        if (status || !syncResult.tlb_synchronized) return false;
        result.tlbSynced |= bit;
        return true;
    };
    result.activation = "sync-on";
    if (!inactive() || (readSmmu32(smmu, tlbStatus) & 1) || !sync(1) || !inactive()) return;

    const uint32_t requested = image.sctlr & ~faultInterrupt;
    writeSmmu32(smmu, ctl, requested);
    result.ctlOn = readSmmu32(smmu, ctl);
    result.fsrOn = readSmmu32(smmu, fsr);
    result.activation = "disable";
    if (!ownsBank()) return;
    // Withdraw M even if the active readback or fault status differs.
    writeSmmu32(smmu, ctl, requested & ~enable);
    result.ctlOff = readSmmu32(smmu, ctl);
    result.fsrOff = readSmmu32(smmu, fsr);
    if ((result.ctlOff & (enable | faultInterrupt)) || !ownsBank()) return;

    result.activation = "sync-off";
    if (!sync(2)) return;
    result.activation = "readback";
    if (!inactive() || result.fsrOn != cbFsrAarch64 || result.fsrOff != cbFsrAarch64 ||
        ((result.ctlOn ^ requested) & policyMask) ||
        ((result.ctlOff ^ (requested & ~enable)) & policyMask)) return;
    result.activation = "ok";
}

template <typename Live>
static void installCb1Root(IOMemoryMap &smmu, GpuCpSnapshot &result, Live live, bool activate) {
    constexpr unsigned va64 = 0x1804, bar = 0x1004, ctl = 0x9000, fsr = 0x9058;
    const auto view = [&](uint32_t expectedVa, uint32_t expectedBar, uint32_t expectedFsr) {
        return live() && readSmmu32(smmu, va64) == expectedVa &&
            readSmmu32(smmu, bar) == expectedBar && readSmmu32(smmu, fsr) == expectedFsr &&
            !(readSmmu32(smmu, ctl) & 1);
    };
    result.rootState = "guard";
    if (!view(0, 0, 0)) return;
    CpTables tables;
    if (!prepareCpTables(tables, readSmmu32(smmu, A650_SMMU_ID0), readSmmu32(smmu, A650_SMMU_ID2),
                         result.sqeBytes)) {
        result.rootState = tables.stage;
        return;
    }
    ArmSmmu4KMmio mmio = {reinterpret_cast<volatile unsigned char *>(smmu.getVirtualAddress()), 0x10000};
    ArmSmmu4KIo io = {};
    result.rootState = "bind";
    if (ArmSmmu4KBindMmio(&mmio, &io)) return;
    publishGmuTables(tables);
    if (!view(0, 0, 0)) return;
    result.rootState = "format";
    writeSmmu32(smmu, va64, tables.image.cba2r);
    if (!view(1, 0, cbFsrAarch64)) return;
    result.rootState = "bar";
    writeSmmu32(smmu, bar, tables.image.cbar);
    const auto ready = [&] { return view(1, tables.image.cbar, cbFsrAarch64); };
    if (!ready()) return;

    constexpr unsigned fields[] = {0x9010, 0x9030, 0x9038, 0x903c, 0x9020, 0x9028};
    constexpr unsigned firstTtbr = 4, count = sizeof(fields) / sizeof(fields[0]);
    const uint64_t expected[] = {tables.image.tcr2, tables.image.tcr, tables.image.mair0,
                                 tables.image.mair1, tables.image.ttbr0, tables.image.ttbr1};
    const auto matches = [&](unsigned i) {
        if (i >= firstTtbr) {
            uint64_t word = 0;
            if (io.read64(io.cookie, fields[i], &word) || readTtbrWords(smmu, fields[i]) != word) return false;
            if (i == firstTtbr) result.liveRoot = word;
            return word == expected[i];
        }
        const uint64_t word = readSmmu32(smmu, fields[i]);
        const uint64_t addedTbi = i == 0 ? word & ~expected[i] & 0x60 : 0;
        return !((word ^ expected[i]) & ~addedTbi);
    };
    result.rootState = "hold";
    for (unsigned i = 0; i < count; ++i) {
        if (!ready()) return;
        if (i == firstTtbr) {
            // Once TTBR programming starts, retain the wired backing even
            // if subsequent writes or readbacks fail.
            tables.memory.detach();
            result.rootHeld = true;
        }
        if (i >= firstTtbr) {
            if (io.write64(io.cookie, fields[i], expected[i]) || io.barrier(io.cookie)) return;
        } else {
            writeSmmu32(smmu, fields[i], static_cast<uint32_t>(expected[i]));
        }
        if (!matches(i)) return;
        result.rootFields |= 1u << i;
    }
    for (unsigned i = 0; i < count; ++i) if (!matches(i)) return;
    if (!ready()) return;
    result.rootState = "audit";
    if (!auditGmuTables(tables, result.liveRoot)) return;
    result.leaves = static_cast<unsigned>(tables.audit.leaf_pages);
    result.rootState = "ok";
    if (activate) pulseCpContext(smmu, result, tables.image, live);
}
#endif

template <typename Live>
static void pulseCb1Format(IOMemoryMap &smmu, GpuCpSnapshot &result, Live live) {
    constexpr unsigned va64 = 0x1804, bar = 0x1004, ctl = 0x9000, fsr = 0x9058;
    constexpr unsigned fields[] = {bar, ctl, 0x9010, 0x9020, 0x9024, 0x9028, 0x902c, 0x9030,
                                   0x9034, 0x9038, 0x903c, fsr, 0x9060, 0x9064, 0x9068};
    uint32_t saved[sizeof(fields) / sizeof(fields[0])];
    result.formatState = "pre";
    if (!live() || readSmmu32(smmu, va64)) return;
    for (unsigned i = 0; i < sizeof(saved) / sizeof(saved[0]); ++i) {
        saved[i] = readSmmu32(smmu, fields[i]);
        if (saved[i] == UINT32_MAX) return;
    }
    if (saved[0] || (saved[1] & 1) || readSmmu32(smmu, fsr) || !live()) return;

    writeSmmu32(smmu, va64, 1);
    result.vaDuring = readSmmu32(smmu, va64);
    result.barDuring = readSmmu32(smmu, bar);
    result.fsrDuring = readSmmu32(smmu, fsr);
    result.ctlDuring = readSmmu32(smmu, ctl);
    const bool active = result.vaDuring == 1 && result.fsrDuring == cbFsrAarch64 &&
        !(result.ctlDuring & 1) && !result.barDuring;

    result.formatState = "hold";
    if (!live() || result.vaDuring == UINT32_MAX) return;
    // Every non-GMU stream remains unpublished, even if the alternate CB1
    // view differed. Restore the original selector before comparing the view.
    writeSmmu32(smmu, va64, 0);
    result.vaAfter = readSmmu32(smmu, va64);
    for (unsigned i = 0; i < sizeof(saved) / sizeof(saved[0]); ++i)
        if (readSmmu32(smmu, fields[i]) != saved[i]) result.formatDiff |= 1u << i;
    if (!live() || result.vaAfter || result.formatDiff) return;
    result.formatState = active ? "ok" : result.vaDuring ? "view" : "filtered";
}

template <typename CheckRoute>
static void samplePoweredCp(IOMemoryMap &smmu, IOMemoryMap &gmu, GpuCpSnapshot &result,
                            unsigned power, CheckRoute checkRoute) {
    using namespace t970_touch;
    const auto live = [&] {
        return checkRoute() && !(read(gmu, 0x14340) & 0xc0) && !read(gmu, 0x14648) &&
            !(read(gmu, 0x24c14) & 0x29) && !read(gmu, 0x24c4c);
    };
    result.state = "guard";
    if (!live()) return;
    result.state = "map";
    auto gpu = mapMmio(A650_GPU_BASE_GPU, 0x40000);
    if (!gpu || !gpu->getVirtualAddress()) return;

    result.state = "read";
    if (!live()) return;
    result.rbbm = read(*gpu, 4 * 0x210);
    if (result.rbbm == UINT32_MAX) return;
    result.irq = read(*gpu, 4 * 0x201);
    result.rbBase = read(*gpu, 4 * 0x800) | (static_cast<uint64_t>(read(*gpu, 4 * 0x801)) << 32);
    result.rbCntl = read(*gpu, 4 * 0x802);
    result.rp = read(*gpu, 4 * 0x806);
    result.wp = read(*gpu, 4 * 0x807);
    result.sqe = read(*gpu, 4 * 0x808);
    result.fault = read(*gpu, 4 * 0x821);
    result.cpIrq = read(*gpu, 4 * 0x823);
    result.cbFormat = readSmmu32(smmu, 0x1804);
    result.cbBar = readSmmu32(smmu, 0x1004);
    result.cbCtl = readSmmu32(smmu, 0x9000);
    result.cbFsr = readSmmu32(smmu, 0x9058);
    result.cbTcr = readSmmu32(smmu, 0x9030);
    result.cbTtbr0 = readTtbrWords(smmu, 0x9020);
    result.slot = readSmmu32(smmu, A650_SMMU_S2CR(1));

    result.state = "busy";
    if ((result.rbbm & ~1u) || result.irq || result.rp || result.wp || result.sqe || result.fault ||
        result.cpIrq || result.cbFormat || result.cbBar || (result.cbCtl & 1) ||
        result.cbFsr || (result.slot & (3u << 16)) != (2u << 16)) return;
    result.state = "drift";
    if (!live() || result.rp != read(*gpu, 4 * 0x806) || result.wp != read(*gpu, 4 * 0x807) ||
        result.sqe != read(*gpu, 4 * 0x808) || result.fault != read(*gpu, 4 * 0x821) ||
        result.cpIrq != read(*gpu, 4 * 0x823) || result.cbCtl != readSmmu32(smmu, 0x9000) ||
        result.cbFsr != readSmmu32(smmu, 0x9058)) return;
    result.state = "idle";
    if (power == cbBootCb1FormatMode) pulseCb1Format(smmu, result, live);
#ifdef T970_GPU_SQE_FIRMWARE
    if (power >= cbBootCb1RootMode) installCb1Root(smmu, result, live, power == cbBootCb1ActivateMode);
#endif
}
#endif

static bool pulseSid5(IOMemoryMap &smmu, IOMemoryMap &gmu, SmmuSnapshot &result,
                      const uint32_t (&routes)[6], uint32_t sctlr,
                      [[maybe_unused]] GmuTables *bootTables, [[maybe_unused]] unsigned power) {
    constexpr unsigned smr0 = A650_SMMU_SMR(0), s2cr0 = A650_SMMU_S2CR(0);
    constexpr uint32_t globalPolicy = 0x40f, faultUnmatched = 0x406;
    constexpr uint32_t routeType = 3u << 16, faultRoute = 2u << 16;
    constexpr uint32_t sid5Match = (1u << 31) | (0x400u << 16) | 5u;
    // The lmi A650 route writes this field subset, preserving the other
    // firmware-owned bits. The stock GMU kernel match covers 5 and 0x405.
    // The inherited FAULT entry forces every read to Instruction. For the
    // live default-attribute probe, preserve the originating IND sideband.
    constexpr uint32_t instCfg = 3u << 26;
    const uint32_t routeMask = 0x030303ffu | (power >= cbBootDefaultInstMode ? instCfg : 0);
    const uint32_t translated = (routes[0] & ~routeMask) | 0x300u;
    uint32_t expectedRoutes[6];
    memcpy(expectedRoutes, routes, sizeof(expectedRoutes));
    const auto matches = [&](uint32_t match, uint32_t route, bool requireCold = true) {
        auto current = readCbGuards(smmu);
        if (!requireCold) {
            result.boot.globalFault = current.gfsr;
            result.boot.contextFault = current.fsr;
        }
        if (current.bar != cbBarStage1 || current.sctlr != sctlr ||
            readSmmu32(smmu, A650_SMMU_ID2) != result.id2 ||
            current.smrs != (match ? 1u : 0u) || readSmmu32(smmu, smr0) != match)
            return false;
        current.smrs = 0;
        expectedRoutes[0] = route;
        return barViewMatches(smmu, result, expectedRoutes, current, true) && (!requireCold || coldGmu(gmu));
    };
    result.sid5State = "policy";
    if ((result.scr0 & globalPolicy) != faultUnmatched || (routes[0] & routeType) != faultRoute)
        return true;
    result.sid5State = "guard";
    if (!matches(0, routes[0])) return false;

    writeSmmu32(smmu, s2cr0, translated);
    result.sid5S2cr = readSmmu32(smmu, s2cr0);
    const bool staged = result.sid5S2cr == translated && matches(0, translated);
    bool published = false;
    if (staged) {
        writeSmmu32(smmu, smr0, sid5Match);
        result.sid5Smr = readSmmu32(smmu, smr0);
        published = result.sid5Smr == sid5Match && matches(sid5Match, translated);
    }

#ifdef T970_GPU_GMU_FIRMWARE
    if (published && bootTables) {
        result.boot.reset = t970_touch::read(gmu, 0x14000);
        const bool safe = stageGmuFirmware(gmu, *bootTables, result.firmware, true);
        result.boot.state = result.firmware.state;
        if (!safe || !strcmp(result.firmware.state, "loaded")) {
            // The loaded image and all live state are kept through reboot.
            result.boot.keepRoute = true;
            result.sid5State = "live";
            if (safe) {
                result.boot.state = "route";
                if (matches(sid5Match, translated)) {
                    const auto hfiMode = power >= cbBootHfiGxMode ? GmuHfiProbeMode::Gx :
                        power == cbBootHfiCoreMode ? GmuHfiProbeMode::Core :
                        power == cbBootHfiPerfMode ? GmuHfiProbeMode::Performance :
                        power == cbBootHfiVersionMode ? GmuHfiProbeMode::Version : GmuHfiProbeMode::None;
                    const auto liveRoute = [&] { return matches(sid5Match, translated, false); };
                    startGmuBoot(gmu, smmu, *bootTables, result.boot, power != cbBootMode, hfiMode, liveRoute);
                    if (power >= cbBootCpReadMode && !strcmp(result.boot.hfiGx.state, "ok"))
                        samplePoweredCp(smmu, gmu, result.cp, power, liveRoute);
                }
            }
            return false;
        }
    }
#endif

    result.sid5State = "detach";
    if (readSmmu32(smmu, A650_SMMU_ID0) != result.id0 ||
        readSmmu32(smmu, A650_SMMU_ID1) != result.id1 ||
        readSmmu32(smmu, A650_SMMU_ID2) != result.id2) return false;
    if (staged) writeSmmu32(smmu, smr0, 0);
    result.sid5SmrAfter = readSmmu32(smmu, smr0);
    // Restore the inherited FAULT route even if SMR withdrawal was filtered.
    writeSmmu32(smmu, s2cr0, routes[0]);
    result.sid5S2crAfter = readSmmu32(smmu, s2cr0);
    if (result.sid5SmrAfter || result.sid5S2crAfter != routes[0] ||
        !matches(0, routes[0])) return false;
    result.sid5State = published ? "ok" : staged ? "smr" : "s2cr";
    return true;
}

static bool pulseCbActivation(IOMemoryMap &smmu, IOMemoryMap &gmu, SmmuSnapshot &result,
                              const uint32_t (&routes)[6], const ArmSmmu4KContextImage &image,
                              uint32_t original, bool publishSid5, GmuTables *bootTables, unsigned power) {
    constexpr unsigned sctlr = 0x8000, tlbStatus = 0x87f4;
    constexpr uint32_t enable = 1, faultInterrupt = 1u << 6, policyMask = 0x1f7;
    const auto tlbIo = contextTlbIo(smmu);
    const auto sync = [&](unsigned bit) {
        ArmSmmu4KProgramResult syncResult = {};
        const auto status = ArmSmmu4KSyncContextTlb(&tlbIo, sctlr, static_cast<unsigned>(image.ttbr0 >> 48),
                                                    0, 1000, &syncResult);
        result.tlbReads += syncResult.poll_reads;
        if (status || !syncResult.tlb_synchronized) return false;
        result.tlbSynced |= bit;
        return true;
    };
    const auto stillOwnsView = [&](const CbGuards &guards) {
        return !(guards.flags() & 1u) && guards.bar == cbBarStage1 && guards.sctlr != UINT32_MAX &&
            readSmmu32(smmu, 0x1800) == 1;
    };
    const auto contextMatches = [&]() {
        const uint32_t tcr2 = readSmmu32(smmu, 0x8010);
        const uint32_t addedTbi = tcr2 & ~image.tcr2 & 0x60;
        return !((tcr2 ^ image.tcr2) & ~addedTbi) && readSmmu32(smmu, 0x8030) == image.tcr &&
            readSmmu32(smmu, 0x8038) == image.mair0 && readSmmu32(smmu, 0x803c) == image.mair1 &&
            readTtbrWords(smmu, 0x8020) == image.ttbr0 && readTtbrWords(smmu, 0x8028) == image.ttbr1;
    };
    const auto before = readCbGuards(smmu);
    result.activation = "sync-on";
    if (!stillOwnsView(before) || before.sctlr != original ||
        !barViewIdle(smmu, gmu, result, routes, before) || (readSmmu32(smmu, tlbStatus) & 1) ||
        !sync(1)) return false;
    const auto ready = readCbGuards(smmu);
    if (!stillOwnsView(ready) || ready.sctlr != original ||
        !barViewIdle(smmu, gmu, result, routes, ready) || !contextMatches()) return false;

    // No stream is published and CM3 stays in reset. Use polling for faults
    // during this pulse, with context fault interrupts disabled.
    const uint32_t requested = image.sctlr & ~faultInterrupt;
    writeSmmu32(smmu, sctlr, requested);
    const auto active = readCbGuards(smmu);
    result.ctlOn = active.sctlr;
    result.activation = "disable";
    if (!stillOwnsView(active)) return false;
    const bool activeClean = barViewIdle(smmu, gmu, result, routes, active, active.sctlr & enable) &&
        contextMatches();
    const bool activeMatch = activeClean && (active.sctlr & policyMask) == (requested & policyMask);
    const bool routeWithdrawn = !publishSid5 || !activeMatch ||
        (pulseSid5(smmu, gmu, result, routes, active.sctlr, bootTables, power) && contextMatches());
    if (result.boot.keepRoute) return false;
    if (publishSid5 && !stillOwnsView(readCbGuards(smmu))) return false;
    // Withdraw M even if the active readback failed, before considering
    // any restoration of the root and original control word.
    writeSmmu32(smmu, sctlr, requested & ~enable);
    const auto disabled = readCbGuards(smmu);
    result.ctlOff = disabled.sctlr;
    if (!activeClean || !routeWithdrawn || !stillOwnsView(disabled) ||
        (disabled.sctlr & (enable | faultInterrupt)) || !barViewIdle(smmu, gmu, result, routes, disabled))
        return false;
    result.activation = "sync-off";
    if (!sync(2)) return false;
    const auto synced = readCbGuards(smmu);
    if (!stillOwnsView(synced) || synced.sctlr != disabled.sctlr ||
        !barViewIdle(smmu, gmu, result, routes, synced)) return false;
    writeSmmu32(smmu, sctlr, original);
    const auto restored = readCbGuards(smmu);
    result.activation = "ctl-restore";
    if (!stillOwnsView(restored) || restored.sctlr != original ||
        !barViewIdle(smmu, gmu, result, routes, restored)) return false;
    result.activation = activeMatch ? "ok" : "readback";
    return true;
}

static bool pulseCbRoot(IOMemoryMap &smmu, IOMemoryMap &gmu, SmmuSnapshot &result,
                        const uint32_t (&routes)[6], IOBufferMemoryDescriptor *&wiredRoot, unsigned power) {
    GmuTables tables;
    if (!prepareGmuTables(tables, result.id0, result.id2, power == cbBootScratchExecMode)) {
        result.rootState = tables.stage;
        return true;
    }
    ArmSmmu4KMmio mmio = {reinterpret_cast<volatile unsigned char *>(smmu.getVirtualAddress()), 0x10000};
    ArmSmmu4KIo io = {};
    result.rootState = "bind";
    if (ArmSmmu4KBindMmio(&mmio, &io)) return true;
    const auto before = readCbGuards(smmu);
    const auto idle = [&]() {
        const auto current = readCbGuards(smmu);
        return current.bar == cbBarStage1 && current.sctlr == before.sctlr &&
            barViewIdle(smmu, gmu, result, routes, current);
    };
    result.rootState = "guard";
    if (before.bar != cbBarStage1 || !idle()) return false;

    constexpr unsigned fields[] = {0x8010, 0x8030, 0x8038, 0x803c, 0x8020, 0x8028};
    constexpr unsigned firstTtbr = 4, fieldCount = 6;
    const uint64_t requested[] = {tables.image.tcr2, tables.image.tcr, tables.image.mair0,
                                  tables.image.mair1, tables.image.ttbr0, tables.image.ttbr1};
    const auto readField = [&](unsigned i, uint64_t &value) {
        const auto offset = fields[i];
        if (i < firstTtbr) {
            value = readSmmu32(smmu, offset);
            return true;
        }
        return !io.read64(io.cookie, offset, &value) && readTtbrWords(smmu, offset) == value;
    };
    const auto writeField = [&](unsigned i, uint64_t value) {
        if (i >= firstTtbr) return !io.write64(io.cookie, fields[i], value) && !io.barrier(io.cookie);
        writeSmmu32(smmu, fields[i], static_cast<uint32_t>(value));
        return true;
    };
    uint64_t saved[fieldCount] = {};
    result.rootState = "baseline";
    for (unsigned i = 0; i < fieldCount; ++i) {
        if (!readField(i, saved[i])) return true;
    }
#ifdef T970_GPU_GMU_FIRMWARE
    if (power == cbFirmwareMode && !stageGmuFirmware(gmu, tables, result.firmware)) return false;
#endif

    publishGmuTables(tables);
    if (!idle()) return false;
    for (unsigned i = 0; i < fieldCount; ++i) {
        uint64_t value = 0;
        if (!readField(i, value) || value != saved[i]) return false;
    }

    // Transfer the retain through final CB0 verification. An uncertain
    // rollback keeps this diagnostic allocation wired until reboot.
    wiredRoot = tables.memory.detach();
    result.rootHeld = true;
    result.rootState = "hold";
    unsigned attempted = 0;
    uint64_t observed[fieldCount] = {};
    for (unsigned i = 0; i < fieldCount; ++i) {
        ++attempted;
        const bool wrote = writeField(i, requested[i]);
        if (!idle()) return false;
        if (!wrote || !readField(i, observed[i])) break;
        // The pinned context validator allows TCR2.TBI0/TBI1 to read as set.
        const uint64_t addedTbi = i == 0 ? observed[i] & ~requested[i] & 0x60 : 0;
        if ((observed[i] ^ requested[i]) & ~addedTbi) break;
        result.rootInstalled |= 1u << i;
    }
    const unsigned fullMask = (1u << fieldCount) - 1;
    if (result.rootInstalled == fullMask) {
        for (unsigned i = 0; i < fieldCount; ++i) {
            uint64_t value = 0;
            if (!readField(i, value) || value != observed[i]) result.rootInstalled &= ~(1u << i);
        }
    }
    if (!idle()) return false;
    const bool installed = result.rootInstalled == fullMask;
    const bool audited = installed && auditGmuTables(tables, observed[firstTtbr]);
    if (audited) result.rootLeaves = static_cast<unsigned>(tables.audit.leaf_pages);
    const bool publishSid5 = power == cbSid5Mode || isBootMode(power);
    GmuTables *bootTables = isBootMode(power) ? &tables : nullptr;
    if (audited && (power == cbActivateMode || publishSid5) &&
        !pulseCbActivation(smmu, gmu, result, routes, tables.image, before.sctlr, publishSid5, bootTables,
                           power))
        return false;

    // TCR2/TCR precede restoring TTBRs because TCR2 controls ASID width.
    for (unsigned i = 0; i < attempted; ++i) {
        if (!idle() || !writeField(i, saved[i])) return false;
    }
    for (unsigned i = 0; i < fieldCount; ++i) {
        uint64_t value = 0;
        if (readField(i, value) && value == saved[i]) result.rootRestored |= 1u << i;
    }
    if (!idle() || result.rootRestored != fullMask) return false;
    result.rootState = audited ? "ok" : installed ? tables.stage : "readback";
    return true;
}
#endif

static bool pulseCbBar(IOMemoryMap &smmu, IOMemoryMap &gmu, SmmuSnapshot &result,
                       const uint32_t (&routes)[6], [[maybe_unused]] unsigned power,
                       [[maybe_unused]] IOBufferMemoryDescriptor *&wiredRoot) {
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
    if (power >= cbRootMode && active.bar == cbBarStage1 &&
        !pulseCbRoot(smmu, gmu, result, routes, wiredRoot, power)) return false;
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
    IOBufferMemoryDescriptor *wiredRoot = nullptr;
    // A CBAR view change alone grants no route. Permit restoring VA64 with
    // all six SMRs zero, translation disabled and fault state clear.
    if (result.va64Active == UINT32_MAX || result.guard.bar == UINT32_MAX ||
        (result.guard.flags() & ~cbBarChanged)) return;
    if (barGmu) {
        if (result.va64Active == 1 && result.guard.fsr == cbFsrAarch64 &&
            !pulseCbBar(smmu, *barGmu, result, routes, power, wiredRoot) && strcmp(result.barState, "pre")) return;
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
#ifdef T970_GPU_GMU_TABLES
    if (wiredRoot) {
        wiredRoot->release();
        result.rootHeld = false;
    }
#endif
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
static void pulseSmmuBus(IOMemoryMap &gcc, IOMemoryMap &gmu, unsigned power, SmmuSnapshot &result) {
    using namespace t970_touch;
    constexpr unsigned gpu = A650_GPU_BASE_GCC_GPU - 0x100000;
    constexpr unsigned clocks[] = {gpu + A650_GCC_GPU_MEMNOC_GFX, gpu + A650_GCC_GPU_SNOC_DVM_GFX,
                                   gpu + A650_GCC_DDRSS_GPU_AXI};
    constexpr uint32_t enable = A650_CBCR_ENABLE;
    const unsigned count = isBootMode(power) ? 3 : 2;
    result.state = "clock";
    uint32_t before[3] = {};
    unsigned visited = 0;
    for (unsigned i = 0; i < count; ++i) {
        before[i] = read(gcc, clocks[i]);
        if (i == ddrAxiIndex) {
            result.state = "axi";
            result.ddrAxiBefore = before[i];
        }
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
    if (result.ready == (1u << count) - 1) sampleSmmu(result, gmu, power);
    if (result.holdParents) return;
    for (unsigned i = count; i-- > 0;) {
        const unsigned bit = 1u << i;
        if (!(visited & bit)) continue;
        uint32_t value = read(gcc, clocks[i]);
        if (value != UINT32_MAX && !(before[i] & enable) && (value & enable)) {
            write(gcc, clocks[i], value & ~enable);
            IODelay(10);
            value = read(gcc, clocks[i]);
        }
        if (i == ddrAxiIndex) result.ddrAxiAfter = value;
        if (value == UINT32_MAX || ((value ^ before[i]) & enable)) break;
        result.restored |= bit;
    }
    result.holdParents = result.restored != visited;
    if (result.holdParents) result.state = "bus-hold";
}

} // namespace t970_gpu
