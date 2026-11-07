// SPDX-License-Identifier: MIT
// GCC parent clock snapshot and diagnostic GPU power handoff report.
// GPLL0 offsets and alpha formula follow lmi-gpu-clock.c (MIT).
#pragma once
#include <stdint.h>
#include "../T970Touch/BusSnapshot.h"
#ifdef T970_GPU_POWER_SNAPSHOT
#include "A650GmuPower.h"
#endif

namespace t970_gpu {

static inline uint64_t gpll0Hz(uint32_t l, uint32_t alpha) {
    return 19200000ull * l + ((19200000ull * alpha) >> 16);
}

#ifdef T970_GPU_POWER_SNAPSHOT
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
    if (cfg == UINT32_MAX || !A650GpuCfgAhbIsEnabled(cfg) || !A650GpuClockIsOn(cfg)) {
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
#endif

static void reportClock(char *out, unsigned length, bool writeGate = false) {
    using namespace t970_touch;
#ifdef T970_GPU_POWER_SNAPSHOT
    unsigned power = 0;
    const bool powerSnapshot = PE_parse_boot_argn("t970-gpu-p", &power, sizeof(power)) && power == 1;
    if (powerSnapshot) writeGate = false;
#endif
    auto gcc = mapMmio(0x100000, 0x80000, writeGate ? 0 : kIOMapReadOnly);
    if (!gcc || !gcc->getVirtualAddress()) {
        snprintf(out, length, "\nGPU clk: mapping failed");
        return;
    }
#ifdef T970_GPU_POWER_SNAPSHOT
    if (powerSnapshot) {
        reportPower(out, length, *gcc);
        return;
    }
#endif
    uint32_t mode = read(*gcc, 0x0), l = read(*gcc, 0x4), alpha = read(*gcc, 0x40);
    uint32_t user = read(*gcc, 0xc), status = read(*gcc, 0x38), branch = read(*gcc, 0x52000);
    unsigned running = (mode & 0x100000u) ? ((mode & 0x40000000u) != 0) : (status & 1u);
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

} // namespace t970_gpu
