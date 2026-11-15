#include <cassert>
#include <cstring>
#include <vector>
#include "../drivers/ShengUfs/T970DataExtent.h"
#include "../../UniXNU/drivers/RamBlock/PersistOverlay.h"
static uint32_t le32(const uint8_t *p) { return persist::get32(p); }
static uint64_t le64(const uint8_t *p) { return persist::get64(p); }
static uint32_t rootCrc32(const uint8_t *p, size_t n) { return persist::crc32(p,n); }
#include "../drivers/ShengUfs/T970LargeData.h"
struct Medium {
  std::vector<uint8_t> data = std::vector<uint8_t>((1 + kT970LargeBitmapBlocks) * 4096, 0xA5);
  int calls = 0, fail = -1;
  bool read(uint64_t b, uint32_t n, void *p) { if (b+n > 1+kT970LargeBitmapBlocks) return false; memcpy(p,data.data()+b*4096,n*4096); return true; }
  bool write(uint64_t b, uint32_t n, const void *p) {
    if (b+n > 1+kT970LargeBitmapBlocks) return false;
    if (calls++ == fail) { if (b == 1) memcpy(data.data()+b*4096,p,(n/2)*4096); return false; }
    memcpy(data.data()+b*4096,p,n*4096); return true;
  }
  bool sync() { return calls++ != fail; }
};
int main() {
  auto first = [](uint64_t blocks, const uint8_t *seed, unsigned enabled=1, unsigned reset=0, unsigned direct=0, uint64_t part=37292800) {
    return t970LargeDataFirst(enabled,reset,direct,part,62458623,9382658048ULL,blocks,262144,seed);
  };
  assert(kT970LargeBitmapBlocks == 584 && kT970LargeBlocks == 19137097);
  assert(first(kT970LargeBlocks,kT970LargeSeed) == kT970LargeFirst);
  assert(!first(kT970LargeBlocks+1,kT970LargeSeed));
  assert(!first(kT970LargeBlocks,kT970LargeSeed,0));
  assert(!first(kT970LargeBlocks,kT970LargeSeed,1,1));
  assert(!first(kT970LargeBlocks,kT970LargeSeed,1,0,1));
  assert(!first(kT970LargeBlocks,kT970LargeSeed,1,0,0,37292801));
  uint8_t wrong[32] = {}; assert(!first(kT970LargeBlocks,wrong));
  // Each failed bitmap/header write or sync must refuse or be resumable; it
  // must never classify a partially initialized overlay as an existing one.
  for (int fail = 0; fail < 4; ++fail) {
    Medium m; m.data[32]='N'; m.data[33]='X'; m.data[34]='S'; m.data[35]='B'; m.fail=fail;
    assert(t970LargeHeaderState(m.data.data(), kT970DirectHeaderHash) == 1);
    std::vector<uint8_t> bits(kT970LargeBitmapBlocks*4096);
    persist::Overlay o; assert(o.open(m,kT970LargePages,kT970LargeSeed,false,bits.data(),true) == persist::Open::Failed);
    // If a committed header is visible, bitmap initialization preceded it.
    int state=t970LargeHeaderState(m.data.data(), kT970DirectHeaderHash);
    if (state == 0) for (size_t i=4096;i<m.data.size();++i) assert(m.data[i] == 0);
    m.fail=-1; m.calls=0;
    persist::Overlay retry;
    assert(retry.open(m,kT970LargePages,kT970LargeSeed,false,bits.data(),state == 1) != persist::Open::Failed);
    assert(t970LargeHeaderState(m.data.data(), nullptr) == 0);
    int before=m.calls; persist::Overlay resumed;
    assert(resumed.open(m,kT970LargePages,kT970LargeSeed,false,bits.data(),false) == persist::Open::Resumed);
    assert(m.calls==before && resumed.present==0);
  }
  uint8_t invalid[4096]={}; assert(t970LargeHeaderState(invalid,nullptr)==-1);
}
