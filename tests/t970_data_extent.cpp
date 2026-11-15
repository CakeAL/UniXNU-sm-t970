#include <cassert>
#include "../drivers/ShengUfs/T970DataExtent.h"
int main() {
  const uint64_t base = 37292800, end = 62458623;
  assert(!t970DataExtentSafe(base, end, base + 2290688, end));
  assert(t970DataExtentSafe(base, end, base + 2290688, base + 5505023));
  assert(!t970DataExtentSafe(base, end, base + 5505023, base + 5505024));
  assert(!t970DataExtentSafe(base, end, base + 5516624 + 6300, end));
  assert(t970DataExtentSafe(base, end, base + 5516624 + 6301, 62065402));
  assert(!t970DataExtentSafe(base, end, 62065402, 62065403));
  assert(!t970DataExtentSafe(base, end, base - 1, base));
  assert(!t970DataExtentSafe(base, end, base, end + 1));
  assert(!t970DataExtentSafe(base + 1, end, base + 1, base + 2));
  assert(!t970DataExtentSafe(base, end, end, base));
}
