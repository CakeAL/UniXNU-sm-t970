#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include "T970UfsHandoff.h"

int main() {
  t970_ufs::Clocks good;
  good.mapped = true; good.gdsc = 0x80000000; good.axi = good.ahb = 1;
  assert(t970_ufs::canReadController(good));
  for (unsigned failure = 0; failure < 8; ++failure) {
    auto c = good;
    switch (failure) {
      case 0: c.mapped = false; break;
      case 1: c.gdsc = 0; break;
      case 2: c.gdsc = 0xffffffffU; break;
      case 3: c.axi = 0; break;
      case 4: c.ahb = 0; break;
      case 5: c.axi = 0xffffffffU; break;
      case 6: c.axi = 0x80000003; break;
      case 7: c.ahb = 0x80000003; break;
    }
    unsigned reads = 0;
    auto h = t970_ufs::collectController(c, [&](unsigned) { ++reads; return 0U; });
    assert(!reads && h.state == 0);
  }
  std::vector<unsigned> reads;
  auto h = t970_ufs::collectController(good, [&](unsigned off) { reads.push_back(off); return off + 1; });
  const std::vector<unsigned> expected = {0, 8, 0x20, 0x30, 0x34, 0x50, 0x54, 0x58, 0x60, 0x78, 0x80};
  assert(reads == expected && h.state == 1 && h.listHigh == 0x55 && h.tmDoorbell == 0x79);
  reads.clear();
  auto c = t970_ufs::collectClocks([&](unsigned off) { reads.push_back(off); return off; });
  for (auto off : reads) assert(off < 0x1000);
  assert(reads.size() == 10 && c.mapped);
  for (unsigned count : {87U, 128U}) {
    auto r = t970_smmu::collect([&](unsigned off) -> uint32_t {
      if (off == 0x20) return 0x4c017e00 | count;
      if (off == 0x24) return 0x6000004a;
      if (off == 0x28) return 0x5111;
      if (off >= 0x800 && off < 0x800 + count * 4) {
        unsigned slot = (off - 0x800) / 4;
        return (slot % 2 ? 0x80000000U : 0U) | (0x100 + slot);
      }
      if (off >= 0xc00 && off < 0xc00 + count * 4) return 0x12340000 + (off - 0xc00) / 4;
      return 0;
    }, 0x100000);
    assert(r.scanned == count && r.valid == count / 2);
    // Invalid SMRs still retain their actual S2CR, rather than defaulting to zero.
    assert(!r.streams[0].valid && r.streams[0].s2cr == 0x12340000);
    char text[3600];
    assert(t970_ufs::format(text, sizeof(text), r, c, h));
    std::string rendered(text);
    assert(rendered.size() < 3600 && rendered.find("END slots=" + std::to_string(count)) != std::string::npos);
    unsigned lines = 0;
    size_t start = 0;
    for (size_t end; (end = rendered.find('\n', start)) != std::string::npos; start = end + 1) {
      assert(end - start <= 155); // Measured 2800px / 18px panic-screen character cell.
      ++lines;
    }
    assert(lines <= 31); // 31 * 42px fits below the measured 1752px screen's header.
    for (unsigned slot = 0; slot < count; ++slot) {
      char token[24];
      snprintf(token, sizeof(token), "%02x:%08x/%08x", slot, r.streams[slot].smr, r.streams[slot].s2cr);
      assert(rendered.find(token) != std::string::npos);
    }
    char clipped[17]; memset(clipped, 'Z', sizeof(clipped));
    assert(!t970_ufs::format(clipped, 16, r, c, h) && clipped[16] == 'Z' && clipped[15] == 0);
    assert(!t970_ufs::format(clipped, 0, r, c, h) && clipped[16] == 'Z');
  }
  std::puts("PASS: handoff clock gates, raw slots and display bounds");
}
