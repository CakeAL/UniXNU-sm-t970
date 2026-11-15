#include <cassert>
#include <cstdint>
#include "../drivers/ShengUfs/T970SeedState.h"
int main() {
  uint8_t data[4096] = {}, expected[4096] = {};
  expected[32] = 0x4e; expected[4095] = 1;
  assert(t970SeedBlockState(data, expected, sizeof data) == T970SeedBlockState::Zero);
  data[32] = 0x4e; data[4095] = 1;
  assert(t970SeedBlockState(data, expected, sizeof data) == T970SeedBlockState::Identical);
  data[4095] = 0;
  assert(t970SeedBlockState(data, expected, sizeof data) == T970SeedBlockState::Foreign);
  data[4095] = 1; data[1000] = 2;
  assert(t970SeedBlockState(data, expected, sizeof data) == T970SeedBlockState::Foreign);
}
