// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>
#include "../T970Touch/BusSnapshot.h"
#ifdef T970_GPU_POWER_SNAPSHOT
#include "A650GmuPower.h"
#include "SmmuSnapshot.h"
#endif

namespace t970_gpu {

static inline uint64_t gpll0Hz(uint32_t l, uint32_t alpha) {
    return 19200000ull * l + ((19200000ull * alpha) >> 16);
}

static inline bool gpll0Running(uint32_t mode, uint32_t opmode) {
    return (mode & 0x100000u) ? (mode & 0x40000000u) != 0 : (opmode & 1u) != 0;
}

#ifdef T970_GPU_POWER_SNAPSHOT
struct GmuRate {
    const char *state = "skip";
    uint64_t parentHz = 0;
    uint32_t before = 0, active = 0, after = 0, command = 0;
    uint32_t gateBefore = 0, gateActive = 0, gateAfter = 0;
    bool holdParents = false;
    SmmuSnapshot smmu;
};

static bool coldGmu(IOMemoryMap &gmu) {
    return t970_touch::read(gmu, 0x14000) == 1 && !t970_touch::read(gmu, 0x14070);
}

static bool updateGmuRcg(IOMemoryMap &cc, uint32_t cfg, uint32_t &command) {
    using namespace t970_touch;
    command = read(cc, A650_CC_GMU_RCGR);
    if (command == UINT32_MAX || (command & A650_RCG_CMD_UPDATE)) return false;
    write(cc, A650_CC_GMU_RCGR + 4, cfg);
    write(cc, A650_CC_GMU_RCGR, command | A650_RCG_CMD_UPDATE);
    for (unsigned us = 0; us < 500; ++us) {
        command = read(cc, A650_CC_GMU_RCGR);
        if (command != UINT32_MAX && !(command & A650_RCG_CMD_UPDATE)) return true;
        IODelay(1);
    }
    return false;
}

// lmi mode 26. The caller holds the verified ARC votes, CX and XO clocks.
static GmuRate pulseGmuRate(IOMemoryMap &gmu, IOMemoryMap &cc, unsigned power) {
    using namespace t970_touch;
    GmuRate result;
    result.state = "gcc-map";
    auto gcc = mapMmio(0x100000, 0x80000, 0);
    if (!gcc || !gcc->getVirtualAddress()) return result;
    constexpr unsigned gateReg = A650_GPU_BASE_GCC_VOTE - 0x100000 + A650_GCC_PLL_VOTE;
    constexpr uint32_t divGate = 1u << 16;
    constexpr uint32_t cfg200 = (1u << 20) | (A650_RCG_SRC_SEL << 8) | A650_RCG_SRC_HID;
    const uint32_t mode = read(*gcc, 0);
    const uint32_t alpha = read(*gcc, 0x40);
    result.parentHz = gpll0Hz(read(*gcc, 4), alpha);
    result.gateBefore = read(*gcc, gateReg);
    result.before = read(cc, A650_CC_GMU_RCGR + 4);
    result.command = read(cc, A650_CC_GMU_RCGR);
    result.state = "pre";
    if (mode == UINT32_MAX || (mode & 0x80000001u) != 0x80000001u ||
        !gpll0Running(mode, read(*gcc, 0x38)) ||
        alpha > 0xffff || ((read(*gcc, 0xc) >> 8) & 15) != 1 ||
        result.parentHz < 599999000 || result.parentHz > 600001000 ||
        result.gateBefore == UINT32_MAX || (result.before & A650_RCG_CFG_CLEAR) != 1 ||
        (result.command & A650_RCG_CMD_UPDATE) || !coldGmu(gmu) ||
        (read(cc, A650_CC_CXO_CLK) & 0x80000001u) != 1 ||
        (read(cc, A650_CC_CX_GMU_CLK) & 0x80000001u) != 1) return result;

    if (!(result.gateBefore & divGate)) write(*gcc, gateReg, result.gateBefore | divGate);
    IODelay(10);
    result.gateActive = read(*gcc, gateReg);
    result.holdParents = true;
    result.state = "gate";
    if (result.gateActive == UINT32_MAX) return result;
    if (result.gateActive & divGate) {
        const uint32_t requested = (result.before & ~A650_RCG_CFG_CLEAR) | cfg200;
        result.state = "update-hold";
        if (!updateGmuRcg(cc, requested, result.command)) return result;
        result.active = read(cc, A650_CC_GMU_RCGR + 4);
        result.state = "xo-hold";
        if (!coldGmu(gmu) || result.active == UINT32_MAX) return result;
        if (power >= 9 && result.active == requested && branchRunning(read(cc, A650_CC_AHB_CLK)) &&
            branchRunning(read(cc, A650_CC_CXO_CLK)) && branchRunning(read(cc, A650_CC_CX_GMU_CLK))) {
            result.smmu = pulseSmmuBus(*gcc, power >= 10);
            if (result.smmu.holdParents) {
                result.state = "smmu-hold";
                return result;
            }
            if (!coldGmu(gmu)) return result;
        }
        const uint32_t original = (result.active & ~A650_RCG_CFG_CLEAR) |
                                  (result.before & A650_RCG_CFG_CLEAR);
        if (!updateGmuRcg(cc, original, result.command)) return result;
        result.after = read(cc, A650_CC_GMU_RCGR + 4);
        if (result.after != result.before) return result;
        result.state = result.active == requested ? "ok" : "readback";
    }
    result.gateAfter = read(*gcc, gateReg);
    const uint32_t gate = result.gateBefore & divGate;
    if (result.gateAfter != UINT32_MAX && (result.gateAfter & divGate) != gate) {
        write(*gcc, gateReg, (result.gateAfter & ~divGate) | gate);
        IODelay(10);
        result.gateAfter = read(*gcc, gateReg);
    }
    result.holdParents = result.gateAfter == UINT32_MAX || (result.gateAfter & divGate) != gate;
    if (result.holdParents) result.state = "gate-hold";
    return result;
}
#endif

} // namespace t970_gpu
