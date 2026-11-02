#!/usr/bin/env python3
"""Host-execute the actual read-only reset-context accessor; ABI stand-ins only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
source = args.source.read_text()
start = source.index('void\nnative_t970_reset_context(uint64_t *out)')
end = source.index('\n#endif', start)
actual = source[start:end]
prelude = r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef uintptr_t vm_offset_t;
typedef struct {uint32_t cpu_phys_id;uintptr_t cpu_reset_handler;} cpu_data_t;
typedef struct {cpu_data_t *cpu_data_vaddr;void *cpu_data_paddr;} cpu_data_entry_t;
cpu_data_entry_t CpuDataEntries[8];
struct {uintptr_t cpu_data_entries;} ResetHandlerData;
uintptr_t start_cpu;
static uintptr_t ml_static_vtop(uintptr_t address){assert(address==(uintptr_t)CpuDataEntries||address==(uintptr_t)&start_cpu);return address^0x123450000ULL;}
'''
main = r'''
int main(void){
 cpu_data_t cpu={0x100,0x123456789abcdef0ULL};
 CpuDataEntries[1].cpu_data_vaddr=&cpu;CpuDataEntries[1].cpu_data_paddr=(void*)0x123456780000ULL;
 ResetHandlerData.cpu_data_entries=0xabcdef0123450000ULL;
 for(unsigned present=0;present<2;++present){
  CpuDataEntries[1].cpu_data_vaddr=present?&cpu:NULL;
  cpu_data_entry_t before[8];memcpy(before,CpuDataEntries,sizeof(before));
  cpu_data_t cpu_before=cpu;uintptr_t reset_before=ResetHandlerData.cpu_data_entries;
  struct {uint64_t first,out[6],last;} result={.first=0xcafebabe,.last=0xfeedface};
  native_t970_reset_context(result.out);
  assert(result.first==0xcafebabe&&result.last==0xfeedface);
  assert(result.out[0]==reset_before&&result.out[1]==ml_static_vtop((uintptr_t)CpuDataEntries));
  assert(result.out[2]==0x123456780000ULL&&result.out[3]==(present?0x100:0));
  assert(result.out[4]==(present?cpu.cpu_reset_handler:0)&&result.out[5]==ml_static_vtop((uintptr_t)&start_cpu));
  assert(!memcmp(before,CpuDataEntries,sizeof(before))&&!memcmp(&cpu_before,&cpu,sizeof(cpu))&&ResetHandlerData.cpu_data_entries==reset_before);
 }
 puts("PASS: actual reset-context accessor preserves sources, full-width addresses, null CPU handling and six output bounds");
}
'''
args.output.mkdir(parents=True, exist_ok=False)
(args.output / 'test.c').write_text(prelude + actual + main)
subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-g', '-O1', '-fsanitize=address,undefined',
                str(args.output / 'test.c'), '-o', str(args.output / 'test')], check=True)
result = subprocess.run([str(args.output / 'test')], capture_output=True, text=True, check=True)
(args.output / 'report.json').write_text(json.dumps(dict(helper_sha256=hashlib.sha256(actual.encode()).hexdigest(),
    passed=True, actual_source=True, address_translation_and_types_mocked=True, actual_reset_handoff_verified=False,
    result=result.stdout.strip()), indent=2) + '\n')
print(result.stdout, end='')
