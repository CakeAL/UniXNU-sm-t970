#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <map>
#include <utility>
#include <vector>
#include "T970SmrIdTest.h"

struct Bus {
  std::map<unsigned, uint32_t> values;
  std::vector<std::pair<unsigned, uint32_t>> writes;
  unsigned mode = 0;
  Bus() {
    values[0] = 0x002d0406; values[0x20] = 0x4c017e57;
    values[0x24] = 0x6000004a; values[0x28] = 0x5111;
    for (unsigned i = 0; i < 87; ++i) values[0xc00 + 4 * i] = 0x200ff;
    values[0x810] = 0x84020820; values[0xc10] = 4;
  }
  uint32_t read(unsigned offset) { return values[offset]; }
  void write(unsigned offset, uint32_t value) {
    // Every path, including fault-injection cases, must be confined here.
    assert(offset == 0x958 && !(value & 0xffff0000U));
    writes.emplace_back(offset, value);
    if (mode == 1) return; // Register ignores writes.
    if (mode == 2 && writes.size() == 2) return; // Restore ignored.
    values[offset] = value;
    if (mode == 3 && writes.size() == 1) values[offset] ^= 1; // Unexpected readback.
    if (mode == 4 && writes.size() == 1) values[0x810] ^= 1; // External display change.
    if (mode == 5 && writes.size() == 1) values[0x48] = 1; // Newly observed fault.
    if (mode == 6 && writes.size() == 1) values[0xc00 + 4 * 0x56] ^= 1;
  }
  t970_smmu::Report capture() {
    return t970_smmu::collect([&](unsigned offset) { return read(offset); }, 0x100000);
  }
};

int main() {
  t970_ufs::Clocks clocks; clocks.mapped = true; clocks.gdsc = 0x80000000;
  clocks.axi = clocks.ahb = 1;
  t970_ufs::Controller hc; hc.state = 1; hc.hce = 1; hc.hcs = 0x10f;
  for (unsigned mode = 0; mode < 7; ++mode) {
    Bus bus; bus.mode = mode;
    auto snapshot = bus.capture();
    auto r = t970_smr::run(snapshot, clocks, hc,
      [&](unsigned off) { return bus.read(off); }, [&](unsigned off, uint32_t value) { bus.write(off, value); });
    assert(r.stage == 5 && bus.writes.size() == 2);
    assert(bus.writes[0] == std::make_pair(0x958U, 0xa5U));
    assert(bus.writes[1] == std::make_pair(0x958U, 0U));
    assert(r.idAccepted == (mode == 0 || (mode >= 2 && mode != 3)));
    assert(r.restoreOK == (mode != 2 && mode != 6));
    assert(r.mappingsUnchanged == (mode != 2 && mode != 4 && mode != 6));
    if (mode == 5) assert(r.gfsrAfter == 1); // Fault flags are read, never cleared.
  }
  for (unsigned failure = 0; failure < 11; ++failure) {
    Bus bus;
    auto snapshot = bus.capture(); auto c = clocks; auto h = hc;
    switch (failure) {
      case 0: snapshot.groups = 88; break;
      case 1: snapshot.extendedIds = true; break;
      case 2: c.axi = 0; break;
      case 3: h.doorbell = 1; break;
      case 4: h.tmDoorbell = 1; break;
      case 5: snapshot.streams[0x56].smr = 0x80; break;
      case 6: snapshot.streams[0x56].s2cr = 0; break;
      case 7: snapshot.streams[4].s2cr = 5; break;
      case 8: bus.values[0x800] = 0x123; break; // Changed after initial capture.
      case 9: bus.values[0x48] = 1; break;
      case 10: snapshot.gfsr = 1; break;
    }
    auto r = t970_smr::run(snapshot, c, h,
      [&](unsigned off) { return bus.read(off); }, [&](unsigned off, uint32_t value) { bus.write(off, value); });
    assert(r.stage < 5 && bus.writes.empty());
  }
  std::puts("PASS: 18 bounded SMR ID-field guard and restoration cases");
}
