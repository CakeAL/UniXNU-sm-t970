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

// Probe-only software I2C. GPIO12 and GPIO13 are QUP5 lanes 0 and 1.
class IdentityBus {
    static constexpr unsigned sda = 0;
    static constexpr unsigned scl = 0x1000;
    static constexpr uint32_t oe = 1u << 9;
    IOMemoryMap &pins;

    bool high(unsigned pin) { return read(pins, pin + 4) & 1u; }
    void release(unsigned pin) { writeMasked(pins, pin, oe, 0); }
    void low(unsigned pin) { writeMasked(pins, pin, oe, oe); }

    bool raiseClock() {
        release(scl);
        for (unsigned wait = 0; wait < 100; ++wait) {
            if (high(scl)) return true;
            IODelay(1);
        }
        fault = "scl-low";
        return false;
    }

    bool bit(bool released, bool &value, bool checkArbitration = false) {
        if (released) release(sda);
        else low(sda);
        IODelay(5);
        if (!raiseClock()) return false;
        IODelay(5);
        value = high(sda);
        if (checkArbitration && released && !value) {
            fault = "arbitration";
            return false;
        }
        low(scl);
        return true;
    }

    bool start() {
        release(sda);
        IODelay(5);
        if (!raiseClock()) return false;
        IODelay(5);
        if (!high(sda)) {
            fault = "sda-low";
            return false;
        }
        low(sda);
        IODelay(5);
        low(scl);
        return true;
    }

    bool writeByte(uint8_t byte) {
        bool value;
        for (unsigned mask = 0x80; mask; mask >>= 1) {
            if (!bit((byte & mask) != 0, value, true)) return false;
        }
        if (!bit(true, value)) return false;
        if (!value) return true;
        fault = "nack";
        return false;
    }

    bool readByte(uint8_t &byte, bool last) {
        bool value;
        for (unsigned i = 0; i < 8; ++i) {
            if (!bit(true, value)) return false;
            byte = static_cast<uint8_t>((byte << 1) | value);
        }
        return bit(last, value);
    }

    const char *readIdentity(uint8_t (&bytes)[5]) {
        if (!writeByte(0x49 << 1)) return "addr-w";
        if (!writeByte(0x22)) return "command";
        if (!start()) return "restart";
        if (!writeByte((0x49 << 1) | 1)) return "addr-r";
        for (; bytesRead < sizeof(bytes); ++bytesRead) {
            if (!readByte(bytes[bytesRead], bytesRead + 1 == sizeof(bytes))) return "read";
        }
        return "done";
    }

public:
    const char *fault = "none";
    unsigned bytesRead = 0;
    bool stopped = false;

    explicit IdentityBus(IOMemoryMap &gpio) : pins(gpio) {}

    const char *transfer(uint8_t (&bytes)[5]) {
        if (!start()) return "start";
        const char *stage = readIdentity(bytes);
        if (strcmp(fault, "arbitration") != 0) {
            low(scl);
            low(sda);
            IODelay(5);
            if (raiseClock()) {
                IODelay(5);
                release(sda);
                IODelay(5);
                stopped = high(sda);
            }
        }
        release(sda);
        release(scl);
        return stage;
    }
};

static void reportIdentity(char *out, size_t length) {
    auto gcc = mapMmio(0x100000, 0x53000);
    if (!gcc || !gcc->getVirtualAddress() ||
        (read(*gcc, voteReg) & seVote) || !(read(*gcc, seBranch) & clockOff)) {
        snprintf(out, length, "\nTouch ID refused SE5 active or unknown");
        return;
    }
    auto pins = mapMmio(0x0f90c000, 0x2000, 0);
    if (!pins || !pins->getVirtualAddress()) {
        snprintf(out, length, "\nTouch ID TLMM map failed");
        return;
    }
    uint32_t sdaConfig = read(*pins, 0x0000);
    uint32_t sclConfig = read(*pins, 0x1000);
    if (sdaConfig != 1 || sclConfig != 1) {
        snprintf(out, length, "\nTouch ID refused gpio=%x/%x", sdaConfig, sclConfig);
        return;
    }

    // Begin with both pins as inputs and remove their weak pull-downs. The
    // board's own pull-ups must release both lines before any output is used.
    constexpr uint32_t pull = 3;
    constexpr uint32_t outputLatch = 1u << 1;
    uint32_t sdaLatch = read(*pins, 0x0004) & outputLatch;
    uint32_t sclLatch = read(*pins, 0x1004) & outputLatch;
    writeMasked(*pins, 0x0000, pull, 0);
    writeMasked(*pins, 0x1000, pull, 0);
    IODelay(100);
    unsigned idle = ((read(*pins, 0x0004) & 1u) << 1) | (read(*pins, 0x1004) & 1u);
    IdentityBus bus(*pins);
    uint8_t bytes[5] = {};
    const char *stage = "idle";
    if (idle == 3) {
        writeMasked(*pins, 0x0004, outputLatch, 0);
        writeMasked(*pins, 0x1004, outputLatch, 0);
        if (!((read(*pins, 0x0004) | read(*pins, 0x1004)) & outputLatch)) {
            stage = bus.transfer(bytes);
        } else {
            stage = "latch";
        }
        writeMasked(*pins, 0x0004, outputLatch, sdaLatch);
        writeMasked(*pins, 0x1004, outputLatch, sclLatch);
    }
    writeMasked(*pins, 0x0000, pull, sdaConfig);
    writeMasked(*pins, 0x1000, pull, sclConfig);
    bool restored = read(*pins, 0x0000) == sdaConfig && read(*pins, 0x1000) == sclConfig &&
                    (read(*pins, 0x0004) & outputLatch) == sdaLatch &&
                    (read(*pins, 0x1004) & outputLatch) == sclLatch;
    snprintf(out, length,
             "\nTouch ID idle=%x stage=%s err=%s n=%u id=%02x%02x%02x%02x%02x stop=%u restore=%u",
             idle, stage, bus.fault, bus.bytesRead, bytes[0], bytes[1], bytes[2], bytes[3], bytes[4],
             bus.stopped, restored);
}

// Mode 1 samples firmware state, mode 2 probes clocks, and mode 3 reads ID.
static void reportBus(char *out, size_t length) {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-touch-bus-report", &enabled, sizeof(enabled))) return;
    if (enabled == 3) {
        reportIdentity(out, length);
        return;
    }
    if (enabled != 1 && enabled != 2) return;

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
