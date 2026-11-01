// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include "T970SmrIdTest.h"

// Qualify stream fields without granting DMA: VALID is tested only with FAULT
// S2CR and unmatched-fault policy. All S2CR writes require an invalid SMR.
namespace t970_fields {
static constexpr unsigned s2crOffset = 0xc00 + 4 * t970_smr::slot;
struct Context {
  unsigned bank = 0;
  uint32_t cbar = 0, cba2r = 0, sctlr = 0, fsr = 0;
};
struct Result {
  t970_smr::Result id;
  unsigned stage = 0, contextsRead = 0;
  bool validTested = false, validAccepted = false, s2crTested = false, s2crAccepted = false;
  bool fallbackUsed = false, allRestored = false, mappingsUnchanged = false;
  uint32_t validObserved = 0, smrRestored = 0, s2crObserved = 0;
  uint32_t directRestore = 0, fallbackRestore = 0, finalS2cr = 0, gfsrAfter = 0;
  Context contexts[6];
};
template <class Read, class Write>
static Result run(const t970_smmu::Report &snapshot, const t970_ufs::Clocks &clocks,
                  const t970_ufs::Controller &hc, Read read, Write write)
{
  Result r;
  // Unmatched requests already fault. The temporary valid entry also faults;
  // no translation/bypass entry is exposed by the VALID test.
  if ((snapshot.scr0 & 0x401U) != 0x400U) return r;
  r.stage = 1;
  r.id = t970_smr::run(snapshot, clocks, hc, read, write);
  if (r.id.stage != 5 || !r.id.idAccepted || !r.id.restoreOK ||
      !r.id.mappingsUnchanged || r.id.gfsrAfter) return r;
  auto finish = [&]() {
    const auto after = t970_smmu::collect(read, 0x100000);
    r.smrRestored = after.streams[t970_smr::slot].smr;
    r.finalS2cr = after.streams[t970_smr::slot].s2cr;
    r.gfsrAfter = after.gfsr;
    r.mappingsUnchanged = t970_smr::sameMappings(snapshot, after);
    r.allRestored = r.smrRestored == 0 && r.finalS2cr == 0x200ff && r.mappingsUnchanged;
  };
  // Recheck the exact fault policy immediately before exposing VALID.
  if (read(0) != snapshot.scr0 || read(t970_smr::offset) != 0 ||
      read(s2crOffset) != 0x200ff || read(0x48)) { finish(); return r; }
  r.stage = 2;
  r.validTested = true;
  write(t970_smr::offset, 0x80000000U | t970_smr::pattern);
  r.validObserved = read(t970_smr::offset);
  write(t970_smr::offset, 0); // Restore even if VALID was rejected.
  r.validAccepted = r.validObserved == (0x80000000U | t970_smr::pattern);
  finish();
  if (!r.allRestored || r.gfsrAfter) return r;
  // Stream remains invalid throughout this phase. Recheck before each write.
  if (read(t970_smr::offset) != 0 || read(s2crOffset) != 0x200ff) { finish(); return r; }
  r.stage = 3;
  r.s2crTested = true;
  write(s2crOffset, 0); // TRANS/CB0 is unobservable to DMA while SMR is invalid.
  r.s2crObserved = read(s2crOffset);
  r.s2crAccepted = r.s2crObserved == 0;
  if (read(t970_smr::offset) != 0) { finish(); return r; }
  write(s2crOffset, 0x200ff);
  r.directRestore = read(s2crOffset);
  if (r.directRestore != 0x200ff) {
    // Linux qcom_smmu_write_s2cr documents FAULT writes ignored / BYPASS
    // converted to FAULT by some firmware. Try only on our still-invalid slot.
    if (read(t970_smr::offset) != 0) { finish(); return r; }
    r.fallbackUsed = true;
    write(s2crOffset, 0x100ff);
    r.fallbackRestore = read(s2crOffset);
    if (r.fallbackRestore != 0x200ff) {
      if (read(t970_smr::offset) != 0) { finish(); return r; }
      write(s2crOffset, 0x200ff); // One final direct restore, never an unbounded retry.
    }
  }
  finish();
  if (!r.allRestored || r.gfsrAfter) return r;
  r.stage = 4;
  const unsigned banks[] = {0, 1, 2, 3, 4, 73};
  for (unsigned bank : banks) {
    if (bank >= snapshot.banks || snapshot.pageShift != 12 ||
        snapshot.contextOffset + (static_cast<uint64_t>(bank) << 12) + 0x5c > 0x100000) break;
    Context &c = r.contexts[r.contextsRead++];
    c.bank = bank;
    c.cbar = read(0x1000 + 4 * bank);
    c.cba2r = read(0x1800 + 4 * bank);
    unsigned cb = static_cast<unsigned>(snapshot.contextOffset) + (bank << 12);
    c.sctlr = read(cb);
    c.fsr = read(cb + 0x58);
  }
  finish();
  return r;
}
static bool format(char *text, size_t capacity, const Result &r, const t970_smmu::Report &snapshot,
                   const t970_ufs::Clocks &clocks, const t970_ufs::Controller &hc)
{
  if (!capacity) return false;
  size_t used = 0;
  auto append = [&](const char *fmt, auto... args) {
    int n = snprintf(text + used, capacity - used, fmt, args...);
    if (n < 0 || static_cast<size_t>(n) >= capacity - used) return false;
    used += static_cast<size_t>(n);
    return true;
  };
  if (!append("%s", "T970 SMMU fields (no UFS commands)\n") ||
      !append("stage=%u idStage=%u idAccepted=%u idRestore=%u\n",
              r.stage, r.id.stage, unsigned(r.id.idAccepted), unsigned(r.id.restoreOK)) ||
      !append("VALID tested=%u accepted=%u observed=%08x smrFinal=%08x\n",
              unsigned(r.validTested), unsigned(r.validAccepted), r.validObserved, r.smrRestored) ||
      !append("S2CR tested=%u accepted=%u observed=%08x directRestore=%08x\n",
              unsigned(r.s2crTested), unsigned(r.s2crAccepted), r.s2crObserved, r.directRestore) ||
      !append("fallbackUsed=%u fallbackRead=%08x s2crFinal=%08x\n",
              unsigned(r.fallbackUsed), r.fallbackRestore, r.finalS2cr) ||
      !append("allRestored=%u mappingsUnchanged=%u gfsrAfter=%08x contexts=%u\n",
              unsigned(r.allRestored), unsigned(r.mappingsUnchanged), r.gfsrAfter, r.contextsRead) ||
      !append("snapshot cr0=%08x id0=%08x id1=%08x id2=%08x gf=%08x\n",
              snapshot.scr0, snapshot.id0, snapshot.id1, snapshot.id2, snapshot.gfsr) ||
      !append("GCC map=%u gdsc=%08x axi=%08x ahb=%08x HC=%u hce=%08x hcs=%08x db=%08x tmDb=%08x\n",
              unsigned(clocks.mapped), clocks.gdsc, clocks.axi, clocks.ahb,
              hc.state, hc.hce, hc.hcs, hc.doorbell, hc.tmDoorbell) ||
      !append("display04=%08x/%08x slot56before=%08x/%08x\n",
              snapshot.streams[4].smr, snapshot.streams[4].s2cr,
              snapshot.streams[t970_smr::slot].smr, snapshot.streams[t970_smr::slot].s2cr)) return false;
  for (unsigned i = 0; i < r.contextsRead && i < 6; ++i) {
    const auto &c = r.contexts[i];
    if (!append("CB%u cbar=%08x cba2r=%08x sctlr=%08x fsr=%08x\n",
                c.bank, c.cbar, c.cba2r, c.sctlr, c.fsr)) return false;
  }
  return append("%s", "END SMMU fields\n");
}
} // namespace t970_fields
