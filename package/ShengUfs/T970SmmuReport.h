// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once

// Register definitions reviewed against Linux v6.12 arm-smmu.h/device_cfg_probe.
// This observer has no write interface and never reads context-bank registers.
namespace t970_smmu {
struct Match {
  unsigned count = 0, slot = 0xffffffffU;
  uint32_t smr = 0, s2cr = 0;
};
struct Stream {
  uint32_t smr = 0, s2cr = 0;
  bool valid = false;
};
struct Report {
  uint32_t scr0 = 0, id0 = 0, id1 = 0, id2 = 0, gfsr = 0;
  unsigned pageShift = 0, banks = 0, stage2Banks = 0, groups = 0, scanned = 0;
  uint64_t contextOffset = 0;
  bool identityValid = false, streamMatching = false, stage1 = false, geometryValid = false, extendedIds = false;
  Match candidate[3]; // Candidate SIDs only: 0x60, 0xe0 and 0x4e0 are not board routing proof.
  Stream streams[128]; // Raw slots, including invalid entries; bounded by scanned.
  unsigned valid = 0;
};
template <class Read>
static Report collect(Read read, uint64_t mappedBytes)
{
  Report r;
  if (mappedBytes < 0x4c) return r;
  r.scr0 = read(0x00);
  r.id0 = read(0x20);
  r.id1 = read(0x24);
  r.id2 = read(0x28);
  r.gfsr = read(0x48);
  r.identityValid = r.id0 && r.id0 != 0xffffffffU && r.id1 != 0xffffffffU && r.id2 != 0xffffffffU;
  r.streamMatching = (r.id0 & (1U << 27)) != 0;
  r.stage1 = (r.id0 & (1U << 30)) != 0;
  r.extendedIds = (r.scr0 & (1U << 3)) != 0;
  r.groups = r.id0 & 0xff;
  r.banks = r.id1 & 0xff;
  r.stage2Banks = (r.id1 >> 16) & 0xff;
  r.pageShift = (r.id1 & (1U << 31)) ? 16 : 12;
  r.contextOffset = (1ULL << (((r.id1 >> 28) & 7) + 1)) << r.pageShift;
  r.geometryValid = r.identityValid && r.banks && r.stage2Banks <= r.banks &&
    r.contextOffset <= mappedBytes &&
    (static_cast<uint64_t>(r.banks) << r.pageShift) <= mappedBytes - r.contextOffset;
  if (!r.identityValid || !r.streamMatching || (r.extendedIds && !(r.id0 & (1U << 8)))) return r;
  unsigned count = r.groups > 128 ? 128 : r.groups;
  const uint16_t candidates[] = {0x60, 0xe0, 0x4e0};
  for (unsigned index = 0; index < count; ++index) {
    const unsigned smrOffset = 0x800 + 4 * index, s2crOffset = 0xc00 + 4 * index;
    if (static_cast<uint64_t>(s2crOffset) + 4 > mappedBytes) break;
    ++r.scanned;
    uint32_t smr = read(smrOffset);
    uint32_t s2cr = read(s2crOffset);
    const bool valid = (r.extendedIds ? s2cr & (1U << 10) : smr & 0x80000000U) != 0;
    r.streams[index] = {smr, s2cr, valid};
    if (!valid) continue;
    ++r.valid;
    uint32_t mask = (smr >> 16) & (r.extendedIds ? 0xffff : 0x7fff);
    for (unsigned candidate = 0; candidate < 3; ++candidate) {
      if (((smr ^ candidates[candidate]) & 0xffffU & ~mask) != 0) continue;
      Match &match = r.candidate[candidate];
      if (!match.count) {
        match.slot = index;
        match.smr = smr;
        match.s2cr = s2cr;
      }
      ++match.count;
    }
  }
  return r;
}
} // namespace t970_smmu
