// SPDX-License-Identifier: MIT
// GCC parent clock snapshot and diagnostic GPU power handoff report.
// GPLL0 offsets and alpha formula follow lmi-gpu-clock.c (MIT).
#pragma once
#include <stdint.h>
#include "../T970Touch/BusSnapshot.h"
#include "GmuRate.h"
#ifdef T970_GPU_POWER_SNAPSHOT
#include "A650GmuPower.h"
#include "RscSnapshot.h"
#endif

namespace t970_gpu {

#ifdef T970_GPU_POWER_SNAPSHOT
static bool cfgAhbReady(uint32_t cfg) {
    return cfg != UINT32_MAX && A650GpuCfgAhbIsEnabled(cfg) && A650GpuClockIsOn(cfg);
}

static void reportPower(char *out, unsigned length, IOMemoryMap &gcc) {
    using namespace t970_touch;
    constexpr unsigned gpu = A650_GPU_BASE_GCC_GPU - 0x100000;
    const uint32_t cfg = read(gcc, gpu + A650_GCC_GPU_CFG_AHB);
    const uint32_t memnoc = read(gcc, gpu + A650_GCC_GPU_MEMNOC_GFX);
    const uint32_t dvm = read(gcc, gpu + A650_GCC_GPU_SNOC_DVM_GFX);
    const uint32_t axi = read(gcc, gpu + A650_GCC_DDRSS_GPU_AXI);
    const int used = snprintf(out, length, "\nGPU pwr cfg/mem/dvm/axi=%x/%x/%x/%x",
                              cfg, memnoc, dvm, axi);
    if (used < 0 || static_cast<unsigned>(used) >= length) return;
    out += used;
    length -= used;

    // Require both the CFG AHB enable vote and an active clock before GPUCC.
    if (!cfgAhbReady(cfg)) {
        snprintf(out, length, " cc=skip");
        return;
    }
    auto cc = mapMmio(A650_GPU_BASE_GPUCC, 0x9000, kIOMapReadOnly);
    if (!cc || !cc->getVirtualAddress()) {
        snprintf(out, length, " cc=map-fail");
        return;
    }
    snprintf(out, length, " cx/hw/gx/ahb/gmu/smmu=%x/%x/%x/%x/%x/%x",
             read(*cc, A650_CC_CX_GDSCR), read(*cc, A650_CC_CX_GDS_HW_CTRL),
             read(*cc, A650_CC_GX_GDSCR), read(*cc, A650_CC_AHB_CLK),
             read(*cc, A650_CC_CX_GMU_CLK), read(*cc, A650_CC_SMMU_VOTE_CLK));
}

struct CxState {
    uint32_t sw, hw;

    bool valid() const { return sw != UINT32_MAX && hw != UINT32_MAX; }
    bool off() const { return valid() && !A650GpuGdscIsOn(sw | hw); }
    bool on() const { return valid() && A650GpuGdscIsOn(hw) && !(sw & A650_GDSC_SW_COLLAPSE); }
};

static CxState sampleCx(IOMemoryMap &cc) {
    return {t970_touch::read(cc, A650_CC_CX_GDSCR), t970_touch::read(cc, A650_CC_CX_GDS_HW_CTRL)};
}

static CxState waitCx(IOMemoryMap &cc, bool powerOn) {
    IODelay(1);
    CxState state = sampleCx(cc);
    for (unsigned us = 0; us < A650_GDSC_POLL_US; us += 10) {
        if (!state.valid() || (powerOn ? state.on() : state.off())) break;
        IODelay(10);
        state = sampleCx(cc);
    }
    return state;
}

struct GmuSnapshot {
    const char *state = "skip";
    uint32_t reset = 0;
    uint32_t fwInit = 0;
    uint32_t counterBefore = 0;
    uint32_t counterAfter = 0;
    RscSnapshot rsc;
};

static GmuSnapshot sampleGmu(IOMemoryMap &cc, const unsigned (&branches)[3], unsigned power) {
    using namespace t970_touch;
    GmuSnapshot result;
    if (!sampleCx(cc).on()) return result;
    for (const unsigned offset : branches) {
        if (!cfgAhbReady(read(cc, offset))) return result;
    }
    // lmi mode 4, with the cold FW_INIT guard from its RSC probe.
    auto gmu = mapMmio(A650_GPU_BASE_GMU, 0x30000, power >= 7 ? 0 : kIOMapReadOnly);
    if (!gmu || !gmu->getVirtualAddress()) {
        result.state = "map-fail";
        return result;
    }
    result.reset = read(*gmu, 0x14000);
    if (result.reset != 1) {
        result.state = "reset";
        return result;
    }
    result.fwInit = read(*gmu, 0x14070);
    if (result.fwInit != 0) {
        result.state = "fw";
        return result;
    }
    result.counterBefore = read(*gmu, 0x14220);
    IODelay(1000);
    result.counterAfter = read(*gmu, 0x14220);
    result.state = "read";
    if (power >= 5 && result.counterBefore != result.counterAfter) result.rsc = sampleRsc(*gmu, cc, power);
    return result;
}

struct XoResult {
    uint32_t cmd, cfg;
    uint32_t active[3] = {};
    unsigned ready = 0;
    unsigned restored = 0;
    bool canReleaseCx = true;
    GmuSnapshot gmu;
};

static XoResult pulseXoClocks(IOMemoryMap &cc, unsigned power) {
    using namespace t970_touch;
    constexpr unsigned offsets[] = {A650_CC_AHB_CLK, A650_CC_CXO_CLK, A650_CC_CX_GMU_CLK};
    constexpr uint32_t enable = A650_CBCR_ENABLE;
    XoResult result{};
    result.cmd = read(cc, A650_CC_GMU_RCGR);
    result.cfg = read(cc, A650_CC_GMU_RCGR + 4);
    // lmi clock_probe: leave the inherited XO source and divider alone.
    if (result.cmd == UINT32_MAX || (result.cmd & A650_RCG_CMD_UPDATE) ||
        (result.cfg & 0x371fu) != 1) return result;

    uint32_t before[3] = {};
    unsigned visited = 0;
    for (unsigned i = 0; i < 3; ++i) {
        if (!sampleCx(cc).on()) break;
        before[i] = read(cc, offsets[i]);
        if (before[i] == UINT32_MAX) break;
        const unsigned bit = 1u << i;
        visited |= bit;
        if (!(before[i] & enable)) write(cc, offsets[i], before[i] | enable);
        IODelay(10);
        uint32_t value = read(cc, offsets[i]);
        // AHB uses BRANCH_HALT_DELAY. Confirm its enable vote; CXO and
        // CX GMU also need a running clock before advancing.
        for (unsigned us = 0; i && us < 500 && value != UINT32_MAX &&
                              !A650GpuClockIsOn(value); us += 10) {
            IODelay(10);
            value = read(cc, offsets[i]);
        }
        result.active[i] = value;
        if (value == UINT32_MAX || !(value & enable) || (i && !A650GpuClockIsOn(value))) break;
        result.ready |= bit;
    }
    if (power >= 4 && result.ready == 7) result.gmu = sampleGmu(cc, offsets, power);
    if (result.gmu.rsc.holdParents) {
        result.canReleaseCx = false;
        return result;
    }
    for (unsigned i = 3; i-- > 0;) {
        const unsigned bit = 1u << i;
        if (!(visited & bit)) continue;
        uint32_t value = read(cc, offsets[i]);
        if (value == UINT32_MAX) break;
        if (!(before[i] & enable) && (value & enable)) {
            write(cc, offsets[i], value & ~enable);
            IODelay(10);
            value = read(cc, offsets[i]);
        }
        if (value == UINT32_MAX || ((value ^ before[i]) & enable)) break;
        result.restored |= bit;
    }
    // Keep parent votes until reset when a child vote cannot be restored.
    result.canReleaseCx = result.restored == visited;
    return result;
}

static void reportCxPulse(char *out, unsigned length, IOMemoryMap &gcc, unsigned power) {
    using namespace t970_touch;
    constexpr unsigned gpu = A650_GPU_BASE_GCC_GPU - 0x100000;
    const uint32_t cfg = read(gcc, gpu + A650_GCC_GPU_CFG_AHB);
    if (!cfgAhbReady(cfg)) {
        snprintf(out, length, "\nGPU cx skip cfg=%x", cfg);
        return;
    }
    auto cc = mapMmio(A650_GPU_BASE_GPUCC, 0x9000, 0);
    if (!cc || !cc->getVirtualAddress()) {
        snprintf(out, length, "\nGPU cx map-fail");
        return;
    }
    const CxState before = sampleCx(*cc);
    const uint32_t gx = read(*cc, A650_CC_GX_GDSCR);
    const uint32_t gxCfg = read(*cc, A650_CC_GX_GDSCR + 4);
    // Linux v6.6 gdsc.c: bit1 HW_CONTROL, bit2 SW_OVERRIDE; GX uses
    // CFG_GDSCR bit16 (power-up complete) in addition to the raw GDSCR.
    constexpr uint32_t swControlMask = 7, gxUpComplete = 1u << 16;
    constexpr uint32_t collapse = A650_GDSC_SW_COLLAPSE;
    if (!before.off() || (before.sw & swControlMask) != collapse ||
        !(gx & collapse) || A650GpuGdscIsOn(gx) || (gxCfg & gxUpComplete)) {
        snprintf(out, length, "\nGPU cx refuse pre=%x/%x gx=%x/%x", before.sw, before.hw, gx, gxCfg);
        return;
    }

    // lmi checkpoint 63 uses the CX software vote. Restore it once any
    // requested branch experiment has released its votes.
    write(*cc, A650_CC_CX_GDSCR, before.sw & ~collapse);
    const CxState during = waitCx(*cc, true);
    const bool clocks = power >= 3 && during.on();
    XoResult xo{};
    if (clocks) xo = pulseXoClocks(*cc, power);
    const bool rscObserved = power >= 5 && xo.ready == 7 && xo.gmu.counterBefore != xo.gmu.counterAfter;
    if (!xo.canReleaseCx) {
        if (power >= 6 && rscObserved) {
            reportRscMode(out, length, xo.gmu.rsc, power, xo.restored, false);
            return;
        }
        snprintf(out, length, "\nGPU xo hold rcg=%x/%x br=%x/%x/%x mask=%x/%x cx=1/0",
                 xo.cmd, xo.cfg, xo.active[0], xo.active[1], xo.active[2], xo.ready, xo.restored);
        return;
    }
    const uint32_t current = clocks ? sampleCx(*cc).sw : during.sw;
    write(*cc, A650_CC_CX_GDSCR, (current == UINT32_MAX ? before.sw : current) | collapse);
    const CxState after = waitCx(*cc, false);
    const bool restored = after.off() && (after.sw & collapse);
    if (rscObserved) {
        reportRscMode(out, length, xo.gmu.rsc, power, xo.restored, restored);
        return;
    }
    if (power >= 4 && xo.ready == 7) {
        const GmuSnapshot &gmu = xo.gmu;
        snprintf(out, length, "\nGPU gmu %s reset=%x fw=%x ao=%x/%x xo=%x/%x cx=1/%u",
                 gmu.state, gmu.reset, gmu.fwInit, gmu.counterBefore, gmu.counterAfter,
                 xo.ready, xo.restored, restored ? 1u : 0u);
        return;
    }
    if (clocks) {
        snprintf(out, length, "\nGPU xo rcg=%x/%x br=%x/%x/%x mask=%x/%x cx=1/%u",
                 xo.cmd, xo.cfg, xo.active[0], xo.active[1], xo.active[2], xo.ready, xo.restored,
                 restored ? 1u : 0u);
        return;
    }
    snprintf(out, length, "\nGPU cx pre=%x/%x on=%x/%x end=%x/%x ack=%u restore=%u",
             before.sw, before.hw, during.sw, during.hw, after.sw, after.hw,
             during.on() ? 1u : 0u, restored ? 1u : 0u);
}
#endif

static void reportClock(char *out, unsigned length, bool writeGate, unsigned power) {
    using namespace t970_touch;
    if (power) writeGate = false;
    auto gcc = mapMmio(0x100000, 0x80000, writeGate ? 0 : kIOMapReadOnly);
    if (!gcc || !gcc->getVirtualAddress()) {
        snprintf(out, length, "\nGPU clk: mapping failed");
        return;
    }
#ifdef T970_GPU_POWER_SNAPSHOT
    if (power) {
        if (power == 1) reportPower(out, length, *gcc);
        else reportCxPulse(out, length, *gcc, power);
        return;
    }
#endif
    uint32_t mode = read(*gcc, 0x0), l = read(*gcc, 0x4), alpha = read(*gcc, 0x40);
    uint32_t user = read(*gcc, 0xc), status = read(*gcc, 0x38), branch = read(*gcc, 0x52000);
    const bool running = gpll0Running(mode, status);
    unsigned postDiv = (user >> 8) & 15u;
    size_t used = snprintf(out, length,
             "\nGPU clk gpl0=%x/%x/%x/%x branch=%x run=%u post=%u hz=%llu",
             mode, l, alpha, status, branch, running ? 1u : 0u, postDiv,
             static_cast<unsigned long long>(gpll0Hz(l, alpha)));
    if (!writeGate || used >= length) return;
    // lmi-gpu-clock.c: force the GPU-only divided gate, confirm it sticks,
    // then restore the exact original bit. No PLL, source or rail write.
    constexpr uint32_t divGate = 0x10000u;
    writeMasked(*gcc, 0x52000, divGate, divGate);
    IODelay(10);
    uint32_t during = read(*gcc, 0x52000);
    bool set = (during & divGate) != 0;
    writeMasked(*gcc, 0x52000, divGate, branch & divGate);
    IODelay(10);
    uint32_t after = read(*gcc, 0x52000);
    bool restored = (after & divGate) == (branch & divGate);
    snprintf(out + used, length - used, " div=%u back=%x restore=%u",
             set ? 1u : 0u, during, restored ? 1u : 0u);
}

static unsigned powerMode() {
#ifdef T970_GPU_POWER_SNAPSHOT
    unsigned power = 0;
    if (PE_parse_boot_argn("t970-gpu-p", &power, sizeof(power)) && power >= 1 && power <= 8) return power;
#endif
    return 0;
}

} // namespace t970_gpu
