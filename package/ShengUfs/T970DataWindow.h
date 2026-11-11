// SPDX-License-Identifier: BSD-2-Clause-Patent
// Included after RootLayout.h for the on-disk endian and CRC helpers.
#pragma once

constexpr uint64_t kT970DataPages = (512ULL << 20) / 4096;
constexpr uint64_t kT970DataBlocks = 1 + (kT970DataPages + 32767) / 32768 + kT970DataPages;

static uint64_t t970DataFirst (uint32_t unixnu, uint32_t reset, uint64_t first, uint64_t last,
                              uint64_t imageBytes, uint64_t blocks, uint64_t reserve)
{
  // The deployed layout uses LUN 0 and 4096-byte LBAs. Pin both ends so a
  // missing selector or another partition cannot grant a write window.
  if (unixnu != 1 || reset || first != 37292800 || last != 62458623 ||
      imageBytes != 9382658048ULL || blocks != kT970DataBlocks || reserve != 262144)
    return 0;
  return last + 1 - reserve - blocks;
}

// 0 = blank, 1 = this seed's overlay, -1 = refuse before opening for writes.
static int t970DataHeaderState (const uint8_t *header, const uint8_t *seed)
{
  static const uint8_t blank[4096] = {};
  if (memcmp (header, blank, sizeof (blank)) == 0) return 0;
  return memcmp (header, "SHNGDATA", 8) == 0 && le32 (header + 8) == 1 &&
         le32 (header + 12) == 64 && le64 (header + 16) == kT970DataPages &&
         memcmp (header + 24, seed, 32) == 0 &&
         le32 (header + 60) == rootCrc32 (header, 60) ? 1 : -1;
}
