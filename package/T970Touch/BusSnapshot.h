// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once

#include <IOKit/IODeviceMemory.h>
#include <IOKit/IOLib.h>
#include <pexpert/pexpert.h>

namespace t970_touch {

static OSSharedPtr<IOMemoryMap> mapMmio(uint64_t base, uint64_t length, IOOptionBits options = kIOMapReadOnly) {
    OSSharedPtr<IODeviceMemory> memory(IODeviceMemory::withRange(base, length), OSNoRetain);
    if (!memory) return {};
    return OSSharedPtr<IOMemoryMap>(memory->map(kIOMapAnywhere | kIOMapInhibitCache | options),
                                    OSNoRetain);
}

static uint32_t read(IOMemoryMap &map, unsigned offset) {
    auto *bytes = reinterpret_cast<const volatile uint8_t *>(map.getVirtualAddress());
    return *reinterpret_cast<const volatile uint32_t *>(bytes + offset);
}

// SM8250 GCC wrapper 0 branches. The vote register is shared.
constexpr unsigned voteReg = 0x52008;
constexpr unsigned seBranch = 0x175fc;
constexpr unsigned masterBranch = 0x17004;
constexpr unsigned slaveBranch = 0x17008;
constexpr uint32_t clockOff = 1u << 31;
constexpr uint32_t wrapperVotes = (1u << 6) | (1u << 7);
constexpr uint32_t seVote = 1u << 15;
constexpr uint32_t slaveHwcg = 1u << 1;

static void writeMasked(IOMemoryMap &map, unsigned offset, uint32_t mask, uint32_t value) {
    auto *bytes = reinterpret_cast<volatile uint8_t *>(map.getVirtualAddress());
    auto *reg = reinterpret_cast<volatile uint32_t *>(bytes + offset);
    *reg = (*reg & ~mask) | (value & mask);
    __asm__ volatile("dsb sy" ::: "memory");
}

struct EngineSnapshot {
    const char *state = "off";
    uint32_t firmware = 0;
    uint32_t fifoOff = 0;
    uint32_t status = 0;
};

static bool clocksRunning(IOMemoryMap &gcc) {
    return !((read(gcc, seBranch) | read(gcc, masterBranch) | read(gcc, slaveBranch)) & clockOff);
}

static EngineSnapshot readEngine() {
    auto geni = mapMmio(0x994000, 0x4000);
    if (!geni || !geni->getVirtualAddress()) return {"map-fail"};
    return {"read", read(*geni, 0x68), read(*geni, 0x64) & 1u, read(*geni, 0x40)};
}

// The test only borrows SE5's previously clear vote. It does not enable the
// wrapper itself, change pins, load firmware, or start an I2C command.
static void reportClockProbe(IOMemoryMap &gcc, char *out, size_t length) {
    uint32_t before = read(gcc, voteReg);
    if ((before & (wrapperVotes | seVote)) != wrapperVotes) {
        snprintf(out, length, "\nTouch CLK refused vote=%x", before);
        return;
    }
    uint32_t originalSlave = read(gcc, slaveBranch);
    bool ungateSlave = (originalSlave & (clockOff | slaveHwcg)) == (clockOff | slaveHwcg);
    writeMasked(gcc, voteReg, seVote, seVote);
    if (ungateSlave) writeMasked(gcc, slaveBranch, slaveHwcg, 0);

    for (unsigned us = 0; us < 250 && !clocksRunning(gcc); ++us) IODelay(1);
    uint32_t during = read(gcc, voteReg);
    uint32_t se = read(gcc, seBranch);
    uint32_t master = read(gcc, masterBranch);
    uint32_t slave = read(gcc, slaveBranch);
    EngineSnapshot engine;
    if ((during & (wrapperVotes | seVote)) == (wrapperVotes | seVote) &&
        !((se | master | slave) & clockOff)) engine = readEngine();

    if (ungateSlave) writeMasked(gcc, slaveBranch, slaveHwcg, originalSlave);
    writeMasked(gcc, voteReg, seVote, before);
    uint32_t after = read(gcc, voteReg);
    bool restored = (after & seVote) == (before & seVote) &&
                    (read(gcc, slaveBranch) & slaveHwcg) == (originalSlave & slaveHwcg);
    snprintf(out, length,
             "\nTouch CLK vote=%x/%x/%x clk=%x/%x/%x restore=%u SE=%s fw=%x fifoOff=%u st=%x",
             before, during, after, se, master, slave, restored, engine.state,
             engine.firmware, engine.fifoOff, engine.status);
}

// Mode 1 samples firmware state. Mode 2 temporarily enables clock access.
static void reportBus(char *out, size_t length) {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-touch-bus-report", &enabled, sizeof(enabled)) ||
        (enabled != 1 && enabled != 2)) return;

    auto gcc = mapMmio(0x100000, 0x53000, enabled == 1 ? kIOMapReadOnly : 0);
    if (!gcc || !gcc->getVirtualAddress()) {
        snprintf(out, length, "\nTouch RO: GCC map failed");
        return;
    }
    if (enabled == 2) {
        reportClockProbe(*gcc, out, length);
        return;
    }
    uint32_t votes = read(*gcc, voteReg);
    uint32_t seClock = read(*gcc, seBranch);
    uint32_t masterClock = read(*gcc, masterBranch);
    uint32_t slaveClock = read(*gcc, slaveBranch);

    // Kona TLMM NORTH, GPIO12/13 are QUP5 and GPIO15 is the IRQ.
    auto pins = mapMmio(0x0f90c000, 0x4000);
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

    EngineSnapshot engine;
    if (!((seClock | masterClock | slaveClock) & clockOff)) engine = readEngine();
    snprintf(out, length,
             "\nTouch RO vote=%x clk=%x/%x/%x gpio=%x/%x/%x lv=%x SE=%s fw=%x fifoOff=%u st=%x",
             votes, seClock, masterClock, slaveClock, sclSdaA, sclSdaB, irqConfig,
             levels, engine.state, engine.firmware, engine.fifoOff, engine.status);
}

} // namespace t970_touch
