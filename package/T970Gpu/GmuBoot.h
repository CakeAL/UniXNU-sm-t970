// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>

namespace t970_gpu {

// One context-fault observation. The SMMU-500 FSR/FAR/FSYNR0 pairing is
// read while the offending transaction is still stalled, so the reported
// values describe the first access the GMU issued after CM3 release.
struct GmuFault {
    uint32_t fsr = 0, fsynr = 0, sid = 0, pteBefore = 0, pteAfter = 0;
    uint64_t far = 0;
    unsigned polls = 0;
    char access = '-', privilege = '-';
    bool resumed = false;
    bool captured = false;
};

struct GmuBootProbe {
    const char *state = "skip";
    uint32_t fwInit = 0, hfiStatus = 0, hfiVersion = 0, reset = 0;
    uint32_t globalFault = 0, contextFault = 0, aoStatus = 0, gmuStatus = 0;
    unsigned offset = 0;
    bool keepRoute = false;
    static constexpr unsigned maxFaults = 3;
    GmuFault fault[maxFaults] = {};
    unsigned faultEvents = 0;
};

}

#ifdef T970_GPU_GMU_FIRMWARE
#include "GmuFirmware.h"

namespace t970_gpu {

// Linux arm-smmu documents the SMMU-500 CBn_FSR layout: TF[1], AFF[2], PF[3],
// EF[4], TLBMCF[5], TLBLKF[6], ASF[7], UUT[8], FORMAT[10:9], SS[30]. FORMAT=2
// (0x400) appears whenever an AArch64 walk is in effect and is not a fault.
enum { gmuFaultNone = 0, gmuFaultPermission, gmuFaultTranslation, gmuFaultExternal, gmuFaultOther };

static unsigned gmuFaultClass(uint32_t fsr) {
    if (!(fsr & 0x1feu)) return gmuFaultNone;
    if (fsr & 0x008u) return gmuFaultPermission;
    if (fsr & 0x002u) return gmuFaultTranslation;
    if (fsr & 0x010u) return gmuFaultExternal;
    return gmuFaultOther;
}

// Stage-1 leaf attributes. AF[10] is required because SCTLR.AFE is clear,
// AP[2:1] select read-only/unprivileged and XN[54:53] removes execute.
static constexpr uint64_t gmuPteAddress = UINT64_C(0x0000fffffffff000);

struct GmuTableShape {
    uint64_t *tables;
    uint64_t physical, bytes;
    unsigned input_bits, start_level;
};

// Walk the same layout ArmSmmu4K built: only 4 KiB level-3 leaves, TTBR0's
// low address region, start level derived from the input width.
static uint64_t *gmuLeafDescriptor(const GmuTableShape &shape, uint64_t iova) {
    if (!shape.tables || !shape.physical || (iova & 0xfff) || (iova >> shape.input_bits))
        return nullptr;
    uint64_t table = shape.physical;
    for (unsigned level = shape.start_level; level < 3; ++level) {
        if (table < shape.physical || table - shape.physical + 0x1000 > shape.bytes) return nullptr;
        const unsigned shift = 39 - 9 * level;
        const unsigned width = level == shape.start_level ? shape.input_bits - shift : 9;
        const uint64_t entry = reinterpret_cast<const uint64_t *>(
            reinterpret_cast<const uint8_t *>(shape.tables) + (table - shape.physical))[
            (iova >> shift) & ((UINT64_C(1) << width) - 1)];
        if ((entry & 3) != 3) return nullptr;
        table = entry & gmuPteAddress;
    }
    return &reinterpret_cast<uint64_t *>(
        reinterpret_cast<uint8_t *>(shape.tables) + (table - shape.physical))[(iova >> 12) & 511];
}

// SMMU-500 CBn_FSYNR0: WNR[4] write, PNU[5] privileged, IND[6] instruction.
// Widen only the rejected attribute: keep the physical address, force AF,
// make the leaf writable, follow the observed privilege, and allow execute
// only for an instruction fetch. A caller must compare before/after and
// refuse when the syndrome asks for no change.
static uint64_t gmuRepairDescriptor(uint64_t pte, uint32_t fsynr) {
    constexpr uint64_t af = UINT64_C(1) << 10, ap1 = UINT64_C(1) << 6, ap2 = UINT64_C(1) << 7;
    constexpr uint64_t xn = UINT64_C(3) << 53;
    pte |= af;
    pte &= ~ap2;
    if (fsynr & (1u << 5)) pte &= ~ap1;
    else pte |= ap1;
    if (fsynr & (1u << 6)) pte &= ~xn;
    return pte;
}

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
//
// With `repair`, a permission fault on the first post-release access is
// captured and the offending 4 KiB leaf is widened by exactly the attribute
// the syndrome names, then the context TLB is dropped, the stalled fault is
// cleared and the transaction is retried. The probe never patches a
// translation, a page-table walk fault or a page outside the audited ranges.
template <typename CheckRoute>
static void startGmuBoot(IOMemoryMap &gmu, IOMemoryMap &smmu, GmuTables &tables,
                         GmuBootProbe &result, bool repair, CheckRoute checkRoute) {
    using t970_touch::read;
    using t970_touch::write;
    constexpr unsigned reset = 0x14000, fwInit = 0x14070;
    constexpr unsigned hfiInit = 0x14618, hfiStatus = 0x14600, hfiVersion = 0x14604;
    constexpr unsigned aoMask = 0x24c18, gmuMask = 0x1464c;
    constexpr uint32_t aoFatal = 0x29, cm3Fatal = 0x00800000;
    // SMMU-500 CB0: FSR, FAR (64-bit), FSYNR0, resume, and the local TLB
    // registers. CBFRSYNRA0 lives at GR1 + 0x400.
    constexpr unsigned cbFsr = 0x8058, cbFar = 0x8060, cbFsynr = 0x8068, cbFrsynra = 0x1400;
    constexpr unsigned cbResume = 0x8008, cbTlbAsid = 0x8610, cbTlbsync = 0x87f0, cbTlbStatus = 0x87f4;
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

    const GmuTableShape shape = {tables.tables, tables.config.table_physical, GmuTables::bytes,
                                 tables.config.input_bits, tables.built.start_level};
    unsigned attempt = 0;
    const auto handleFault = [&]() -> bool {
        const unsigned fsr = read(smmu, cbFsr);
        if (!repair || gmuFaultClass(fsr) == gmuFaultNone) return false;
        if (result.faultEvents >= GmuBootProbe::maxFaults) {
            // Out of repair attempts: release the stalled transaction so the
            // reset write cannot wait on it.
            write(smmu, cbFsr, fsr);
            write(smmu, cbResume, 1);
            __asm__ volatile("dsb sy" ::: "memory");
            return false;
        }
        GmuFault &f = result.fault[result.faultEvents++];
        f.captured = true;
        f.fsr = fsr;
        f.far = read(smmu, cbFar) | (static_cast<uint64_t>(read(smmu, cbFar + 4)) << 32);
        f.fsynr = read(smmu, cbFsynr);
        f.sid = read(smmu, cbFrsynra) & 0xffff;
        f.polls = attempt;
        const auto stop = [&](char why) {
            f.access = why;
            // Drop a stalled transaction before the caller re-asserts reset.
            write(smmu, cbFsr, fsr);
            write(smmu, cbResume, 1);
            __asm__ volatile("dsb sy" ::: "memory");
            return false;
        };
        if (gmuFaultClass(fsr) != gmuFaultPermission) return stop('t');
        if (f.fsynr & (1u << 10)) return stop('t'); // page-table walk fault
        // FAR may zero- or sign-extend below the context width; accept only
        // one of those two upper halves before trusting the address.
        const uint64_t widthMask = (UINT64_C(1) << shape.input_bits) - 1;
        const uint64_t upper = f.far & ~widthMask;
        if (upper && upper != ~widthMask) return stop('t');
        const uint64_t page = (f.far & widthMask) & ~UINT64_C(0xfff);
        uint64_t *leaf = gmuLeafDescriptor(shape, page);
        if (!leaf || (*leaf & 3) != 3) return stop('t');
        const uint64_t before = *leaf;
        uint64_t expected = UINT64_MAX;
        for (const auto &range : tables.ranges) {
            if (page >= range.iova && page + 0x1000 <= range.iova + range.bytes) {
                expected = range.physical + (page - range.iova);
                break;
            }
        }
        if (expected == UINT64_MAX || (before & gmuPteAddress) != expected) return stop('t');
        const uint64_t after = gmuRepairDescriptor(before, f.fsynr);
        if (after == before) return stop('t');
        *leaf = after;
        __asm__ volatile("dc cvac, %0" :: "r"(leaf) : "memory");
        __asm__ volatile("dsb sy" ::: "memory");
        f.pteBefore = static_cast<uint32_t>(before);
        f.pteAfter = static_cast<uint32_t>(after);
        f.access = (f.fsynr & (1u << 6)) ? 'x' : (f.fsynr & (1u << 4)) ? 'w' : 'r';
        f.privilege = (f.fsynr & (1u << 5)) ? 'p' : 'u';
        // Drop every cached translation of this owned ASID, clear the stalled
        // fault and retry. The GMU is the only published stream in the bank.
        write(smmu, cbTlbAsid, static_cast<uint32_t>((tables.image.ttbr0 >> 48) & 0xffff));
        write(smmu, cbTlbsync, UINT32_MAX);
        for (unsigned i = 0; i < 1000 && (read(smmu, cbTlbStatus) & 1); ++i) IODelay(1);
        write(smmu, cbFsr, fsr);
        write(smmu, cbResume, 0);
        __asm__ volatile("dsb sy" ::: "memory");
        f.resumed = true;
        return true;
    };
    const auto poll = [&](unsigned offset, uint32_t mask, uint32_t expected, uint32_t &last) {
        for (attempt = 0; attempt < 1000; ++attempt) {
            last = read(gmu, offset);
            if (read(gmu, reset) != 0) return false;
            if (!healthy()) {
                if (!handleFault()) return false;
                continue;
            }
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
