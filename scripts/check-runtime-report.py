#!/usr/bin/env python3
"""Execute the prepared snapshot code with scheduler/process API substitutes."""
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
start = source.index('struct native_t970_runtime_snapshot {')
end = source.index('static int\nnative_owner_data_prepare(', start)
actual = source[start:end]
prelude = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <setjmp.h>
typedef struct process { int pid; char name[64]; } *proc_t;
typedef int wait_result_t;
typedef void *event_t;
typedef void *thread_t;
typedef int kern_return_t;
typedef void (*thread_continue_t)(void *,wait_result_t);
#define PROC_RETURNED 0
#define PROC_RETURNED_DONE 1
#define PROC_ALLPROCLIST 1
#define PROC_NOWAITTRANS 4
#define NSEC_PER_SEC 1000000000
#define NSEC_PER_MSEC 1000000
#define THREAD_UNINT 1
#define THREAD_WAITING 1
#define THREAD_CONTINUE_NULL NULL
#define THREAD_NULL NULL
#define KERN_SUCCESS 0
static struct process processes[1000];
static unsigned supplied,count,enabled,seconds,starts,deallocs,waits,blocks,iteration_calls;
static int start_error,wait_result=THREAD_WAITING;
static void *start_arg;
static thread_continue_t start_function;
static jmp_buf stop;
static char message[2048];
int native_owner_data_status=0,native_t970_watchdog_policy_status=0,native_t970_watchdog_policy_stage=4;
volatile uint64_t native_ufs_verified_blocks=123456;
static int main_state=1;
uint32_t processor_avail_count=1;
volatile uint32_t armcpu_smp_running,armcpu_smp_step[8],armcpu_smp_fail[8];
volatile int32_t armcpu_smp_psci_rc[8];
volatile uint32_t armcpu_core_timer[8],armcpu_core_sgi[8];
volatile uint64_t armcpu_ipi_sent,armcpu_ipi_selftest_sent,armcpu_ipi_interrupts;
void armcpu_ipi_selftest(uint64_t aff){assert(aff==0x100);++armcpu_ipi_selftest_sent;}
void armcpu_gic_diag(uint64_t aff,uint32_t *out){assert(aff==0x100);memset(out,0,8*sizeof(*out));}
void native_t970_trampoline_snapshot(uint64_t *out){for(unsigned i=0;i<8;++i)out[i]=0x100000000ULL+i;}
void native_t970_secondary_snapshot(uint32_t *out){for(unsigned i=0;i<8;++i)out[i]=i%5;}
int native_t970_initproc_main(void){return main_state;}
void native_t970_reset_context(uint64_t *out){
 const uint64_t values[6]={0x1000,0x1000,0x2000,0x100,0x3000,0x3000};memcpy(out,values,sizeof(values));
}
static int proc_pid(proc_t p){return p->pid;}
static void proc_name(int pid,char *name,int size){
 assert(pid>=0&&(unsigned)pid<supplied);snprintf(name,(size_t)size,"%s",processes[pid].name);
}
static void proc_iterate(unsigned flags,int (*callout)(proc_t,void*),void *arg,void *filter,void *filterarg){
 assert(flags==(PROC_ALLPROCLIST|PROC_NOWAITTRANS)&&!filter&&!filterarg);++iteration_calls;count=0;
 for(unsigned i=0;i<supplied;++i){++count;int result=callout(&processes[i],arg);assert(result==PROC_RETURNED||result==PROC_RETURNED_DONE);if(result==PROC_RETURNED_DONE)break;}
}
static void clock_interval_to_deadline(unsigned n,unsigned scale,uint64_t *out){assert(scale==NSEC_PER_SEC);*out=(uint64_t)n*scale;}
static int assert_wait_deadline(event_t e,int flags,uint64_t deadline){assert(e&&flags==THREAD_UNINT&&deadline>0);++waits;return wait_result;}
static int thread_block(void *continuation){assert(!continuation);++blocks;return 3;}
static int PE_parse_boot_argn(const char *name,void *out,int size){if(!strcmp(name,"t970-ipi-check"))return 0;assert(!strcmp(name,"t970-runtime-report")&&size==sizeof(unsigned));*(unsigned*)out=seconds;return (int)enabled;}
static kern_return_t kernel_thread_start(thread_continue_t function,void *arg,thread_t *thread){++starts;start_function=function;start_arg=arg;*thread=(void*)1;return start_error;}
static void thread_deallocate(thread_t t){assert(t==(void*)1);++deallocs;}
static void test_panic(const char *format,...) __attribute__((noreturn,format(printf,1,2)));
static void test_panic(const char *format,...){va_list ap;va_start(ap,format);vsnprintf(message,sizeof(message),format,ap);va_end(ap);longjmp(stop,1);}
#define panic(...) test_panic(__VA_ARGS__)
'''
main = r'''
static void reset(void){
 enabled=seconds=starts=deallocs=waits=blocks=iteration_calls=0;start_error=0;wait_result=THREAD_WAITING;
 native_t970_runtime_started=0;message[0]=0;main_state=1;
 supplied=1000;for(unsigned i=0;i<supplied;++i){processes[i].pid=(int)i;snprintf(processes[i].name,64,"proc%u",i);}
}
int main(void){
 char cpu[512];memset(cpu,'Z',sizeof(cpu));native_t970_smp_state(cpu,0);assert(cpu[0]=='Z');
 native_t970_smp_state(cpu,1);assert(!cpu[0]&&cpu[1]=='Z');
 native_t970_smp_state(cpu,2);assert(cpu[0]=='0'&&!cpu[1]&&cpu[2]=='Z');
 for(unsigned i=0;i<8;++i){armcpu_smp_step[i]=armcpu_smp_fail[i]=armcpu_core_timer[i]=armcpu_core_sgi[i]=UINT32_MAX;armcpu_smp_psci_rc[i]=INT32_MIN;}
 native_t970_smp_state(cpu,sizeof(cpu));assert(strlen(cpu)<sizeof(cpu)&&strstr(cpu,"7:4294967295/-2147483648/4294967295/4294967295/4294967295"));
 reset();native_t970_runtime_report_start();assert(!starts);
 enabled=1;native_t970_runtime_report_start();assert(!starts);
 for(unsigned n=4;n<=301;n+=297){reset();enabled=1;seconds=n;if(!setjmp(stop)){native_t970_runtime_report_start();assert(0);}assert(!starts&&strstr(message,"interval invalid"));}
 unsigned valid[]={5,10,300};for(unsigned j=0;j<3;++j){unsigned n=valid[j];reset();enabled=1;seconds=n;native_t970_runtime_report_start();native_t970_runtime_report_start();assert(starts==1&&deallocs==1&&start_function==native_t970_runtime_report&&(uintptr_t)start_arg==n);}
 reset();enabled=1;seconds=120;start_error=17;if(!setjmp(stop)){native_t970_runtime_report_start();assert(0);}assert(starts==1&&!deallocs&&strstr(message,"failed: 17"));
 reset();strcpy(processes[31].name,"watchdogd");strcpy(processes[32].name,"SpringBoard");strcpy(processes[33].name,"backboardd");strcpy(processes[34].name,"runningboardd");
 struct {struct native_t970_runtime_snapshot sample;uint64_t guard;} s={.guard=0x123456789abcdef0ULL};
 proc_iterate(PROC_ALLPROCLIST|PROC_NOWAITTRANS,native_t970_runtime_collect,&s.sample,NULL,NULL);
 assert(count==512&&s.sample.count==512&&s.sample.watchdog==31&&s.sample.springboard==32&&s.sample.backboard==33&&s.sample.runningboard==34);
 assert(s.sample.used<512&&strlen(s.sample.names)==s.sample.used&&s.guard==0x123456789abcdef0ULL);
 reset();for(unsigned i=0;i<18;++i)memset(processes[i].name,'X',63);
 struct native_t970_runtime_snapshot long_names={0};proc_iterate(PROC_ALLPROCLIST|PROC_NOWAITTRANS,native_t970_runtime_collect,&long_names,NULL,NULL);assert(long_names.used<512&&strlen(long_names.names)==long_names.used);
 for(int awakened=0;awakened<2;++awakened){reset();supplied=35;strcpy(processes[32].name,"SpringBoard");wait_result=awakened?0:THREAD_WAITING;
  if(!setjmp(stop)){native_t970_runtime_report((void*)120,0);assert(0);}
  assert(waits==1&&blocks==(unsigned)!awakened&&iteration_calls==1);
  assert(strstr(message,"main=1 n=35 wd=0 sb=32 bb=0 rb=0 D=0 W=0 S=4 blocks=123456"));
  assert(strstr(message,"E reset/found/common/C 0 1 2 3 4 0 1 2"));
  assert(strstr(message,"V target=100000000 ret=100000001 vb=100000002 pb=100000003 t1=100000004 t0=100000005 tcr=100000006 primary1=100000007"));
  assert(strstr(message,"R table=1000 want=1000 data1=2000 id1=100 handler=3000 start=3000"));
 }
 puts("PASS: actual runtime report bounds, process names/PIDs, 512 callback cap, scheduler yield, opt-in/range/once guards and thread failure");
 return 0;
}
'''
args.output.mkdir(parents=True, exist_ok=False)
(args.output / 'test.c').write_text(prelude + actual.replace('#include <kern/processor.h>\n', '') + main)
subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
                '-fsanitize=address,undefined', str(args.output / 'test.c'), '-o', str(args.output / 'test')], check=True)
result = subprocess.run([str(args.output / 'test')], capture_output=True, text=True, check=True)
report = dict(helper_sha256=hashlib.sha256(actual.encode()).hexdigest(), passed=True,
              scheduler_and_process_apis_mocked=True, hardware_timer_verified=False,
              hardware_process_snapshot_verified=False, result=result.stdout.strip())
(args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout, end='')
