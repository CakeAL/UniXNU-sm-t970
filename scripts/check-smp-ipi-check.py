#!/usr/bin/env python3
"""Run actual bounded SGI-check logic using scheduler and ArmCpu API substitutes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();source=a.source.read_text();lo=source.index('struct native_t970_ipi_snapshot {');hi=source.index('static uint32_t native_t970_runtime_started;',lo);actual=source[lo:hi]
prelude=r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
#define NSEC_PER_MSEC 1000000
#define THREAD_UNINT 1
#define THREAD_WAITING 1
#define THREAD_CONTINUE_NULL NULL
typedef void *event_t;
static unsigned present,enabled,waits,blocks,diags,deliver;
uint32_t processor_avail_count;
volatile uint32_t armcpu_smp_step[8],armcpu_core_sgi[8];
volatile uint64_t armcpu_ipi_sent,armcpu_ipi_selftest_sent,armcpu_ipi_interrupts;
static int PE_parse_boot_argn(const char *name,void *out,int size){assert(!strcmp(name,"t970-ipi-check")&&size==4);*(uint32_t*)out=enabled;return present;}
void armcpu_ipi_selftest(uint64_t aff){assert(aff==0x100);++armcpu_ipi_selftest_sent;}
void armcpu_gic_diag(uint64_t aff,uint32_t *out){assert(aff==0x100&&blocks==1);++diags;for(unsigned i=0;i<8;++i)out[i]=0x1000+i;}
static void clock_interval_to_deadline(unsigned count,unsigned scale,uint64_t *out){assert(count==100&&scale==NSEC_PER_MSEC);*out=(uint64_t)count*scale;}
static int assert_wait_deadline(event_t e,int flags,uint64_t deadline){assert(e&&flags==THREAD_UNINT&&deadline==100000000);++waits;return THREAD_WAITING;}
static int thread_block(void *cont){assert(!cont);++blocks;armcpu_core_sgi[1]+=deliver;armcpu_ipi_interrupts+=deliver;return 0;}
'''
main=r'''
int main(void){
 unsigned cases=0;
 for(unsigned ex=0;ex<2;++ex)for(unsigned value=0;value<3;++value)for(unsigned ready=0;ready<3;++ready)for(unsigned received=0;received<2;++received){
  present=ex;enabled=value;deliver=received;waits=blocks=diags=0;armcpu_ipi_sent=9;armcpu_ipi_selftest_sent=0;armcpu_ipi_interrupts=0;armcpu_core_sgi[1]=11;
  processor_avail_count=ready?2:1;armcpu_smp_step[1]=ready==2?7:6;
  struct {struct native_t970_ipi_snapshot ipi;uint64_t guard;} out={.guard=0xabcdef0123456789ULL};
  native_t970_ipi_check(&out.ipi);
  if(!ex||value!=1){assert(!out.ipi.attempted&&!waits&&!blocks&&!diags&&!armcpu_ipi_selftest_sent);}
  else if(ready!=2){assert(out.ipi.attempted==2&&!waits&&!blocks&&!diags&&!armcpu_ipi_selftest_sent);}
  else {assert(out.ipi.attempted==1&&waits==1&&blocks==1&&diags==1&&armcpu_ipi_selftest_sent==1);assert(out.ipi.before==11&&out.ipi.after==11+received&&out.ipi.sent==9&&out.ipi.tested==1&&out.ipi.received==received);for(unsigned i=0;i<8;++i)assert(out.ipi.gic[i]==0x1000+i);}
  assert(out.guard==0xabcdef0123456789ULL);++cases;
 }
 printf("PASS: %u actual IPI helper cases, opt-in/readiness guards, one send, 100ms scheduler yield, delivered/undelivered snapshots and output bounds\n",cases);
}
'''
a.output.mkdir(parents=True,exist_ok=False);c=a.output/'test.c';c.write_text(prelude+actual+main)
subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=address,undefined',str(c),'-o',str(a.output/'test')],check=True)
r=subprocess.run([str(a.output/'test')],capture_output=True,text=True,check=True)
(a.output/'report.json').write_text(json.dumps(dict(passed=True,cases=36,actual_source=True,helper_sha256=hashlib.sha256(actual.encode()).hexdigest(),scheduler_and_armcpu_apis_mocked=True,hardware_ipi_delivery_verified=False,result=r.stdout.strip()),indent=2)+'\n');print(r.stdout,end='')
