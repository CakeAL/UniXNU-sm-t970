// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include "T970UfsHandoff.h"

// One measured inactive slot only. VALID stays clear; never write S2CR/CB/GCC/HCI.
// Compare Samsung arm-smmu.c::arm_smmu_test_smr_masks (ad129ac...), but restore
// the original word and check protected mappings instead of leaving test bits.
namespace t970_smr {
static constexpr unsigned slot = 0x56, offset = 0x800 + 4 * slot;
static constexpr uint32_t pattern = 0x000000a5; // ID bits only, no VALID or mask.
static_assert(!(pattern & 0xffff0000U), "Test must not expose a valid mapping");
struct Result {
  unsigned stage = 0; // 1=geometry refused, 2=HCI refused, 3=slot/display refused,
                      // 4=state changed before write, 5=test and restore attempted.
  uint32_t before = 0, observed = 0, restored = 0, s2crBefore = 0, s2crAfter = 0;
  uint32_t gfsrBefore = 0, gfsrAfter = 0;
  bool idAccepted = false, restoreOK = false, mappingsUnchanged = false;
};
static bool sameMappings(const t970_smmu::Report &a, const t970_smmu::Report &b)
{
  if (a.scr0 != b.scr0 || a.id0 != b.id0 || a.id1 != b.id1 || a.id2 != b.id2 ||
      a.scanned != b.scanned || a.scanned > 128) return false;
  for (unsigned i = 0; i < a.scanned; ++i) {
    if (a.streams[i].smr != b.streams[i].smr || a.streams[i].s2cr != b.streams[i].s2cr) return false;
  }
  return true;
}
template <class Read, class Write>
static Result run(const t970_smmu::Report &snapshot, const t970_ufs::Clocks &clocks,
                  const t970_ufs::Controller &hc, Read read, Write write)
{
  Result result;
  result.stage = 1;
  if (snapshot.id0 != 0x4c017e57 || snapshot.id1 != 0x6000004a || snapshot.id2 != 0x5111 ||
      !snapshot.identityValid || !snapshot.geometryValid || !snapshot.streamMatching ||
      snapshot.extendedIds || snapshot.groups != 87 || snapshot.scanned != 87 || snapshot.gfsr) return result;
  result.stage = 2;
  if (!t970_ufs::canReadController(clocks) || hc.state != 1 || !(hc.hce & 1) ||
      (hc.hcs & 15) != 15 || hc.doorbell || hc.tmDoorbell) return result;
  result.stage = 3;
  // Protect the exact measured display route and refuse any new valid stream.
  if (snapshot.valid != 1 || snapshot.streams[4].smr != 0x84020820 ||
      snapshot.streams[4].s2cr != 4 || snapshot.streams[slot].valid ||
      snapshot.streams[slot].smr != 0 || snapshot.streams[slot].s2cr != 0x200ff) return result;
  result.stage = 4;
  {
    const auto fresh = t970_smmu::collect(read, 0x100000);
    if (!sameMappings(snapshot, fresh) || fresh.gfsr != snapshot.gfsr) return result;
  }
  result.before = read(offset);
  result.s2crBefore = read(0xc00 + 4 * slot);
  result.gfsrBefore = read(0x48);
  if (result.before != 0 || result.s2crBefore != 0x200ff || result.gfsrBefore != snapshot.gfsr) return result;
  result.stage = 5;
  write(offset, pattern);
  result.observed = read(offset);
  // Always attempt restore, including rejected or unexpected test readback.
  write(offset, result.before);
  result.restored = read(offset);
  result.s2crAfter = read(0xc00 + 4 * slot);
  result.idAccepted = result.observed == pattern;
  result.restoreOK = result.restored == result.before && result.s2crAfter == result.s2crBefore;
  {
    const auto after = t970_smmu::collect(read, 0x100000);
    result.gfsrAfter = after.gfsr;
    result.mappingsUnchanged = sameMappings(snapshot, after);
  }
  return result;
}
} // namespace t970_smr
