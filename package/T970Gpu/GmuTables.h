// SPDX-License-Identifier: MIT
#pragma once
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <IOKit/IOLib.h>
#include <libkern/c++/OSSharedPtr.h>
#include "ArmSmmu4KTableMemory.h"

namespace t970_gpu {

template <size_t PayloadPages, size_t RangeCount>
struct T970GpuTables {
    static constexpr size_t pageBytes = 4096;
    static constexpr size_t poolPages = 8, payloadPages = PayloadPages, rangeCount = RangeCount;
    static constexpr size_t bytes = (poolPages + payloadPages) * pageBytes;
    OSSharedPtr<IOBufferMemoryDescriptor> memory;
    uint64_t *tables = nullptr;
    ArmSmmu4KRange ranges[rangeCount] = {};
    ArmSmmu4KConfig config = {};
    ArmSmmu4KResult built = {};
    ArmSmmu4KContextImage image = {};
    ArmSmmu4KTableAuditResult audit = {};
    ArmSmmu4KStatus status = ArmSmmu4KSuccess;
    const char *stage = "alloc";
};

using GmuTables = T970GpuTables<42, 5>;

template <typename Tables>
static bool auditGmuTables(Tables &gmu, uint64_t ttbr0) {
    const ArmSmmu4KTableMemory backing = {1, {{gmu.tables, gmu.config.table_physical, Tables::poolPages}, {}}};
    ArmSmmu4KTableIo io = {};
    gmu.stage = "bind";
    gmu.status = ArmSmmu4KBindTableMemory(&backing, &io);
    if (gmu.status) return false;
    unsigned char visited[Tables::poolPages] = {};
    const ArmSmmu4KAuditRegion region = {gmu.ranges, Tables::rangeCount, Tables::poolPages,
                                        Tables::poolPages * 512, visited, sizeof(visited)};
    const uint64_t root = ttbr0 & UINT64_C(0x0000ffffffffffff);
    gmu.stage = "audit";
    gmu.status = ArmSmmu4KAuditTables(&io, &gmu.config, &gmu.built, &region, root, &gmu.audit);
    if (!gmu.status && (!gmu.audit.complete || gmu.audit.leaf_pages != Tables::payloadPages))
        gmu.status = ArmSmmu4KStateMismatch;
    if (!gmu.status) gmu.stage = "ok";
    return !gmu.status;
}

template <typename Tables>
static bool allocateGpuTables(Tables &gmu) {
    // Kernel-owned wired backing. Its retain must outlive any installed root.
    const IOOptionBits options = static_cast<IOOptionBits>(kIODirectionInOut) |
        static_cast<IOOptionBits>(kIOMemoryPhysicallyContiguous) | kIOMemoryMapperNone;
    gmu.memory = OSSharedPtr<IOBufferMemoryDescriptor>(
        IOBufferMemoryDescriptor::inTaskWithOptions(kernel_task, options, Tables::bytes, 16384), OSNoRetain);
    if (!gmu.memory) return false;
    gmu.stage = "backing";
    IOByteCount contiguous = 0;
    const uint64_t physical = gmu.memory->getPhysicalSegment(0, &contiguous, kIOMemoryMapperNone);
    gmu.tables = static_cast<uint64_t *>(gmu.memory->getBytesNoCopy());
    constexpr unsigned addressBits = 36;
    constexpr uint64_t pageMask = Tables::pageBytes - 1;
    if (!gmu.tables || (reinterpret_cast<uintptr_t>(gmu.tables) & pageMask) ||
        !physical || (physical & pageMask) || contiguous < Tables::bytes ||
        physical > (UINT64_C(1) << addressBits) - Tables::bytes) return false;
    gmu.config = {addressBits, addressBits, physical, Tables::payloadPages};
    bzero(gmu.tables, Tables::bytes);
    return true;
}

template <typename Tables>
static bool buildGpuTables(Tables &gmu, uint32_t id0, uint32_t id2, unsigned asid) {
    gmu.stage = "build";
    gmu.status = ArmSmmu4KBuild(&gmu.config, gmu.ranges, Tables::rangeCount, gmu.tables,
                               Tables::poolPages, &gmu.built);
    if (gmu.status) return false;
    const ArmSmmu4KContextConfig context = {&gmu.config, nullptr, &gmu.built, nullptr, id0, id2, asid, 0, 1, 0};
    gmu.stage = "encode";
    gmu.status = ArmSmmu4KEncodeContext(&context, &gmu.image);
    if (gmu.status) return false;
    return auditGmuTables(gmu, gmu.image.ttbr0);
}

static bool prepareGmuTables(GmuTables &gmu, uint32_t id0, uint32_t id2, bool executeScratch = false) {
    constexpr unsigned rw = ArmSmmu4KRead | ArmSmmu4KWrite | ArmSmmu4KPrivileged;
    if (!allocateGpuTables(gmu)) return false;
    // A650 GMU RAM windows from lmi mode 27. Payloads stay zero for the probe.
    const uint64_t payload = gmu.config.table_physical + GmuTables::poolPages * GmuTables::pageBytes;
    const ArmSmmu4KRange ranges[] = {
        {0x00004000, payload,           0x08000, ArmSmmu4KRead | ArmSmmu4KExecute | ArmSmmu4KPrivileged, 0, 2},
        // T970 SID5 issued privileged fetches in this window at CM3 startup.
        {0x00144000, payload + 0x08000, 0x13000, executeScratch ? rw | ArmSmmu4KExecute : rw, 0, 2},
        {0x00157000, payload + 0x1b000, 0x09000, rw, 0, 2},
        {0x60000000, payload + 0x24000, 0x01000, rw, 0, 2},
        {0x60001000, payload + 0x25000, 0x05000, rw, 0, 2},
    };
    static_assert(sizeof(ranges) == sizeof(gmu.ranges));
    memcpy(gmu.ranges, ranges, sizeof(ranges));
    return buildGpuTables(gmu, id0, id2, 1);
}

template <typename Tables>
static void publishGmuTables(const Tables &gmu) {
    // SM8250 uses 64-byte cache lines. Publish the backing at PoC for the GMU.
    const auto start = reinterpret_cast<uintptr_t>(gmu.tables);
    for (uintptr_t at = start; at < start + Tables::bytes; at += 64)
        __asm__ volatile("dc cvac, %0" :: "r"(at) : "memory");
    __asm__ volatile("dsb sy" ::: "memory");
}

static void reportGmuTables(char *out, unsigned length) {
    if (!length) return;
    GmuTables gmu;
    // Recorded v112 ID0/ID2 are sufficient for the software-only mode.
    if (!prepareGmuTables(gmu, 0x4c017e06, 0x5511) && !gmu.status) {
        snprintf(out, length, "%s", gmu.memory ? "\nGPU tables backing" : "\nGPU tables alloc");
        return;
    }
    snprintf(out, length, "\nGPU tables %s rc=%u table/leaf/read=%lu/%lu/%lu tcr=%x",
             gmu.stage, static_cast<unsigned>(gmu.status),
             gmu.audit.table_pages, gmu.audit.leaf_pages, gmu.audit.descriptor_reads, gmu.image.tcr);
}

} // namespace t970_gpu
