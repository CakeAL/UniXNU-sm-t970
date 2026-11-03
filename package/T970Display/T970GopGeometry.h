// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include <stdint.h>
// Only the photographed T970 firmware scanout mode is qualified for this probe.
static inline bool t970GopGeometry(uint64_t base, uint64_t width, uint64_t height,
                                  uint64_t stride, uint64_t depth, uint64_t rotation) {
    return base == 0x9c000000ULL && width == 2800 && height == 1752 &&
           stride == 11200 && depth == 32 && rotation == 0;
}
