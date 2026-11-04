// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once

#include <IOKit/IODeviceMemory.h>
#include <pexpert/pexpert.h>

namespace t970_touch {

static OSSharedPtr<IOMemoryMap> mapReadOnly(uint64_t base, uint64_t length) {
    OSSharedPtr<IODeviceMemory> memory(IODeviceMemory::withRange(base, length), OSNoRetain);
    if (!memory) return {};
    return OSSharedPtr<IOMemoryMap>(memory->map(kIOMapAnywhere | kIOMapInhibitCache | kIOMapReadOnly),
                                    OSNoRetain);
}

static uint32_t read(IOMemoryMap &map, unsigned offset) {
    auto *bytes = reinterpret_cast<const volatile uint8_t *>(map.getVirtualAddress());
    return *reinterpret_cast<const volatile uint32_t *>(bytes + offset);
}

// Report firmware state without changing GPIOs, clock votes or GENI state.
static void reportBus(char *out, size_t length) {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-touch-bus-report", &enabled, sizeof(enabled)) || enabled != 1) return;

    // SM8250 GCC: SE5, wrapper 0 master AHB and wrapper 0 slave AHB.
    constexpr unsigned clockOff = 1u << 31;
    auto gcc = mapReadOnly(0x100000, 0x53000);
    if (!gcc || !gcc->getVirtualAddress()) {
        snprintf(out, length, "\nTouch RO: GCC map failed");
        return;
    }
    uint32_t votes = read(*gcc, 0x52008);
    uint32_t seClock = read(*gcc, 0x175fc);
    uint32_t masterClock = read(*gcc, 0x17004);
    uint32_t slaveClock = read(*gcc, 0x17008);

    // Kona TLMM NORTH, GPIO12/13 are QUP5 and GPIO15 is the IRQ.
    auto pins = mapReadOnly(0x0f90c000, 0x4000);
    if (!pins || !pins->getVirtualAddress()) {
        snprintf(out, length, "\nTouch RO: TLMM map failed clk=%x/%x/%x", seClock, masterClock, slaveClock);
        return;
    }
    uint32_t sclSdaA = read(*pins, 0x0000);
    uint32_t sclSdaB = read(*pins, 0x1000);
    uint32_t irqConfig = read(*pins, 0x3000);
    unsigned levels = ((read(*pins, 0x0004) & 1u) << 2) |
                      ((read(*pins, 0x1004) & 1u) << 1) |
                      (read(*pins, 0x3004) & 1u);

    uint32_t fw = 0, fifo = 0, status = 0;
    const char *engine = "off";
    // A halted wrapper/SE must never be accessed to determine its status.
    if (!((seClock | masterClock | slaveClock) & clockOff)) {
        auto geni = mapReadOnly(0x994000, 0x4000);
        engine = "map-fail";
        if (geni && geni->getVirtualAddress()) {
            fw = read(*geni, 0x68);
            fifo = read(*geni, 0x64) & 1u;
            status = read(*geni, 0x40);
            engine = "read";
        }
    }
    snprintf(out, length,
             "\nTouch RO vote=%x clk=%x/%x/%x gpio=%x/%x/%x lv=%x SE=%s fw=%x fifoOff=%u st=%x",
             votes, seClock, masterClock, slaveClock, sclSdaA, sclSdaB, irqConfig,
             levels, engine, fw, fifo, status);
}

} // namespace t970_touch
