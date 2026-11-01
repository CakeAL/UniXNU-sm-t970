// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include "T970SmmuReport.h"
namespace t970_preflight {
static bool ownsDma(uint64_t base, uint64_t size, uint64_t dma, uint64_t bytes, uint64_t contiguous)
{
  return size && size <= UINT64_MAX - base && bytes && contiguous >= bytes &&
    !(dma & 4095) && dma >= base && bytes <= size && dma - base <= size - bytes;
}
static bool candidate(const t970_smmu::Report &r, uint32_t cbar, uint32_t cba2r, uint32_t sctlr)
{
  if (r.id0 != 0x4c017e57 || r.id1 != 0x6000004a || r.id2 != 0x5111 ||
      !r.geometryValid || r.extendedIds || r.scanned != 87 || r.valid != 1 || r.gfsr ||
      r.streams[4].smr != 0x84020820 || r.streams[4].s2cr != 4) return false;
  if (r.streams[2].smr != 0x4e0 || r.streams[3].smr != 0xe0) return false;
  const unsigned slots[] = {0x55, 0x56};
  for (unsigned slot : slots) {
    if (r.streams[slot].smr || r.streams[slot].s2cr != 0x200ff) return false;
  }
  // Read-only candidate CB0: preserve its complete existing configuration.
  if (cbar != 0x100ff || cba2r != 1 || sctlr != 0xe0) return false;
  for (unsigned i = 0; i < r.scanned; ++i) {
    const auto &s = r.streams[i];
    if (s.valid && ((s.s2cr >> 16) & 3) == 0 && (s.s2cr & 255) == 0) return false;
  }
  return true;
}
}
