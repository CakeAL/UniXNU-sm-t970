// SPDX-License-Identifier: MIT
// Read-only GCC snapshot for the GPU parent clock and GPU branch gate.
// Offsets and the GPLL0 alpha formula follow lmi-gpu-clock.c (MIT). The GCC
// block is always accessible on this board; no PLL, branch or rail write.
#pragma once
#include <stdint.h>
#include "../T970Touch/BusSnapshot.h"

namespace t970_gpu {

static inline uint64_t gpll0Hz(uint32_t l, uint32_t alpha) {
    return 19200000ull * l + ((19200000ull * alpha) >> 16);
}

static void reportClock(char *out, unsigned length, bool writeGate = false) {
    using namespace t970_touch;
    auto gcc = mapMmio(0x100000, 0x80000, writeGate ? 0 : kIOMapReadOnly);
    if (!gcc || !gcc->getVirtualAddress()) {
        snprintf(out, length, "\nGPU clk: mapping failed");
        return;
    }
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
