// SPDX-License-Identifier: MIT
#pragma once
#include "ArcResources.h"
#include "A650GmuPower.h"

namespace t970_gpu {

// GPU DRV0 TCS1, as in lmi mode 25. These offsets are relative to GPU RSCC.
constexpr unsigned voteIrqEnable = 0xd00, voteIrqStatus = 0xd04, voteIrqClear = 0xd08;
constexpr unsigned voteSlot = 0xfa0, voteIrq = 2;
constexpr unsigned voteWait = voteSlot + 0x10, voteControl = voteSlot + 0x14;
constexpr unsigned voteIdle = voteSlot + 0x18, voteEnable = voteSlot + 0x1c;
constexpr unsigned voteMessage = voteSlot + 0x30, voteAddress = voteSlot + 0x34;
constexpr unsigned voteData = voteSlot + 0x38, voteStatus = voteSlot + 0x3c;

struct ArcRequest {
    const char *state = "skip";
    uint32_t status = 0;
    bool hold = false;
    bool ack = false;
};

struct ArcVotes {
    const char *state = "skip";
    ArcRequest mx, cx;
    uint32_t irq = 0, control = 0, idle = 0;
    bool holdParents = false;
};

static bool setVoteControl(IOMemoryMap &rscc, uint32_t value) {
    t970_touch::write(rscc, voteControl, value);
    for (unsigned us = 0; us < 200; ++us) {
        if (t970_touch::read(rscc, voteControl) == value) return true;
        IODelay(1);
    }
    return false;
}

static bool voteSlotIdle(IOMemoryMap &rscc) {
    using namespace t970_touch;
    return read(rscc, voteIdle) == 1 && !read(rscc, voteControl) && !read(rscc, voteIrqStatus);
}

static ArcRequest sendArcVote(IOMemoryMap &rscc, uint32_t address, unsigned selector) {
    using namespace t970_touch;
    constexpr uint32_t message = 0x10108, mode = 1u << 16, trigger = 1u << 24;
    constexpr uint32_t complete = 0x10100;
    if (!voteSlotIdle(rscc)) return {"busy", 0, true};
    write(rscc, voteMessage, message);
    write(rscc, voteAddress, address);
    write(rscc, voteData, selector);
    write(rscc, voteWait, 1);
    write(rscc, voteEnable, 1);
    if (read(rscc, voteMessage) != message || read(rscc, voteAddress) != address ||
        read(rscc, voteData) != selector || read(rscc, voteWait) != 1 ||
        read(rscc, voteEnable) != 1) return {"setup"};
    if (!setVoteControl(rscc, mode)) return {"arm", 0, true};
    write(rscc, voteControl, mode | trigger);

    for (unsigned us = 0; us < 200000; us += 100) {
        if ((read(rscc, voteIrqStatus) & voteIrq) && read(rscc, voteIdle) == 1) {
            const uint32_t status = read(rscc, voteStatus);
            if (status == UINT32_MAX || !setVoteControl(rscc, mode) || !setVoteControl(rscc, 0))
                return {"done-hold", status, true};
            write(rscc, voteEnable, 0);
            write(rscc, voteWait, 0);
            write(rscc, voteIrqClear, voteIrq);
            if (!voteSlotIdle(rscc) || read(rscc, voteEnable) || read(rscc, voteWait))
                return {"clear-hold", status, true};
            const bool ack = (status & complete) == complete;
            return {ack ? "ack" : "nack", status, false, ack};
        }
        IODelay(100);
    }
    return {"timeout", read(rscc, voteStatus), true};
}

static ArcVotes voteArcMin(IOMemoryMap &gmu, IOMemoryMap &rscc) {
    using namespace t970_touch;
    ArcVotes result;
    result.state = "db";
    auto db = mapMmio(A650_CMD_DB_BASE, A650_CMD_DB_BYTES, kIOMapReadOnly);
    if (!db || !db->getVirtualAddress()) return result;
    auto bytes = reinterpret_cast<const volatile uint8_t *>(db->getVirtualAddress());
    ArcResource cx, mx;
    if (!parseArc(bytes, A650_CMD_DB_BYTES, "cx.lvl\0", cx) ||
        !parseArc(bytes, A650_CMD_DB_BYTES, "mx.lvl\0", mx) ||
        cx.address != 0x30000 || mx.address != 0x30010 || cx.levels != 9 || mx.levels != 9 ||
        cx.minSvs != 2 || cx.level[2] != 64 || mx.level[1] >= cx.level[2] || mx.level[2] != 128)
        return result;

    result.state = "refuse";
    constexpr unsigned rpmh = 0x143a0;
    if (read(gmu, rpmh) || read(rscc, voteIrqEnable) || !voteSlotIdle(rscc) ||
        read(rscc, voteWait) || read(rscc, voteEnable)) return result;
    const uint32_t saved[] = {read(rscc, voteMessage), read(rscc, voteAddress), read(rscc, voteData)};
    for (const auto word : saved) if (word == UINT32_MAX) return result;

    write(gmu, rpmh, 0xf11);
    if (read(gmu, rpmh) == 0xf11) {
        write(rscc, voteIrqEnable, voteIrq);
        if (read(rscc, voteIrqEnable) == voteIrq) {
            result.mx = sendArcVote(rscc, mx.address, 2);
            if (result.mx.ack) result.cx = sendArcVote(rscc, cx.address, cx.minSvs);
        }
    }
    result.irq = read(rscc, voteIrqStatus);
    result.control = read(rscc, voteControl);
    result.idle = read(rscc, voteIdle);
    result.holdParents = result.mx.hold || result.cx.hold || !voteSlotIdle(rscc);
    if (result.holdParents) {
        result.state = "pending";
        return result;
    }

    // Restore TCS storage and the interface. Completed rail votes persist
    // until reset, even after the command slot itself has been restored.
    write(rscc, voteEnable, 0);
    write(rscc, voteWait, 0);
    write(rscc, voteMessage, saved[0]);
    write(rscc, voteAddress, saved[1]);
    write(rscc, voteData, saved[2]);
    write(rscc, voteIrqEnable, 0);
    write(gmu, rpmh, 0);
    result.holdParents = !voteSlotIdle(rscc) || read(rscc, voteEnable) || read(rscc, voteWait) ||
                         read(rscc, voteMessage) != saved[0] || read(rscc, voteAddress) != saved[1] ||
                         read(rscc, voteData) != saved[2] || read(rscc, voteIrqEnable) || read(gmu, rpmh);
    result.state = result.holdParents ? "restore-hold" : result.cx.ack ? "ok" : "incomplete";
    return result;
}

} // namespace t970_gpu
