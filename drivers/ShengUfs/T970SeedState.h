// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include <stddef.h>
#include <stdint.h>

// Check each seed block before the first write. Identical blocks are safe to
// resume after an interrupted initialization; any other nonzero block refuses.
enum class T970SeedBlockState { Zero, Identical, Foreign };
static T970SeedBlockState t970SeedBlockState(const uint8_t *actual, const uint8_t *expected, size_t length)
{
  bool zero = true, identical = true;
  for (size_t i = 0; i < length; ++i) {
    zero &= actual[i] == 0;
    identical &= actual[i] == expected[i];
  }
  return identical ? T970SeedBlockState::Identical : zero ? T970SeedBlockState::Zero : T970SeedBlockState::Foreign;
}
