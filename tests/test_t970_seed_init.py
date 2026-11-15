#!/usr/bin/env python3
"""Fault-inject the actual APFS seed routine with an in-memory block device."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'drivers/ShengUfs/NativeUfs.cpp').read_text()
start = source.index('static bool t970ApfsSeed (')
end = source.index('\n\n// Returns 1 and the first absolute', start)
function = source[start:end]
prefix = r'''
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <cassert>
#include "T970SeedState.h"
using IOReturn = int;
const int kIOReturnSuccess = 0;
uint8_t disk[4][4096], expected[3 * 4096];
const uint32_t kT970ApfsSeedBlocks = 3;
const uint32_t kT970ApfsSeedIndex[] = {0,1,3};
uint8_t *kT970ApfsSeedData = expected;
bool window = false; int writes = 0, fail_after = -1; int order[3] = {};
void *IOMalloc(size_t n) { return malloc(n); }
void IOFree(void *p, size_t) { free(p); }
void IOLog(const char *, ...) {}
bool PE_parse_boot_argn(const char *, uint32_t *out, size_t) { *out = 1; return true; }
IOReturn hostRead4k(int, uint64_t at, int, void *out) { if(at>=4) return 1; memcpy(out,disk[at],4096); return 0; }
bool hostRootOpen(uint64_t first, uint64_t blocks, bool rw) { if(window || first || blocks!=4 || !rw) return false; return window=true; }
void hostRootClose() { window=false; }
IOReturn hostRootWrite4k(int, uint64_t at, int, const void *src, bool) {
  assert(window && at<4); if (writes==fail_after) return 1;
  order[writes++] = int(at); memcpy(disk[at],src,4096); return 0;
}
IOReturn hostRootSync() { return window ? 0 : 1; }
'''
suffix = r'''
int main() {
 expected[32]='N'; expected[33]='X'; expected[34]='S'; expected[35]='B';
 expected[4096]=42; expected[8192]=73;
 assert(!t970ApfsSeed(0,4,false)); assert(writes==0 && !window);
 disk[3][10]=9; assert(!t970ApfsSeed(0,4,true)); assert(writes==0 && !window);
 disk[3][10]=0; fail_after=1; assert(!t970ApfsSeed(0,4,true));
 assert(writes==1 && order[0]==1 && disk[0][32]==0 && !window);
 writes=0; fail_after=-1; assert(t970ApfsSeed(0,4,true));
 assert(writes==2 && order[0]==3 && order[1]==0 && !window);
 writes=0; assert(t970ApfsSeed(0,4,true)); assert(writes==0);
}
'''
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / 'test.cpp'
    path.write_text(prefix + function + suffix)
    executable = Path(tmp) / 'test'
    subprocess.run(['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined', '-I', str(root / 'drivers/ShengUfs'), str(path), '-o', str(executable)], check=True)
    subprocess.run([str(executable)], check=True)
