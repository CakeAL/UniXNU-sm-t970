// SPDX-License-Identifier: MIT
#pragma once
#include "A650GmuPower.h"
#include "../T970Touch/BusSnapshot.h"
#include "ArcVotes.h"
#include "GmuRate.h"

namespace t970_gpu {

struct RscSnapshot {
    const char *state = "skip";
    uint32_t gmuBusy = 0;
    uint32_t config = 0, status = 0, busy = 0, irqEnable = 0, irqStatus = 0;
    unsigned idle = 0;
    uint32_t hidden[6] = {}, route[5] = {}, seq[5] = {};
    uint32_t pdcStart = 0, pdcEnable = 0;
    bool tablesRead = false;
    unsigned programmed = 0, restored = 0;
    bool holdParents = false;
    ArcVotes votes;
    GmuRate rate;
};

static uint32_t gmuRscActivity(IOMemoryMap &gmu) {
    using namespace t970_touch;
    // RPMH_CTRL, RSCC_CONTROL_REQ and RSCC_CONTROL_ACK in the GMU window.
    return read(gmu, 0x143a0) | read(gmu, 0x24c1c) | read(gmu, 0x24c20);
}

static bool readRscIdle(IOMemoryMap &rscc, RscSnapshot &result) {
    using namespace t970_touch;
    result.config = read(rscc, 0xc);
    result.status = read(rscc, 0x10);
    result.busy = read(rscc, 0x404);
    if (result.config != 0x4000000a) {
        result.state = "layout";
        return false;
    }

    // lmi DRV0 has ten slots of eight commands. Inspect the same status,
    // control, wait and enable registers without reading or issuing commands.
    result.irqEnable = read(rscc, 0xd00);
    result.irqStatus = read(rscc, 0xd04);
    result.idle = 0;
    for (unsigned slot = 0; slot < 10; ++slot) {
        const unsigned base = 0xd00 + slot * 0x2a0;
        const uint32_t pending = read(rscc, base + 0x10) |
                                 read(rscc, base + 0x14) | read(rscc, base + 0x1c);
        if (read(rscc, base + 0x18) == 1 && !pending) result.idle |= 1u << slot;
    }
    if ((result.status & 0x10000) || result.busy || result.irqStatus || result.idle != 0x3ff) {
        result.state = "busy";
        return false;
    }
    return true;
}

static void readRscTables(IOMemoryMap &rscc, RscSnapshot &result) {
    using namespace t970_touch;
    constexpr unsigned routing[] = {0x2c, 0x400, 0x20, 0x24, 0x28};
    for (unsigned i = 0; i < 6; ++i) result.hidden[i] = read(rscc, 0x34 + i * 4);
    for (unsigned i = 0; i < 5; ++i) {
        result.route[i] = read(rscc, routing[i]);
        result.seq[i] = read(rscc, 0x600 + i * 4);
    }
    result.tablesRead = true;
}

static bool rscRouteMatches(const RscSnapshot &state) {
    constexpr uint32_t hidden[] = {0x82204514, 0, 0x82204510, 0, 0x82204520, 0};
    constexpr uint32_t route[] = {1, 0, 0x4520, 0x4510, 0x4514};
    return !memcmp(state.hidden, hidden, sizeof(hidden)) && !memcmp(state.route, route, sizeof(route));
}

static bool rscCold(const RscSnapshot &state) {
    constexpr uint32_t empty[5] = {};
    return !state.status && !state.irqEnable && state.pdcStart == 0 && state.pdcEnable == 0x100 &&
           rscRouteMatches(state) && !memcmp(state.seq, empty, sizeof(empty));
}

static bool rscStillIdle(IOMemoryMap &gmu, IOMemoryMap &rscc, RscSnapshot &state) {
    using namespace t970_touch;
    return read(gmu, 0x14000) == 1 && !read(gmu, 0x14070) && !gmuRscActivity(gmu) &&
           readRscIdle(rscc, state) && !state.irqEnable;
}

static void pulseRscInit(IOMemoryMap &gmu, IOMemoryMap &cc, IOMemoryMap &rscc,
                         IOMemoryMap &pdc, RscSnapshot &result, unsigned power) {
    using namespace t970_touch;
    RscSnapshot state;
    if (!rscCold(result) || !rscStillIdle(gmu, rscc, state) || state.status) {
        result.state = "refuse";
        return;
    }

    // lmi mode 24, A650 pdc_in_aop. Preserve the inherited hidden commands.
    constexpr uint32_t seq[] = {0xeaaae5a0, 0xe1a1ebab, 0xa2e0a581, 0xecac82e2, 0x0020edad};
    const struct { IOMemoryMap &bank; unsigned offset; uint32_t before, requested; } writes[] = {
        {rscc, 0x10, 0, 0x01000000},
        {rscc, 0x600, 0, seq[0]}, {rscc, 0x604, 0, seq[1]}, {rscc, 0x608, 0, seq[2]},
        {rscc, 0x60c, 0, seq[3]}, {rscc, 0x610, 0, seq[4]},
        {pdc, 0x4520, 0, 0}, {pdc, 0x4500, 0x100, 0x80000001},
    };
    unsigned attempted = 0;
    for (const auto &op : writes) {
        const unsigned bit = 1u << attempted++;
        write(op.bank, op.offset, op.requested);
        if (read(op.bank, op.offset) != op.requested) break;
        result.programmed |= bit;
    }

    result.holdParents = true;
    if (!rscStillIdle(gmu, rscc, state)) {
        result.state = "busy-hold";
        return;
    }
    if (power >= 7 && result.programmed == 0xff) {
        readRscTables(rscc, state);
        if (state.status == 0x01000000 && rscRouteMatches(state) && !memcmp(state.seq, seq, sizeof(seq)) &&
            read(pdc, 0x4520) == 0 && read(pdc, 0x4500) == 0x80000001) {
            result.votes = voteArcMin(gmu, rscc);
        } else {
            result.votes.state = "rsc-profile";
        }
        if (result.votes.holdParents || !rscStillIdle(gmu, rscc, state)) {
            result.state = "arc-hold";
            return;
        }
        if (power >= 8 && result.votes.mx.ack && result.votes.cx.ack) {
            result.rate = pulseGmuRate(gmu, cc, power);
            if (result.rate.holdParents || !rscStillIdle(gmu, rscc, state)) {
                result.state = "rate-hold";
                return;
            }
        }
    }
    for (unsigned i = attempted; i-- > 0;) {
        const auto &op = writes[i];
        write(op.bank, op.offset, op.before);
        if (read(op.bank, op.offset) != op.before) {
            result.state = "restore-hold";
            return;
        }
        result.restored |= 1u << i;
    }
    if (!rscStillIdle(gmu, rscc, state)) {
        result.state = "busy-hold";
        return;
    }
    readRscTables(rscc, state);
    state.pdcStart = read(pdc, 0x4520);
    state.pdcEnable = read(pdc, 0x4500);
    if (!rscCold(state)) {
        result.state = "restore-hold";
        return;
    }
    result.holdParents = false;
    result.state = result.programmed == 0xff ? "ok" : "rollback";
}

// The caller holds CX and all three XO clock branches with CM3 in reset.
static RscSnapshot sampleRsc(IOMemoryMap &gmu, IOMemoryMap &cc, unsigned power) {
    using namespace t970_touch;
    RscSnapshot result;
    result.gmuBusy = gmuRscActivity(gmu);
    if (result.gmuBusy) {
        result.state = "gmu-busy";
        return result;
    }
    const IOOptionBits options = power >= 6 ? 0 : kIOMapReadOnly;
    auto rscc = mapMmio(A650_GPU_BASE_RSCC, 0x10000, options);
    if (!rscc || !rscc->getVirtualAddress()) {
        result.state = "rscc-map";
        return result;
    }
    if (!readRscIdle(*rscc, result)) return result;
    readRscTables(*rscc, result);
    // T970 stock kgsl_gmu_pdc_cfg. The PDC sequencer is a separate resource.
    auto pdc = mapMmio(0x0b290000, 0x10000, options);
    if (!pdc || !pdc->getVirtualAddress()) {
        result.state = "pdc-map";
        return result;
    }
    result.pdcStart = read(*pdc, 0x4520);
    result.pdcEnable = read(*pdc, 0x4500);
    result.state = "read";
    if (power >= 6) pulseRscInit(gmu, cc, *rscc, *pdc, result, power);
    return result;
}

static void reportArcVotes(char *out, unsigned length, const RscSnapshot &rsc,
                           unsigned xoRestored, bool cxRestored) {
    const ArcVotes &v = rsc.votes;
    snprintf(out, length,
        "\nGPU vote %s/%s mx=%s/%x cx=%s/%x irq/ctl/st=%x/%x/%x rsc=%x/%x xo=7/%x cxr=%u",
        rsc.state, v.state, v.mx.state, v.mx.status, v.cx.state, v.cx.status, v.irq, v.control, v.idle,
        rsc.programmed, rsc.restored, xoRestored, cxRestored ? 1u : 0u);
}

static void reportRscInit(char *out, unsigned length, const RscSnapshot &rsc,
                          unsigned xoRestored, bool cxRestored) {
    snprintf(out, length,
        "\nGPU init %s cfg=%x idle=%x wr=%x restore=%x xo=7/%x cx=1/%u",
        rsc.state, rsc.config, rsc.idle, rsc.programmed, rsc.restored, xoRestored, cxRestored ? 1u : 0u);
}

static void reportRsc(char *out, unsigned length, const RscSnapshot &rsc, bool restored) {
    const int used = snprintf(out, length,
        "\nGPU rsc %s cfg/st/busy=%x/%x/%x g=%x irq=%x/%x idle=%x xo=7/7 cx=1/%u",
        rsc.state, rsc.config, rsc.status, rsc.busy, rsc.gmuBusy,
        rsc.irqEnable, rsc.irqStatus, rsc.idle, restored ? 1u : 0u);
    if (!rsc.tablesRead || used < 0 || static_cast<unsigned>(used) >= length) return;
    const auto &h = rsc.hidden;
    const auto &r = rsc.route;
    const auto &s = rsc.seq;
    snprintf(out + used, length - used,
        "\nRSC hidden=%x/%x/%x/%x/%x/%x route=%x/%x/%x/%x/%x seq=%x/%x/%x/%x/%x pdc=%x/%x",
        h[0], h[1], h[2], h[3], h[4], h[5], r[0], r[1], r[2], r[3], r[4],
        s[0], s[1], s[2], s[3], s[4], rsc.pdcStart, rsc.pdcEnable);
}

static void reportRscMode(char *out, unsigned length, const RscSnapshot &rsc, unsigned power,
                          unsigned xoRestored, bool cxRestored) {
    if (power >= 8 && rsc.votes.mx.ack && rsc.votes.cx.ack && !rsc.votes.holdParents) {
        const GmuRate &rate = rsc.rate;
        if (power >= 9 && strcmp(rate.smmu.state, "skip")) {
            const SmmuSnapshot &s = rate.smmu;
            if (power == cbBarMode) {
                snprintf(out, length,
                    "\nGPU cbar %s/%s/%s bar=%x/%x rb=%u va=%x/%x f=%x diff=%x bus=%x/%x rsc=%x/%x xo=%x cxr=%u",
                    s.barState, s.format, rate.state, s.barActive, s.barRestored,
                    s.barRestoreRead ? 1u : 0u, s.va64Active, s.va64After, s.restoreFlags, s.restoreDiff,
                    s.ready, s.restored, rsc.programmed, rsc.restored, xoRestored, cxRestored ? 1u : 0u);
                return;
            }
            if (power >= 10 && strcmp(s.format, "skip")) {
                snprintf(out, length,
                    "\nGPU cbfmt %s/%s va64=%x/%x/%x rb=%u guard=%x/%x diff=%x bus=%x/%x rsc=%x/%x xo=%x cxr=%u"
                    "\nCB guard id=%x/%x f=%x/%x bar/scr/ctl=%x/%x/%x smr=%x",
                    s.format, rate.state, s.va64Before, s.va64Active, s.va64After,
                    s.restoreRead ? 1u : 0u, s.guard.flags(), s.restoreFlags, s.restoreDiff,
                    s.ready, s.restored, rsc.programmed, rsc.restored, xoRestored, cxRestored ? 1u : 0u,
                    s.guard.id0, s.guard.id1, s.guard.gfsr, s.guard.fsr, s.guard.bar, s.guard.scr0,
                    s.guard.sctlr, s.guard.smrs);
                return;
            }
            const int used = snprintf(out, length,
                "\nGPU smmu %s/%s id=%x/%x/%x scr/f=%x/%x sm=%u/%u/%x bus=%x/%x:%x/%x rsc=%x/%x xo=%x cxr=%u",
                s.state, rate.state, s.id0, s.id1, s.id2, s.scr0, s.gfsr,
                s.valid, s.nonzero, s.firstS2cr, s.clock[0], s.clock[1], s.ready, s.restored,
                rsc.programmed, rsc.restored, xoRestored, cxRestored ? 1u : 0u);
            if (s.contextRead && used >= 0 && static_cast<unsigned>(used) < length) {
                const auto &c = s.cb;
                snprintf(out + used, length - used,
                    "\nCB0 bar/attr=%x/%x ctl=%x/%x tt=%x/%x/%x/%x tcr=%x/%x mair=%x/%x fsr=%x far=%x/%x chg=%u",
                    c[0], c[1], c[2], c[3], c[4], c[5], c[6], c[7], c[8], c[9],
                    c[10], c[11], c[12], c[13], c[14], s.changed);
            }
            return;
        }
        snprintf(out, length,
            "\nGPU rate %s/%s hz=%llu cfg=%x/%x/%x cmd=%x gate=%x/%x/%x rsc=%x/%x xo=7/%x cxr=%u",
            rsc.state, rate.state, static_cast<unsigned long long>(rate.parentHz),
            rate.before, rate.active, rate.after, rate.command,
            rate.gateBefore, rate.gateActive, rate.gateAfter, rsc.programmed, rsc.restored,
            xoRestored, cxRestored ? 1u : 0u);
    } else if (power >= 7) {
        reportArcVotes(out, length, rsc, xoRestored, cxRestored);
    } else if (power == 6) {
        reportRscInit(out, length, rsc, xoRestored, cxRestored);
    } else {
        reportRsc(out, length, rsc, cxRestored);
    }
}

} // namespace t970_gpu
