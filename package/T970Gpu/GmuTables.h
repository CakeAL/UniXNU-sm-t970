// SPDX-License-Identifier: MIT
#pragma once
#include <IOKit/IOBufferMemoryDescriptor.h>
#include <IOKit/IOLib.h>
#include "ArmSmmu4KTableMemory.h"

namespace t970_gpu {

static void reportGmuTables(char *out, unsigned length) {
    if (!length) return;
    constexpr uint64_t pageBytes = 4096;
    constexpr size_t poolPages = 8, payloadPages = 42;
    constexpr uint64_t poolBytes = poolPages * pageBytes;
    constexpr uint64_t bytes = (poolPages + payloadPages) * pageBytes;
    constexpr unsigned addressBits = 36;
    constexpr unsigned rw = ArmSmmu4KRead | ArmSmmu4KWrite | ArmSmmu4KPrivileged;

    // Kernel-owned wired backing. The descriptor stays live through the audit.
    const IOOptionBits options = static_cast<IOOptionBits>(kIODirectionInOut) |
        static_cast<IOOptionBits>(kIOMemoryPhysicallyContiguous) | kIOMemoryMapperNone;
    auto *memory = IOBufferMemoryDescriptor::inTaskWithOptions(kernel_task, options, bytes, 16384);
    if (!memory) {
        snprintf(out, length, "\nGPU tables alloc");
        return;
    }
    IOByteCount contiguous = 0;
    const uint64_t physical = memory->getPhysicalSegment(0, &contiguous, kIOMemoryMapperNone);
    auto *tables = static_cast<uint64_t *>(memory->getBytesNoCopy());
    if (!tables || (reinterpret_cast<uintptr_t>(tables) & (pageBytes - 1)) ||
        !physical || (physical & (pageBytes - 1)) || contiguous < bytes ||
        physical > (UINT64_C(1) << addressBits) - bytes) {
        snprintf(out, length, "\nGPU tables backing");
        memory->release();
        return;
    }

    // A650 GMU RAM windows from lmi mode 27. This is a software-only layout
    // test with zeroed payloads. Firmware permissions need separate validation.
    const uint64_t payload = physical + poolBytes;
    const ArmSmmu4KRange ranges[] = {
        {0x00004000, payload,           0x08000, ArmSmmu4KRead | ArmSmmu4KExecute | ArmSmmu4KPrivileged, 0, 2},
        {0x00144000, payload + 0x08000, 0x13000, rw, 0, 2},
        {0x00157000, payload + 0x1b000, 0x09000, rw, 0, 2},
        {0x60000000, payload + 0x24000, 0x01000, rw, 0, 2},
        {0x60001000, payload + 0x25000, 0x05000, rw, 0, 2},
    };
    constexpr size_t rangeCount = sizeof(ranges) / sizeof(ranges[0]);
    bzero(tables, bytes);
    const ArmSmmu4KConfig config = {addressBits, addressBits, physical, payloadPages};
    ArmSmmu4KResult result = {};
    const char *stage = "build";
    auto status = ArmSmmu4KBuild(&config, ranges, rangeCount, tables, poolPages, &result);

    const ArmSmmu4KTableMemory backing = {1, {{tables, physical, poolPages}, {}}};
    ArmSmmu4KTableIo io = {};
    if (!status) {
        stage = "bind";
        status = ArmSmmu4KBindTableMemory(&backing, &io);
    }
    // ID0/ID2 from v112. These are inputs to the encoder, with no live MMIO.
    const ArmSmmu4KContextConfig context = {&config, nullptr, &result, nullptr,
                                            0x4c017e06, 0x5511, 1, 0, 1, 0};
    ArmSmmu4KContextImage image = {};
    if (!status) {
        stage = "encode";
        status = ArmSmmu4KEncodeContext(&context, &image);
    }
    unsigned char visited[poolPages] = {};
    const ArmSmmu4KAuditRegion region = {ranges, rangeCount, poolPages, poolPages * 512,
                                        visited, sizeof(visited)};
    ArmSmmu4KTableAuditResult audit = {};
    if (!status) {
        stage = "audit";
        // Walk the actual backing starting at the address encoded in TTBR0.
        const uint64_t root = image.ttbr0 & UINT64_C(0x0000ffffffffffff);
        status = ArmSmmu4KAuditTables(&io, &config, &result, &region, root, &audit);
        if (!status && (!audit.complete || audit.leaf_pages != payloadPages))
            status = ArmSmmu4KStateMismatch;
    }
    memory->release();
    snprintf(out, length, "\nGPU tables %s rc=%u table/leaf/read=%lu/%lu/%lu tcr=%x",
             status ? stage : "ok", static_cast<unsigned>(status),
             audit.table_pages, audit.leaf_pages, audit.descriptor_reads, image.tcr);
}

} // namespace t970_gpu
