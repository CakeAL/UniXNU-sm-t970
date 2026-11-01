#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <map>
#include <string>
#include <utility>
#include <vector>
#include "T970SmmuFields.h"

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
  uint32_t read(unsigned off) { return values[off]; }
  void write(unsigned off, uint32_t value) {
    assert(off == 0x958 || off == 0xd58);
    if (off == 0xd58) {
      assert(values[0x958] == 0); // No S2CR update may affect an active stream.
      assert(value == 0 || value == 0x200ff || value == 0x100ff);
    } else if (value & 0x80000000U) {
      assert(value == 0x800000a5 && values[0xd58] == 0x200ff);
      assert((values[0] & 0x401) == 0x400); // Temporary rule matches the default fault policy.
    } else assert(value == 0 || value == 0xa5);
    writes.emplace_back(off, value);
    if (mode == 1 && value == 0x800000a5) { values[off] = 0xa5; return; }
    if (mode == 2 && off == 0xd58) return;
    if ((mode == 3 || mode == 4) && off == 0xd58 && value == 0x200ff) return;
    if (mode == 3 && off == 0xd58 && value == 0x100ff) { values[off] = 0x200ff; return; }
    if (mode == 5 && off == 0x958 && value == 0 && values[off] == 0x800000a5) return;
    if (mode == 6 && value == 0xa5) return;
    values[off] = value;
    if (mode == 7 && value == 0x800000a5) values[0x810] ^= 1;
    if (mode == 9 && off == 0xd58 && value == 0) values[0x48] = 1;
  }
  t970_smmu::Report capture() {
    return t970_smmu::collect([&](unsigned off) { return read(off); }, 0x100000);
  }
};

int main() {
  t970_ufs::Clocks c; c.mapped = true; c.gdsc = 0x80000000; c.axi = c.ahb = 1;
  t970_ufs::Controller h; h.state = 1; h.hce = 1; h.hcs = 15;
  for (unsigned mode = 0; mode < 10; ++mode) {
    Bus bus; bus.mode = mode;
    if (mode == 8) bus.values[0] &= ~0x400U;
    auto snapshot = bus.capture();
    auto r = t970_fields::run(snapshot, c, h,
      [&](unsigned off) { return bus.read(off); }, [&](unsigned off, uint32_t value) { bus.write(off, value); });
    assert(bus.writes.size() <= 8);
    if (mode == 0 || mode == 1 || mode == 2 || mode == 3) {
      assert(r.stage == 4 && r.contextsRead == 6 && r.allRestored && r.mappingsUnchanged);
      assert(r.validAccepted == (mode != 1));
      assert(r.s2crAccepted == (mode != 2));
    }
    if (mode == 0) assert(bus.writes.size() == 6 && !r.fallbackUsed);
    if (mode == 3) assert(r.directRestore == 0 && r.fallbackRestore == 0x200ff && r.fallbackUsed);
    if (mode == 4) assert(r.stage == 3 && !r.allRestored && !r.mappingsUnchanged && r.contextsRead == 0);
    if (mode == 5 || mode == 7) assert(r.stage == 2 && !r.allRestored && !r.s2crTested && !r.contextsRead);
    if (mode == 6) assert(r.stage == 1 && !r.validTested && bus.writes.size() == 2);
    if (mode == 8) assert(r.stage == 0 && bus.writes.empty());
    if (mode == 9) assert(r.stage == 3 && r.allRestored && r.gfsrAfter == 1 && !r.contextsRead);
    char text[1800];
    assert(t970_fields::format(text, sizeof(text), r, snapshot, c, h));
    std::string output(text);
    assert(output.find("END SMMU fields") != std::string::npos && output.size() < 1800);
    if (r.contextsRead) assert(output.find("CB73 ") != std::string::npos);
    char truncated[16];
    assert(!t970_fields::format(truncated, sizeof(truncated), r, snapshot, c, h));
  }
  // Old guards also apply to the combined path: no write on an active target.
  Bus bus; auto snapshot = bus.capture(); snapshot.streams[0x56].valid = true;
  auto r = t970_fields::run(snapshot, c, h,
    [&](unsigned off) { return bus.read(off); }, [&](unsigned off, uint32_t value) { bus.write(off, value); });
  assert(r.id.stage == 3 && bus.writes.empty());
  std::puts("PASS: field qualification, quirk recovery and protected-route cases");
}
