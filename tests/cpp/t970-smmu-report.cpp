#include <cassert>
#include <cstdint>
#include <cstdio>
#include <map>
#include <vector>
#include "T970SmmuReport.h"
#include "SmmuTakeover.h"

struct Bus {
  std::map<unsigned, uint32_t> values;
  std::vector<unsigned> reads;
  uint32_t read(unsigned offset) {
    reads.push_back(offset);
    return values[offset];
  }
  Bus() {
    values[0] = 0x002d0405; // Deliberately unlike ID0: must not determine the count.
    values[0x20] = (1U << 30) | (1U << 27) | 4;
    values[0x24] = (2U << 16) | 8;
    values[0x28] = 1U << 12;
  }
  bool scanned() const {
    for (auto offset : reads) if (offset >= 0x800) return true;
    return false;
  }
};

int main() {
  {
    Bus bus;
    bus.values[0x800] = 0x80000060;
    bus.values[0x808] = 0x800000e0;
    bus.values[0x80c] = 0x840000e0; // Mask SID bit 10: e0 and 4e0.
    auto before = bus.values;
    auto r = t970_smmu::collect([&](unsigned off) { return bus.read(off); }, 0x100000);
    assert(r.scr0 == 0x002d0405 && r.groups == 4 && r.scanned == 4);
    assert(r.geometryValid && r.pageShift == 12 && r.contextOffset == 0x2000);
    assert(r.banks == 8 && r.stage2Banks == 2);
    assert(r.candidate[0].count == 1 && r.candidate[1].count == 2 && r.candidate[2].count == 1);
    assert(r.candidate[1].slot == 2 && r.candidate[2].slot == 3);
    for (auto off : bus.reads) assert(off <= 0x48 || (off >= 0x800 && off < 0xe00));
    // Read callbacks may materialize absent zero registers; nonzero state is unchanged.
    for (auto value : before) assert(bus.values[value.first] == value.second);
  }
  {
    Bus bus;
    bus.values[0x20] = (1U << 30) | 4; // Indexing mode: do not scan SMRs.
    auto r = t970_smmu::collect([&](unsigned off) { return bus.read(off); }, 0x100000);
    assert(!r.streamMatching && !r.scanned && !bus.scanned());
  }
  {
    Bus bus;
    bus.values[0x20] = 0xffffffffU;
    auto r = t970_smmu::collect([&](unsigned off) { return bus.read(off); }, 0x100000);
    assert(!r.identityValid && !bus.scanned());
  }
  {
    Bus bus;
    bus.values[0x24] |= 1U << 31;
    auto r = t970_smmu::collect([&](unsigned off) { return bus.read(off); }, 0x100000);
    assert(r.pageShift == 16 && r.contextOffset == 0x20000 && r.geometryValid);
  }
  {
    Bus bus;
    bus.values[0x24] |= 7U << 28;
    auto r = t970_smmu::collect([&](unsigned off) { return bus.read(off); }, 0x1000);
    assert(!r.geometryValid);
    for (auto off : bus.reads) assert(off < 0x1000);
  }
  {
    Bus bus;
    bus.values[0x20] = (1U << 30) | (1U << 27) | 255;
    bus.values[0x800 + 127 * 4] = 0x800004e0;
    auto r = t970_smmu::collect([&](unsigned off) { return bus.read(off); }, 0x100000);
    assert(r.groups == 255 && r.scanned == 128 && r.candidate[2].slot == 127);
  }
  {
    Bus bus;
    bus.values[0] = 1U << 3;
    bus.values[0x20] |= 1U << 8;
    bus.values[0x800] = 0xe0; // EXIDS validity comes from S2CR, not SMR bit 31.
    bus.values[0xc00] = (1U << 10) | 7;
    auto r = t970_smmu::collect([&](unsigned off) { return bus.read(off); }, 0x100000);
    assert(r.extendedIds && r.candidate[1].count == 1 && r.candidate[1].s2cr == 0x407);
    UfsSmmuStreamEntry entries[4];
    assert(collectUfsSmmuStreams([&](unsigned off) { return bus.read(off); }, entries, 4) == 1);
    assert(entries[0].smr == 0xe0 && entries[0].s2cr == 0x407);
  }
  {
    Bus bus;
    auto r = t970_smmu::collect([&](unsigned off) { return bus.read(off); }, 0x40);
    assert(!r.identityValid && bus.reads.empty());
    r = t970_smmu::collect([&](unsigned off) { return bus.read(off); }, 0xc04);
    assert(r.scanned == 1);
  }
  {
    Bus bus;
    bus.values[0x80c] = 0x800004e0;
    UfsSmmuStreamEntry entries[1];
    assert(collectUfsSmmuStreams([&](unsigned off) { return bus.read(off); }, entries, 1) == 1);
    assert(bus.reads.front() == 0x20 && entries[0].index == 3);
    for (auto off : bus.reads) assert(off < 0x1000);
  }
  {
    Bus bus;
    bus.values[0x28] = (1U << 12) | 0x222;
    auto p = planUfsSmmu(0xe0, 0x100000, 4096, [&](unsigned off) { return bus.read(off); });
    assert(!p.error && p.bank == 2 && p.slot == 0); // NUMS2CB=2, not guessed bank 1.
    bus.values[0x24] = (9U << 16) | 8;
    p = planUfsSmmu(0xe0, 0x100000, 4096, [&](unsigned off) { return bus.read(off); });
    assert(p.error);
  }
  {
    Bus bus;
    bus.values[0x28] = (1U << 12) | 0x222;
    bus.values[0x800] = 0x80000200;
    bus.values[0xc00] = 2; // An unrelated stream already owns the first eligible bank.
    auto p = planUfsSmmu(0xe0, 0x100000, 4096, [&](unsigned off) { return bus.read(off); });
    assert(!p.error && p.bank == 3 && p.slot == 1);
  }
  std::puts("PASS: 11 SMMUv2 report and planning cases");
}
