#!/usr/bin/env python3
"""Run the actual opt-in publication helper with cache/boot-argument substitutes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();source=a.source.read_text();lo=source.index('static void\nnative_t970_publish_reset_state(void)');hi=source.index('\n#endif',lo);actual=source[lo:hi]
prelude=r'''
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
#define FALSE 0
typedef uintptr_t vm_offset_t;
static uint64_t cpu_ttep=0x12345678c4325000ULL;
static struct {uint64_t tcr_el1;} sysreg_restore={0x22a51a251aULL};
static unsigned enabled,present,calls;
static int PE_parse_boot_argn(const char *name,void *out,int size){assert(!strcmp(name,"t970-smp-publish-state")&&size==4);*(uint32_t*)out=enabled;return present;}
static void flush_dcache(vm_offset_t va,unsigned bytes,int physical){assert(!physical);if(calls%2==0)assert(va==(uintptr_t)&cpu_ttep&&bytes==sizeof(cpu_ttep));else assert(va==(uintptr_t)&sysreg_restore&&bytes==sizeof(sysreg_restore));++calls;}
'''
main=r'''
int main(void){
 for(unsigned exists=0;exists<2;++exists)for(unsigned value=0;value<3;++value){
  present=exists;enabled=value;calls=0;native_t970_publish_reset_state();
  assert(calls==((exists&&value==1)?2u:0u));
  assert(cpu_ttep==0x12345678c4325000ULL&&sysreg_restore.tcr_el1==0x22a51a251aULL);
 }
 puts("PASS: six opt-in cases, two exact cache ranges/order, full-width state unchanged");
}
'''
a.output.mkdir(parents=True,exist_ok=False);c=a.output/'test.c';c.write_text(prelude+actual+main)
subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=address,undefined',str(c),'-o',str(a.output/'test')],check=True)
r=subprocess.run([str(a.output/'test')],capture_output=True,text=True,check=True)
(a.output/'report.json').write_text(json.dumps(dict(passed=True,actual_source=True,helper_sha256=hashlib.sha256(actual.encode()).hexdigest(),cases=6,live_values_unchanged=True,cache_ranges_and_order_checked=True,cache_primitive_mocked=True,hardware_cache_visibility_verified=False,result=r.stdout.strip()),indent=2)+'\n');print(r.stdout,end='')
