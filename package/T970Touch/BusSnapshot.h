// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once

#include <IOKit/IODeviceMemory.h>
#include <IOKit/IOLib.h>
#include <kern/clock.h>
#include <kern/thread.h>
#include <machine/machine_routines.h>
#include <pexpert/pexpert.h>
#include "TouchHid.h"

#if defined(T970_TOUCH_HID)
extern "C" void thread_terminate_self(void);
extern "C" void native_t970_touch_down();
extern "C" void native_t970_runtime_report_request();
#endif

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

static void write(IOMemoryMap &map, unsigned offset, uint32_t value) {
    auto *bytes = reinterpret_cast<volatile uint8_t *>(map.getVirtualAddress());
    *reinterpret_cast<volatile uint32_t *>(bytes + offset) = value;
    __asm__ volatile("dsb sy" ::: "memory");
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
    write(map, offset, (read(map, offset) & ~mask) | (value & mask));
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
class ProbeBus {
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
        byte = 0;
        for (unsigned i = 0; i < 8; ++i) {
            if (!bit(true, value)) return false;
            byte = static_cast<uint8_t>((byte << 1) | value);
        }
        return bit(last, value);
    }

    const char *exchange(const uint8_t *command, unsigned commandLength,
                         uint8_t *bytes, unsigned length) {
        if (!writeByte(0x49 << 1)) return "addr-w";
        for (unsigned i = 0; i < commandLength; ++i) {
            if (!writeByte(command[i])) return "command";
        }
        if (!length) return "done";
        if (!start()) return "restart";
        if (!writeByte((0x49 << 1) | 1)) return "addr-r";
        for (; bytesRead < length; ++bytesRead) {
            if (!readByte(bytes[bytesRead], bytesRead + 1 == length)) return "read";
        }
        return "done";
    }

public:
    const char *fault = "none";
    unsigned bytesRead = 0;
    bool stopped = false;

    explicit ProbeBus(IOMemoryMap &gpio) : pins(gpio) {}

    bool transfer(const uint8_t *command, unsigned commandLength,
                  uint8_t *bytes = nullptr, unsigned length = 0) {
        fault = "none";
        bytesRead = 0;
        stopped = false;
        bool started = start();
        stage = started ? exchange(command, commandLength, bytes, length) : "start";
        if (started && strcmp(fault, "arbitration") != 0) {
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
        return !strcmp(stage, "done") && !strcmp(fault, "none") && stopped;
    }

    const char *stage = "idle";
};

// SEC fts1ba90a FIFO as used by the stock T970 driver and Galaxy Tab S6.
struct EventSample {
    unsigned polls = 0;
    unsigned count[4] = {};
    unsigned drags = 0;
    unsigned slot = 0, x = 0, y = 0;
    unsigned echo = 0, irqLow = 0, status = 0;
    unsigned pressed = 0, moved = 0;

    void record(const uint8_t *event) {
        if (event[0] == 0x43 && event[1] == 1 &&
            event[2] == 0xa0 && event[3] == 0 && event[4] == 1) {
            ++echo;
        } else if ((event[0] & 3u) != 0) {
            status = (event[0] << 8) | event[1];
        } else if (unsigned action = event[0] >> 6) {
            slot = (event[0] >> 2) & 15u;
            x = (event[1] << 4) | (event[3] >> 4);
            y = (event[2] << 4) | (event[3] & 15u);
            ++count[action];
            unsigned mask = 1u << slot;
            if (action == 1) {
                pressed |= mask;
                moved &= ~mask;
            } else if (action == 2) {
                moved |= pressed & mask;
            } else {
                if (moved & mask) ++drags;
                pressed &= ~mask;
                moved &= ~mask;
            }
        }
    }
};

static const char *enableScan(ProbeBus &bus) {
    constexpr uint8_t touchFunctions[] = {0x30, 0x61, 0};
    constexpr uint8_t clearFifo = 0x62;
    constexpr uint8_t scanOn[] = {0xa0, 0, 1};
    if (!bus.transfer(touchFunctions, sizeof(touchFunctions))) return "functions";
    IOSleep(10);
    if (!bus.transfer(&clearFifo, 1)) return "clear";
    if (!bus.transfer(scanOn, sizeof(scanOn))) return "scan";
    return nullptr;
}

struct FifoBatch {
    static constexpr unsigned eventSize = 16, capacity = 32;
    uint8_t bytes[capacity * eventSize];
    unsigned count = 0;

    const uint8_t *event(unsigned index) const { return bytes + index * eventSize; }

    const char *readFrom(ProbeBus &bus) {
        constexpr uint8_t readOne = 0x60, readRest = 0x61;
        if (!bus.transfer(&readOne, 1, bytes, eventSize)) return "read";
        unsigned left = bytes[7] & 0x3fu;
        if (left >= capacity) left = capacity - 1;
        count = 1;
        if (left && !bus.transfer(&readRest, 1, bytes + eventSize, left * eventSize)) return "drain";
        count += left;
        return nullptr;
    }
};

static const char *sampleEvents(ProbeBus &bus, IOMemoryMap &irqPin, EventSample &sample) {
    if (const char *failure = enableScan(bus)) return failure;

    uint64_t deadline = 0;
    clock_interval_to_deadline(20, NSEC_PER_SEC, &deadline);
    for (; sample.polls < 500 && mach_absolute_time() < deadline; ++sample.polls) {
        if (!(read(irqPin, 4) & 1u)) ++sample.irqLow;
        FifoBatch batch;
        const char *failure = batch.readFrom(bus);
        for (unsigned i = 0; i < batch.count; ++i) sample.record(batch.event(i));
        if (failure) return failure;
        IOSleep(40);
    }
    return "done";
}

#if defined(T970_TOUCH_HID)
struct SetupReportHold {
    uint16_t contacts = 0;
    uint64_t deadline = 0;
    bool requested = false;

    bool update(uint16_t active) {
        if (requested) return false;
        if (contacts != active) {
            contacts = active;
            deadline = 0;
        }
        if (__builtin_popcount(contacts) != 3) return false;
        if (!deadline) {
            clock_interval_to_deadline(2, NSEC_PER_SEC, &deadline);
            return false;
        }
        requested = mach_absolute_time() >= deadline;
        return requested;
    }
};

static const char *deliverEvents(ProbeBus &bus, IOMemoryMap &irqPin, EventSample &) {
    if (const char *failure = enableScan(bus)) return failure;
    IOLog("T970 touch: FTS scanning\n");
    T970TouchFrame frame;
    bool pending = false;
    unsigned report = 0;
    const bool reportOnHold = PE_parse_boot_argn("t970-setup-report-touch", &report, sizeof(report)) && report == 1;
    SetupReportHold reportHold;
    unsigned idlePolls = 0;
    unsigned failures = 0;
    for (;;) {
        // Read even if IRQ stays high so a missed or masked IRQ cannot stall input.
        if (!(read(irqPin, 4) & 1u) || ++idlePolls >= 16) {
            idlePolls = 0;
            FifoBatch batch;
            if (const char *failure = batch.readFrom(bus)) {
                // Release host contacts after a bus error before trying to recover.
                frame.active = frame.down = 0;
                pending = !t970_touch_hid_frame(frame);
                if (++failures >= 3 || !bus.stopped) return failure;
            } else {
                failures = 0;
                for (unsigned i = 0; i < batch.count; ++i) {
                    if (frame.apply(batch.event(i))) {
                        if (frame.down) native_t970_touch_down();
                        pending = !t970_touch_hid_frame(frame);
                    }
                }
            }
        }
        if (pending) pending = !t970_touch_hid_frame(frame);
        if (reportOnHold && reportHold.update(frame.active)) native_t970_runtime_report_request();
        IOSleep(8);
    }
}
#endif

using Scan = const char *(*)(ProbeBus &, IOMemoryMap &, EventSample &);

static void reportIdentity(char *out, size_t length, Scan scan = nullptr) {
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
    ProbeBus bus(*pins);
    uint8_t bytes[5] = {};
    constexpr uint8_t identityCommand = 0x22;
    constexpr uint8_t expectedId[] = {0x53, 0x54, 0x39, 0x36, 0x03};
    const char *stage = "idle";
    const char *eventStage = "id";
    const char *eventFault = "none";
    bool identityStop = false;
    unsigned identityLength = 0;
    const char *identityFault = "none";
    const char *scanOff = "skip";
    EventSample sample;
    auto irqPin = scan ? mapMmio(0x0f90f000, 0x1000) : OSSharedPtr<IOMemoryMap>{};
    if (idle == 3) {
        writeMasked(*pins, 0x0004, outputLatch, 0);
        writeMasked(*pins, 0x1004, outputLatch, 0);
        if (!((read(*pins, 0x0004) | read(*pins, 0x1004)) & outputLatch)) {
            bool identified = bus.transfer(&identityCommand, 1, bytes, sizeof(bytes));
            stage = bus.stage;
            identityStop = bus.stopped;
            identityLength = bus.bytesRead;
            identityFault = bus.fault;
            if (scan && identified && !memcmp(bytes, expectedId, sizeof(bytes))) {
                if (irqPin && irqPin->getVirtualAddress()) {
                    eventStage = scan(bus, *irqPin, sample);
                    eventFault = bus.fault;
                    if (bus.stopped && strcmp(eventStage, "functions") && strcmp(eventStage, "clear")) {
                        constexpr uint8_t stopScan[] = {0xa0, 0, 0};
                        scanOff = bus.transfer(stopScan, sizeof(stopScan)) ? "ok" : "fail";
                    }
                } else {
                    eventStage = "irq-map";
                }
            }
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
    int written = snprintf(out, length,
                           "\nTouch ID idle=%x stage=%s err=%s n=%u id=%02x%02x%02x%02x%02x stop=%u restore=%u",
                           idle, stage, identityFault, identityLength, bytes[0], bytes[1], bytes[2],
                           bytes[3], bytes[4], identityStop, restored);
    if (scan && written > 0 && static_cast<size_t>(written) < length) {
        snprintf(out + written, length - written,
                 "\nTouch FIFO %s/%s off=%s poll/irq/echo=%u/%u/%u status=%04x"
                 "\nTouch P/M/R/drag=%u/%u/%u/%u last=%u:%u,%u",
                 eventStage, eventFault, scanOff, sample.polls, sample.irqLow, sample.echo, sample.status,
                 sample.count[1], sample.count[2], sample.count[3], sample.drags,
                 sample.slot, sample.x, sample.y);
    }
}

// Qualcomm command DB: offsets are relative to the data following the header.
static bool readTouchRailAddresses(IOMemoryMap &db, uint32_t &analog, uint32_t &digital) {
    constexpr unsigned dbBytes = 0x20000;
    constexpr unsigned dataOffset = 0x90;
    constexpr unsigned entryBytes = 24;
    if (read(db, 4) != 0x0c0330db) return false;

    for (unsigned slot = 0; slot < 8; ++slot) {
        unsigned header = 8 + 16 * slot;
        uint32_t tag = read(db, header);
        if ((tag & 0xffff) != 4) continue; // VRM slave
        unsigned offset = tag >> 16;
        unsigned count = read(db, header + 4) >> 16;
        if ((offset & 3) || offset > dbBytes - dataOffset ||
            count > (dbBytes - dataOffset - offset) / entryBytes) return false;
        for (unsigned i = 0; i < count; ++i) {
            unsigned entry = dataOffset + offset + entryBytes * i;
            if (read(db, entry) != 0x616f646c) continue; // "ldoa"
            uint32_t suffix = read(db, entry + 4);
            if (suffix != 0x3331 && suffix != 0x3431) continue;
            uint32_t address = read(db, entry + 16);
            uint32_t &rail = suffix == 0x3331 ? analog : digital;
            if (rail || (address & 3) || address < 0x40000 || address > 0x4fff4) return false;
            rail = address;
        }
    }
    return analog && digital && analog != digital;
}

static void reportRails(char *out, size_t length) {
    auto db = mapMmio(0x80860000, 0x20000);
    if (!db || !db->getVirtualAddress()) {
        snprintf(out, length, "\nTouch RAIL command DB map failed");
        return;
    }
    uint32_t analog = 0, digital = 0;
    uint32_t version = read(*db, 0);
    if (!readTouchRailAddresses(*db, analog, digital)) {
        snprintf(out, length, "\nTouch RAIL invalid DB ver=%x l13=%x l14=%x", version, analog, digital);
        return;
    }

    // T970 stock DT selects APPS RSC DRV2 with TCS at +0xd00.
    auto rsc = mapMmio(0x18220000, 0x2000);
    if (!rsc || !rsc->getVirtualAddress()) {
        snprintf(out, length, "\nTouch RAIL db=%x l13=%x l14=%x RSC map failed", version, analog, digital);
        return;
    }
    uint32_t id = read(*rsc, 0);
    uint32_t config = read(*rsc, 0x0c);
    if (((config >> 12) & 0x3f) != 8 || ((config >> 27) & 0x1f) != 16) {
        snprintf(out, length, "\nTouch RAIL db=%x l13=%x l14=%x rsc=%x/%x layout mismatch",
                 version, analog, digital, id, config);
        return;
    }

    constexpr unsigned first = 0xd00;
    constexpr unsigned second = first + 0x2a0;
    snprintf(out, length,
             "\nTouch RAIL db=%x l13=%x l14=%x rsc=%x/%x irq=%x/%x"
             "\nTouch TCS st/ctl/en/wait=%x/%x/%x/%x %x/%x/%x/%x",
             version, analog, digital, id, config, read(*rsc, first), read(*rsc, first + 4),
             read(*rsc, first + 0x18), read(*rsc, first + 0x14),
             read(*rsc, first + 0x1c), read(*rsc, first + 0x10),
             read(*rsc, second + 0x18), read(*rsc, second + 0x14),
             read(*rsc, second + 0x1c), read(*rsc, second + 0x10));
}

// APPS RSC DRV2 TCS1 was empty, idle and IRQ-masked in v73. Borrow it
// only under those conditions. A timed-out slot remains armed and masked.
static const char *voteTouchRail(IOMemoryMap &rsc, uint32_t rail, uint32_t millivolts,
                                uint32_t (&status)[3]) {
    constexpr unsigned irqEnable = 0xd00, irqStatus = 0xd04, irqClear = 0xd08;
    constexpr unsigned slot = 0xfa0;
    constexpr unsigned wait = slot + 0x10, control = slot + 0x14;
    constexpr unsigned state = slot + 0x18, enable = slot + 0x1c;
    constexpr uint32_t irq = 2, allCommands = 7, mode = 1u << 16, trigger = 1u << 24;
    constexpr uint32_t writeResponse = 0x10108, completed = 0x10100;
    if ((read(rsc, irqEnable) & 3) != 1 || (read(rsc, irqStatus) & 3) ||
        read(rsc, 0xd18) != 1 || read(rsc, 0xd14) || read(rsc, 0xd1c) || read(rsc, 0xd10) ||
        read(rsc, state) != 1 ||
        read(rsc, control) || read(rsc, enable) || read(rsc, wait)) return "busy";

    // VRM indices: voltage in mV, PMIC5 LDO HPM, then enable.
    const uint32_t address[] = {rail, rail + 8, rail + 4};
    const uint32_t data[] = {millivolts, 7, 1};
    uint32_t saved[3][3];
    for (unsigned i = 0; i < 3; ++i) {
        unsigned cmd = slot + 0x30 + 20 * i;
        for (unsigned j = 0; j < 3; ++j) saved[i][j] = read(rsc, cmd + 4 * j);
        write(rsc, cmd, writeResponse);
        write(rsc, cmd + 4, address[i]);
        write(rsc, cmd + 8, data[i]);
    }
    write(rsc, wait, allCommands);
    write(rsc, enable, allCommands);
    writeMasked(rsc, irqEnable, irq, irq);
    write(rsc, control, mode);

    bool ready = read(rsc, control) == mode && read(rsc, enable) == allCommands &&
                 read(rsc, wait) == allCommands && (read(rsc, irqEnable) & irq);
    for (unsigned i = 0; i < 3; ++i) {
        unsigned cmd = slot + 0x30 + 20 * i;
        ready &= read(rsc, cmd) == writeResponse && read(rsc, cmd + 4) == address[i] &&
                 read(rsc, cmd + 8) == data[i];
    }
    const char *result = "readback";
    if (ready) {
        write(rsc, control, mode | trigger);
        bool finished = false;
        for (unsigned us = 0; us < 10000; ++us) {
            if ((read(rsc, irqStatus) & irq) && (read(rsc, state) & 1)) {
                finished = true;
                break;
            }
            IODelay(1);
        }
        bool acknowledged = true;
        for (unsigned i = 0; i < 3; ++i) {
            status[i] = read(rsc, slot + 0x3c + 20 * i);
            acknowledged &= (status[i] & completed) == completed;
        }
        if (!finished) {
            writeMasked(rsc, irqEnable, irq, 0);
            return (read(rsc, irqEnable) & irq) ? "timeout-irq" : "timeout";
        }
        result = acknowledged ? "ack" : "no-ack";
    }

    write(rsc, control, mode);
    if (read(rsc, control) != mode) {
        writeMasked(rsc, irqEnable, irq, 0);
        return "restore-trigger";
    }
    write(rsc, control, 0);
    if (read(rsc, control)) {
        writeMasked(rsc, irqEnable, irq, 0);
        return "restore-mode";
    }
    writeMasked(rsc, irqEnable, irq, 0);
    write(rsc, irqClear, irq);
    write(rsc, enable, 0);
    write(rsc, wait, 0);
    bool restored = !(read(rsc, irqEnable) & irq) && !(read(rsc, irqStatus) & irq) &&
                    !read(rsc, enable) && !read(rsc, wait);
    for (unsigned i = 0; i < 3; ++i) {
        unsigned cmd = slot + 0x30 + 20 * i;
        for (unsigned j = 0; j < 3; ++j) {
            write(rsc, cmd + 4 * j, saved[i][j]);
            restored &= read(rsc, cmd + 4 * j) == saved[i][j];
        }
    }
    return restored ? result : "restore";
}

static void reportPoweredIdentity(char *out, size_t length, Scan scan) {
    auto db = mapMmio(0x80860000, 0x20000);
    uint32_t analog = 0, digital = 0;
    if (!db || !db->getVirtualAddress() || read(*db, 0) != 1 || (read(*db, 0x8c) & 1u) ||
        !readTouchRailAddresses(*db, analog, digital) || analog != 0x40a00 || digital != 0x42100) {
        snprintf(out, length, "\nTouch PWR refused DB l13=%x l14=%x", analog, digital);
        return;
    }
    auto rsc = mapMmio(0x18220000, 0x2000, 0);
    if (!rsc || !rsc->getVirtualAddress() || read(*rsc, 0) != 0x20000 || read(*rsc, 0x0c) != 0x800c8104) {
        snprintf(out, length, "\nTouch PWR refused RSC");
        return;
    }

    uint32_t avdd[3] = {}, dvdd[3] = {};
    bool interrupts = ml_set_interrupts_enabled(false);
    const char *a = voteTouchRail(*rsc, analog, 3300, avdd);
    ml_set_interrupts_enabled(interrupts);
    const char *d = "skip";
    if (!strcmp(a, "ack")) {
        IOSleep(1);
        interrupts = ml_set_interrupts_enabled(false);
        d = voteTouchRail(*rsc, digital, 1800, dvdd);
        ml_set_interrupts_enabled(interrupts);
    }
    int written = snprintf(out, length, "\nTouch PWR A=%s:%x/%x/%x D=%s:%x/%x/%x",
                           a, avdd[0], avdd[1], avdd[2], d, dvdd[0], dvdd[1], dvdd[2]);
    // Leave the verified stock voltage/enable votes in place until reset.
    if (!strcmp(d, "ack") && written > 0 && static_cast<size_t>(written) < length) {
        IOSleep(100);
        reportIdentity(out + written, length - written, scan);
    }
}

#if defined(T970_TOUCH_HID)
static void hidWorker(void *, wait_result_t) {
    if (t970_touch_hid_start()) {
        char state[384] = {};
        reportPoweredIdentity(state, sizeof(state), deliverEvents);
        IOLog("T970 touch: FTS worker stopped%s\n", state);
    }
    thread_terminate_self();
}

static void startHid() {
    unsigned enabled = 0, diagnostic = 0;
    if (!PE_parse_boot_argn("t970-touch-hid", &enabled, sizeof(enabled)) || enabled != 1 ||
        PE_parse_boot_argn("t970-touch-bus-report", &diagnostic, sizeof(diagnostic))) return;
    thread_t worker = THREAD_NULL;
    if (kernel_thread_start(hidWorker, nullptr, &worker) == KERN_SUCCESS) {
        thread_deallocate(worker);
    }
}
#endif

// Modes 1–6 cover firmware state, clocks, identity, rail resources, power and events.
static void reportBus(char *out, size_t length) {
    unsigned enabled = 0;
    if (!PE_parse_boot_argn("t970-touch-bus-report", &enabled, sizeof(enabled))) return;
    if (enabled == 3) {
        reportIdentity(out, length);
        return;
    }
    if (enabled == 4) {
        reportRails(out, length);
        return;
    }
    if (enabled == 5 || enabled == 6) {
        reportPoweredIdentity(out, length, enabled == 6 ? sampleEvents : nullptr);
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
