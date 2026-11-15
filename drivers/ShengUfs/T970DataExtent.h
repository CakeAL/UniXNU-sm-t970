// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include <stdint.h>

// Partition-relative 4 KiB policy envelopes, including their final partial block.
// The root policy loader uses the same fixed offsets and 4 KiB rounding.
static bool t970DataExtentSafe(uint64_t partitionFirst, uint64_t partitionLast,
                               uint64_t first, uint64_t last)
{
  if (partitionFirst != 37292800ULL || partitionLast != 62458623ULL ||
      first < partitionFirst || first > last || last > partitionLast ||
      last >= 62065403ULL) // Preserve the existing 512 MiB overlay and the 1 GiB tail reserve.
    return false;
  const uint64_t lo = first - partitionFirst, hi = last - partitionFirst;
  const uint64_t policy0First = 5505024ULL, policy0Last = policy0First + 11593ULL - 1;
  const uint64_t policy1First = 5516624ULL, policy1Last = policy1First + 6301ULL - 1;
  return !(lo <= policy0Last && hi >= policy0First) &&
         !(lo <= policy1Last && hi >= policy1First);
}
