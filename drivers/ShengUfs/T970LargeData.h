// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
// The first installation replaces only the previously backed-up direct Data
// container. Thereafter the exact seed's SHNGDATA header is the authority.
// Include after RootLayout.h and T970DataExtent.h.
constexpr uint64_t kT970LargePages = (73ULL << 30) / 4096;
constexpr uint64_t kT970LargeBitmapBlocks = (kT970LargePages + 32767) / 32768;
constexpr uint64_t kT970LargeBlocks = 1 + kT970LargeBitmapBlocks + kT970LargePages;
constexpr uint64_t kT970LargeFirst = 42816256ULL;
static const uint8_t kT970LargeSeed[32] = {
  0xd4,0x37,0x2c,0x71,0xbe,0x21,0x6b,0xed,0x6f,0x82,0x78,0x02,0x6f,0xb6,0xbd,0x08,
  0xd5,0x2f,0xa7,0x56,0x5f,0xed,0x02,0x76,0xa9,0xbe,0x8f,0xff,0xac,0x8b,0x2c,0xb9
};
static const uint8_t kT970DirectHeaderHash[32] = {
  0xf1,0xd8,0x80,0xae,0x3b,0xb4,0xad,0x6b,0x87,0x4c,0x44,0xdd,0xa3,0xa1,0x78,0x27,
  0x22,0xc1,0x44,0xad,0x56,0xbe,0x0d,0x24,0x38,0x51,0x08,0xdb,0x94,0xd0,0xf0
};
static uint64_t t970LargeDataFirst(uint32_t enabled, uint32_t reset, uint32_t direct,
                                  uint64_t first, uint64_t last, uint64_t imageBytes,
                                  uint64_t blocks, uint64_t reserve, const uint8_t *seed)
{
  if (enabled != 1 || reset || direct || !seed || memcmp(seed, kT970LargeSeed, 32) ||
      first != 37292800 || last != 62458623 || imageBytes != 9382658048ULL ||
      blocks != kT970LargeBlocks || reserve != 262144 ||
      !t970DataExtentSafe(first, last, kT970LargeFirst, kT970LargeFirst + blocks - 1)) return 0;
  return kT970LargeFirst;
}
// 0 = current overlay; 1 = reviewed old direct container; -1 = refuse.
static int t970LargeHeaderState(const uint8_t *header, const uint8_t *digest)
{
  if (memcmp(header, "SHNGDATA", 8) == 0 && le32(header + 8) == 1 &&
      le32(header + 12) == 64 && le64(header + 16) == kT970LargePages &&
      memcmp(header + 24, kT970LargeSeed, 32) == 0 &&
      le32(header + 60) == rootCrc32(header, 60)) return 0;
  if (digest && memcmp(digest, kT970DirectHeaderHash, 32) == 0) return 1;
  return -1;
}
