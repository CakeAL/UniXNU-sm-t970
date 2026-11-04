"""Actual register sampler: bounded traversal, try-lock failures and IRQ restoration."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class WaitState(unittest.TestCase):
    def test_lock_copy_and_bounds(self):
        added = (Path(__file__).resolve().parents[1] / 'package/T970Display/UiWaitSnapshot.c').read_text()
        block = added[added.index('/* T970_UI_WAIT_BEGIN'):added.index('/* T970_UI_WAIT_END */')]
        stub = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <assert.h>
typedef int boolean_t;
#define FALSE 0
#define PROC_RETURNED 0
#define PROC_RETURNED_DONE 1
#define PROC_ALLPROCLIST 1
#define PROC_NOWAITTRANS 4
typedef struct state { uint64_t pc,lr,fp,regs[17]; int is64; } arm_saved_state_t;
typedef struct thread { struct thread *next; int sched_lock; unsigned state; uint64_t wait_event; int sched_pri,base_pri; struct {arm_saved_state_t *upcb;} machine; } *thread_t;
typedef struct test_map {unsigned refs,reads;int fail;} *vm_map_t;
static struct test_map map_storage;static uint64_t fake_frames[20][2];
typedef struct task { thread_t threads; unsigned thread_count; int busy; unsigned task_shared_region_slide; vm_map_t map; } *task_t;
typedef struct proc { int pid; char name[17]; task_t task; } *proc_t;
static int irq=1,entry_irq=1,taskHeld,schedHeld,thread_lck_grp;
static unsigned copies,visits;
static struct proc processes[3];
static int proc_pid(proc_t p){return p->pid;}
static void proc_name(int pid,char *out,unsigned size){assert(pid>=0&&pid<3);snprintf(out,size,"%s",processes[pid].name);}
static uint64_t thread_tid(thread_t th){return (uint64_t)(uintptr_t)th;}
static task_t proc_task(proc_t p){return p->task;}
static int ml_get_interrupts_enabled(void){return irq;}
static int ml_set_interrupts_enabled(int value){int old=irq;irq=value;return old;}
static int task_lock_try(task_t task){assert(!taskHeld&&!schedHeld);if(task->busy)return 0;taskHeld=1;return 1;}
static void task_unlock(task_t task){(void)task;assert(taskHeld&&!schedHeld&&irq==entry_irq);taskHeld=0;}
static int simple_lock_try(int *lock,int *group){assert(taskHeld&&!schedHeld&&!irq&&group==&thread_lck_grp);if(*lock)return 0;schedHeld=1;return 1;}
static void thread_unlock(thread_t thread){(void)thread;assert(taskHeld&&schedHeld&&!irq);schedHeld=0;}
static int is_saved_state64(arm_saved_state_t *s){assert(taskHeld&&schedHeld&&!irq);return s->is64;}
static uint64_t get_saved_state_pc(arm_saved_state_t *s){++copies;assert(taskHeld&&schedHeld&&!irq);return s->pc;}
static uint64_t get_saved_state_lr(arm_saved_state_t *s){return s->lr;}
static uint64_t get_saved_state_fp(arm_saved_state_t *s){return s->fp;}
static uint64_t get_saved_state_reg(arm_saved_state_t *s,unsigned n){return s->regs[n];}
#define queue_iterate(head,thread,type,field) for(thread=*(head);thread;thread=thread->next)
static void proc_iterate(unsigned flags,int (*callback)(proc_t,void *),void *context,void *filter,void *arg){
 assert(flags==(PROC_ALLPROCLIST|PROC_NOWAITTRANS)&&!filter&&!arg);
 for(unsigned i=0;i<3;++i){++visits;if(callback(&processes[i],context)==PROC_RETURNED_DONE)break;}
}
static int unlocked_snprintf(char *out,size_t size,const char *format,...){
 assert(!taskHeld&&!schedHeld&&irq==entry_irq);
 va_list ap;va_start(ap,format);int n=vsnprintf(out,size,format,ap);va_end(ap);return n;
}

typedef int kern_return_t,wait_result_t;
typedef void *event_t;
#define KERN_SUCCESS 0
#define THREAD_NULL NULL
#define THREAD_UNINT 1
#define THREAD_WAITING 1
#define THREAD_CONTINUE_NULL NULL
#define NSEC_PER_MSEC 1000000
static unsigned userStacks,workerStarts,workerDrops,workerStops,waitCount,stalled;
static int workerError;
static int PE_parse_boot_argn(const char *name,void *out,unsigned size){assert(!strcmp(name,"t970-ui-stack")&&size==4);*(unsigned*)out=userStacks;return userStacks!=0;}
static void vm_map_reference(vm_map_t map){assert(taskHeld);++map->refs;}
static void vm_map_deallocate(vm_map_t map){assert(!taskHeld&&!schedHeld&&map->refs);--map->refs;}
static int vm_map_read_user(vm_map_t map,uint64_t address,void *out,unsigned size){
 assert(!taskHeld&&!schedHeld&&irq&&map->refs&&size==16);++map->reads;
 if(map->fail)return 1;assert(address>=0x10000&&address<0x10140&&!(address&15));memcpy(out,fake_frames[(address-0x10000)/16],16);return 0;
}
static int kernel_thread_start(void (*fn)(void*,int),void *arg,thread_t *thread){++workerStarts;if(workerError)return workerError;*thread=(thread_t)1;if(!stalled)fn(arg,0);return 0;}
static void thread_deallocate(thread_t thread){assert(thread==(thread_t)1);++workerDrops;}
static void thread_terminate_self(void){++workerStops;}
static void clock_interval_to_deadline(unsigned n,unsigned scale,uint64_t *deadline){assert((n==100||n==500)&&scale==NSEC_PER_MSEC);*deadline=(uint64_t)n*scale;}
static int assert_wait_deadline(event_t event,int flags,uint64_t deadline){assert(event&&flags==THREAD_UNINT&&deadline);return THREAD_WAITING;}
static void absolutetime_to_nanoseconds(uint64_t ticks,uint64_t *ns){assert(!taskHeld&&!schedHeld);*ns=ticks*1000000;}
static int thread_block(void *continuation){assert(!continuation);++waitCount;return 0;}

#define snprintf unlocked_snprintf
'''
        main = r'''
#undef snprintf
static unsigned wqCalls;static int wqError;
int fill_procworkqueue(proc_t p,struct proc_workqueueinfo *info){(void)p;assert(!taskHeld&&!schedHeld&&irq);++wqCalls;if(wqError)return wqError;*info=(struct proc_workqueueinfo){7,1,6,4};return 0;}
int native_t970_workqueue_detail(proc_t p,uint64_t *out){(void)p;assert(!taskHeld&&!schedHeld&&irq);out[0]=2;out[6]=100;out[5]=40;return 0;}
int main(void){
 struct state states[10];struct thread threads[10];memset(states,0,sizeof(states));memset(threads,0,sizeof(threads));
 for(unsigned i=0;i<10;++i){states[i].is64=1;states[i].pc=UINT64_MAX;states[i].lr=UINT64_MAX;states[i].regs[16]=UINT64_MAX;states[i].regs[1]=UINT64_MAX;states[i].regs[3]=UINT64_MAX;threads[i].state=1;threads[i].machine.upcb=&states[i];threads[i].next=i==9?NULL:&threads[i+1];}
 struct task task={threads,10,0,0x12340000,&map_storage};
 processes[0]=(struct proc){0,"SpringBoard",&task};processes[1]=(struct proc){1,"backboardd",&task};processes[2]=(struct proc){2,"ignored",&task};
 const char *text=native_t970_ui_wait_text();assert(visits==2&&copies==8&&strlen(text)<1792);assert(strstr(text,"threads=10 visited=4 busy=0"));assert(strstr(text,"slide=12340000"));assert(strstr(text,"S4 st=1 pc=ffffffffffffffff"));assert(strstr(text,"b4 st=1 pc=ffffffffffffffff"));assert(!strstr(text,"S5"));
 copies=0;threads[0].sched_lock=1;text=native_t970_ui_wait_text();assert(copies==6&&strstr(text,"busy=1"));assert(irq==1&&!taskHeld&&!schedHeld);
 task.busy=1;text=native_t970_ui_wait_text();assert(strstr(text,"status=3 threads=0 visited=0 busy=0"));task.busy=0;
 processes[0].task=processes[1].task=NULL;text=native_t970_ui_wait_text();assert(strstr(text,"status=2"));
 irq=entry_irq=0;text=native_t970_ui_wait_text();assert(strstr(text,"status=1")&&!irq);irq=entry_irq=1;
 processes[0].task=&task;threads[0].sched_lock=0;threads[0].machine.upcb=NULL;states[1].is64=0;
 copies=0;text=native_t970_ui_wait_text();assert(copies==2&&strstr(text,"S3 st=1 pc=")&&!strstr(text,"S1 st=1 pc="));
 struct {struct native_t970_ui_wait_buffer out;uint64_t guard;} checked={0};checked.guard=0x123456789abcdef0ULL;
 checked.out.used=sizeof(checked.out.text)-2;
 native_t970_ui_wait_collect(&processes[0],&checked.out);assert(checked.guard==0x123456789abcdef0ULL&&checked.out.used==sizeof(checked.out.text)-1&&!checked.out.text[sizeof(checked.out.text)-1]);

 processes[0].task=processes[1].task=&task;threads[0].machine.upcb=&states[0];states[1].is64=1;
 states[0].fp=0x10000;fake_frames[0][0]=0x10010;fake_frames[0][1]=0x180001000;fake_frames[1][1]=0x180002000;
 userStacks=1;text=native_t970_ui_wait_text();assert(workerStarts==1&&workerDrops==1&&workerStops==1);
 assert(strstr(text,"n=2 e=0 180001000 180002000")&&map_storage.reads==4&&!map_storage.refs);
 captureStarted=captureDone=0;map_storage.fail=1;text=native_t970_ui_wait_text();assert(strstr(text,"n=0 e=1"));map_storage.fail=0;
 captureStarted=captureDone=0;states[0].fp=0x10003;text=native_t970_ui_wait_text();assert(strstr(text,"n=0 e=2"));
 captureStarted=captureDone=0;states[0].fp=0x10000;fake_frames[0][0]=0x10000;text=native_t970_ui_wait_text();assert(strstr(text,"n=1 e=3"));
 captureStarted=captureDone=0;userStacks=2;states[1].fp=states[2].fp=0x10000;fake_frames[0][0]=0x10010;
 text=native_t970_ui_wait_text();assert(strstr(text,"stacks=2")&&strstr(text,"b2 FP=")&&strstr(text,"b3 FP="));
 assert(!strstr(text,"b1 FP=")&&!strstr(text,"S1 FP=")&&!map_storage.refs);userStacks=1;
 captureStarted=captureDone=0;userStacks=2;
 for(unsigned i=0;i<20;++i){fake_frames[i][0]=0x10000+16*(i+1);fake_frames[i][1]=0x180001000+4*i;}
 text=native_t970_ui_wait_text();assert(strstr(text,"n=16 e=0")&&!map_storage.refs);userStacks=1;
 captureStarted=captureDone=0;userStacks=3;processes[2].task=&task;strcpy(processes[2].name,"MobileGestaltHel");
 text=native_t970_ui_wait_text();assert(strstr(text,"stacks=3")&&strstr(text,"MobileGestal p2")&&strstr(text,"M1 FP=")&&strstr(text,"M2 FP="));
 assert(!strstr(text,"M3 FP=")&&!strstr(text,"backboardd p")&&!map_storage.refs);userStacks=1;
 captureStarted=captureDone=0;userStacks=4;
 for(unsigned i=4;i<8;++i)states[i].fp=0x10000;
 text=native_t970_ui_wait_text();assert(strstr(text,"stacks=4")&&strstr(text,"visited=8")&&strstr(text,"M5 FP=")&&strstr(text,"M8 FP="));
 assert(!strstr(text,"M1 st=")&&!strstr(text,"M9 st=")&&!map_storage.refs);userStacks=1;
 captureStarted=captureDone=0;userStacks=5;wqCalls=0;
 text=native_t970_ui_wait_text();assert(wqCalls==3&&strstr(text,"UI batch end processes=3 clipped=0")&&strstr(text,"wq=0:7/1/6/4"));
 assert(strstr(text,"M8 id=")&&strstr(text,"S8 id=")&&strstr(text,"b8 id=")&&strstr(text,"same=")&&!map_storage.refs);
 captureStarted=captureDone=0;wqError=16;text=native_t970_ui_wait_text();assert(strstr(text,"wq=16:0/0/0/0"));wqError=0;userStacks=1;
 captureStarted=captureDone=0;userStacks=6;unsigned readsBefore=map_storage.reads,copiesBefore=copies,waitsBefore=waitCount;
 text=native_t970_ui_wait_text();assert(strstr(text,"queue progress")&&strstr(text,"W0 rc=0")&&strstr(text,"W1 rc=0")&&strstr(text,"Q1 C(q/f/n)")&&strstr(text,"age_ms=60")&&strstr(text,"UI batch end processes=3 clipped=0"));
 assert(map_storage.reads==readsBefore&&copies==copiesBefore&&waitCount==waitsBefore+3&&!map_storage.refs);
 captureStarted=captureDone=0;userStacks=7;copiesBefore=copies;strcpy(processes[2].name,"lsd");
 text=native_t970_ui_wait_text();assert(strstr(text,"stacks=7")&&strstr(text,"SpringBoard p0")&&strstr(text,"lsd p2")&&strstr(text,"S4 FP=")&&strstr(text,"l4 FP=")&&!strstr(text,"S5 st=")&&!strstr(text,"l5 st=")&&!strstr(text,"backboardd p")&&strstr(text,"UI batch end processes=2 clipped=0"));
 assert(copies==copiesBefore+8&&strstr(text,"n=8 e=0")&&!map_storage.refs);
 waitCount=0;userStacks=1;
 captureStarted=captureDone=0;workerError=17;text=native_t970_ui_wait_text();assert(strstr(text,"worker start error=17"));workerError=0;
 captureStarted=captureDone=0;stalled=1;text=native_t970_ui_wait_text();assert(waitCount==20&&strstr(text,"partial rows hidden"));
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source, exe = Path(directory) / 'test.c', Path(directory) / 'test'
            source.write_text(stub + block + main)
            subprocess.run(['xcrun','clang','-std=c11','-Wall','-Wextra','-Werror',
                            '-fsanitize=address,undefined',str(source),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
