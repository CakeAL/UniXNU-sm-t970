// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include "T970TransportPreflight.h"
#include "T970SmrIdTest.h"
namespace t970_nop {
struct Result {
  unsigned stage = 0; // 0 refused; 1 stopping; 2 routes; 3 queue; 4 final gate; 5 submitted; 6 NOP success
  bool submitted = false, success = false, protectedUnchanged = false;
};
// Port retains DMA allocation and mappings through the terminal diagnostic.
// No restore, cancellation or retry after a possible submission. No CB writes.
template <class Port>
static Result run(Port &p, const t970_smmu::Report &before, const t970_ufs::Clocks &clocks,
                  const t970_ufs::Controller &hc, bool owned, uint64_t dma)
{
  Result r;
  auto rd = [&](unsigned off) { return p.smmuRead(off); };
  auto candidate = [&]() { return t970_preflight::candidate(before, rd(0x1000), rd(0x1800), rd(0x80000)); };
  auto ready = [&]() { return (p.hcRead(0x34) & 1) && (p.hcRead(0x30) & 15) == 15 &&
    !p.hcRead(0x58) && !p.hcRead(0x78) && !(p.hcRead(0x20) & 0x71880); };
  if (!owned || !t970_ufs::canReadController(clocks) || hc.state != 1 ||
      before.scr0 != 0x002d0406 || !candidate() || !ready()) return r;
  const auto fresh = t970_smmu::collect(rd, 0x100000);
  if (!t970_smr::sameMappings(before, fresh) || fresh.gfsr) return r;
  const uint32_t fsrBefore = rd(0x80058);
  uint32_t display[4] = {rd(0x1010), rd(0x1810), rd(0x84000), rd(0x84058)};
  auto protectedState = [&]() {
    r.protectedUnchanged = rd(0x810) == 0x84020820 && rd(0xc10) == 4 &&
      rd(0x1010) == display[0] && rd(0x1810) == display[1] &&
      rd(0x84000) == display[2] && rd(0x84058) == display[3] && candidate();
    return r.protectedUnchanged;
  };
  r.stage = 1;
  p.hcWrite(0x24, 0); // Polling only. Do not clear existing UIC/fault status.
  if (p.hcRead(0x24)) return r;
  p.hcWrite(0x60, 0); p.hcWrite(0x80, 0);
  if (!p.wait(0x60, 1, 0) || !p.wait(0x80, 1, 0) || !ready()) return r;
  r.stage = 2;
  const unsigned slots[2] = {0x55, 0x56};
  const uint32_t sids[2] = {0xe0, 0x4e0};
  // Route only the two board candidates; exact SID masks, existing disabled CB0.
  // Install S2CR while both SMRs are still invalid, verify before VALID.
  for (unsigned i = 0; i < 2; ++i) {
    unsigned smr = 0x800 + 4 * slots[i], s2cr = 0xc00 + 4 * slots[i];
    if (rd(smr) || rd(s2cr) != 0x200ff || !protectedState()) return r;
    p.smmuWrite(s2cr, 0);
    if (rd(s2cr) || rd(smr) || rd(0x48) || !protectedState()) return r;
    p.smmuWrite(smr, 0x80000000U | sids[i]);
    if (rd(smr) != (0x80000000U | sids[i]) || rd(s2cr)) return r;
  }
  auto expected = before;
  for (unsigned i = 0; i < 2; ++i) {
    expected.streams[slots[i]].smr = 0x80000000U | sids[i];
    expected.streams[slots[i]].s2cr = 0;
  }
  const auto installed = t970_smmu::collect(rd, 0x100000);
  if (!t970_smr::sameMappings(expected, installed) || installed.gfsr || !protectedState()) return r;
  r.stage = 3;
  p.hcWrite(0x50, uint32_t(dma)); p.hcWrite(0x54, uint32_t(dma >> 32));
  if (p.hcRead(0x50) != uint32_t(dma) || p.hcRead(0x54) != uint32_t(dma >> 32)) return r;
  p.hcWrite(0x60, 1);
  if (!p.wait(0x60, 1, 1)) return r;
  r.stage = 4;
  if (!ready() || !protectedState() || rd(0x48) || rd(0x80058) != fsrBefore) return r;
  // Recheck all stream words immediately before the one allowed command.
  if (!t970_smr::sameMappings(expected, t970_smmu::collect(rd, 0x100000))) return r;
  r.stage = 5;
  r.success = p.nop(); // Production bounded poll, no cancel/retry on failure.
  r.submitted = p.submitted();
  protectedState();
  if (r.success) r.stage = 6;
  return r;
}
} // namespace t970_nop
