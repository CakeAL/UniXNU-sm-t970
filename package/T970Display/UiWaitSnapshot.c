// SPDX-License-Identifier: MIT
// T970 bounded diagnostic adapted from UniXNU-umi@3eb7257 BootUiTraceProbe.c.
#include <kern/task.h>
#include <kern/thread.h>
#include <kern/simple_lock.h>
#include <machine/machine_routines.h>
#include <arm/thread.h>
#include <kern/misc_protos.h>
#include <string.h>
#include <vm/vm_map.h>
#include <kern/clock.h>
#include <kern/sched_prim.h>
#include <pexpert/pexpert.h>
// Same source-kernel private proc ABI as the reference BootProcessProbe.c.
struct proc; typedef struct proc *proc_t;
int proc_pid(proc_t);
void proc_name(int, char *, int);
task_t proc_task(proc_t);
void proc_iterate(unsigned,int (*)(proc_t,void *),void *,int (*)(proc_t,void *),void *);
#define PROC_RETURNED 0
#define PROC_RETURNED_DONE 1
#define PROC_ALLPROCLIST (1U<<0)
#define PROC_NOWAITTRANS (1U<<2)
/* T970_UI_WAIT_BEGIN: umi3eb7257 lock/copy pattern and bounded FP walk (MIT).
 * Stack mode reads user VM only in an isolated worker. The reporter waits at
 * most20 scheduler deadlines and never consumes a partially published buffer. */
#define T970_UI_WAIT_THREADS 4
#define T970_UI_STACK_FRAMES 8
struct native_t970_ui_wait_row {
 uint64_t pc,lr,fp,trap,arg1,arg3,frames[T970_UI_STACK_FRAMES];
 unsigned index,kstate,frames_used,frame_error;
};
struct native_t970_ui_wait_buffer { char text[1792]; unsigned used,selected; };
static struct native_t970_ui_wait_buffer capture;
static unsigned readUserStacks,captureStarted,captureDone,capturePhase,capturePid;
const char *native_t970_ui_wait_text(void);
static int ui_user_address(uint64_t address,unsigned size) {
 return address>=4096 && address<(UINT64_C(1)<<39) && size<=(UINT64_C(1)<<39)-address;
}
static void ui_stack_read(struct native_t970_ui_wait_row *row,vm_map_t map) {
 uint64_t fp=row->fp;
 if(!map){row->frame_error=4;return;}
 for(unsigned i=0;i<T970_UI_STACK_FRAMES && fp;++i) {
  uint64_t pair[2]={0};
  if(!ui_user_address(fp,sizeof(pair)) || (fp&15)){row->frame_error=2;break;}
  if(vm_map_read_user(map,fp,pair,sizeof(pair))!=KERN_SUCCESS){row->frame_error=1;break;}
  if(pair[1] && !ui_user_address(pair[1],4)){row->frame_error=2;break;}
  row->frames[row->frames_used++]=pair[1];
  if(!pair[0])break;
  if(pair[0]<=fp || pair[0]-fp>1048576){row->frame_error=3;break;}
  fp=pair[0];
 }
}
static int native_t970_ui_wait_collect(proc_t p,void *context)
{
 struct native_t970_ui_wait_buffer *out=context;
 char name[17]={0};int pid=proc_pid(p);proc_name(pid,name,sizeof(name));name[sizeof(name)-1]=0;
 if(strcmp(name,"SpringBoard") && strcmp(name,"backboardd"))return PROC_RETURNED;
 ++out->selected;
 __atomic_store_n(&capturePid,(unsigned)pid,__ATOMIC_RELAXED);
 __atomic_store_n(&capturePhase,2,__ATOMIC_RELAXED);
 struct native_t970_ui_wait_row rows[T970_UI_WAIT_THREADS]={0};
 unsigned count=0,visited=0,busy=0,total=0,slide=0;int status=0;task_t task=proc_task(p);
 vm_map_t map=NULL;
 if(!ml_get_interrupts_enabled())status=1;
 else if(!task)status=2;
 else if(!task_lock_try(task))status=3;
 else {
  total=(unsigned)task->thread_count;slide=task->task_shared_region_slide;
  if(readUserStacks && task->map){map=task->map;vm_map_reference(map);}
  thread_t thread;
  queue_iterate(&task->threads,thread,thread_t,task_threads) {
   if(visited>=T970_UI_WAIT_THREADS)break;
   ++visited;boolean_t irq=ml_set_interrupts_enabled(FALSE);
   if(!simple_lock_try(&thread->sched_lock,&thread_lck_grp)){++busy;ml_set_interrupts_enabled(irq);continue;}
   arm_saved_state_t *state=thread->machine.upcb;
   if(state && is_saved_state64(state)) {
    struct native_t970_ui_wait_row *r=&rows[count++];r->index=visited;r->kstate=thread->state;
    r->pc=get_saved_state_pc(state);r->lr=get_saved_state_lr(state);r->fp=get_saved_state_fp(state);
    r->trap=get_saved_state_reg(state,16);r->arg1=get_saved_state_reg(state,1);r->arg3=get_saved_state_reg(state,3);
   }
   thread_unlock(thread);ml_set_interrupts_enabled(irq);
  }
  task_unlock(task);
 }
 if(readUserStacks && count && rows[0].index==1) {
  __atomic_store_n(&capturePhase,3,__ATOMIC_RELAXED);
  ui_stack_read(&rows[0],map);
 }
 if(map)vm_map_deallocate(map);
 __atomic_store_n(&capturePhase,4,__ATOMIC_RELAXED);
 /* No formatting or user reads while task/scheduler locks or IRQ masking remain. */
 unsigned left=sizeof(out->text)-out->used;
 int n=snprintf(out->text+out->used,left,"\n%.12s p%d status=%d threads=%u visited=%u busy=%u slide=%x",name,pid,status,total,visited,busy,slide);
 if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
 for(unsigned i=0;i<count && out->used<sizeof(out->text)-1;++i) {
  struct native_t970_ui_wait_row *r=&rows[i];left=sizeof(out->text)-out->used;
  n=snprintf(out->text+out->used,left,"\n%c%u st=%x pc=%llx lr=%llx x16=%llx",name[0],r->index,r->kstate,
   (unsigned long long)r->pc,(unsigned long long)r->lr,(unsigned long long)r->trap);
  if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
  if(readUserStacks && r->index==1 && out->used<sizeof(out->text)-1) {
   left=sizeof(out->text)-out->used;
   n=snprintf(out->text+out->used,left,"\n%c FP=%llx n=%u e=%u",name[0],(unsigned long long)r->fp,r->frames_used,r->frame_error);
   if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   for(unsigned j=0;j<r->frames_used && out->used<sizeof(out->text)-1;++j) {
    left=sizeof(out->text)-out->used;n=snprintf(out->text+out->used,left," %llx",(unsigned long long)r->frames[j]);
    if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   }
  }
 }
 return out->selected>=2?PROC_RETURNED_DONE:PROC_RETURNED;
}
static void ui_collect(void) {
 memset(&capture,0,sizeof(capture));
 capture.used=(unsigned)snprintf(capture.text,sizeof(capture.text),"UI saved-regs: queue order; live/best-effort; stacks=%u",readUserStacks);
 __atomic_store_n(&capturePhase,1,__ATOMIC_RELAXED);
 proc_iterate(PROC_ALLPROCLIST|PROC_NOWAITTRANS,native_t970_ui_wait_collect,&capture,NULL,NULL);
 __atomic_store_n(&capturePhase,0,__ATOMIC_RELAXED);
 __atomic_store_n(&captureDone,1,__ATOMIC_RELEASE);
}
static void ui_stack_worker(void *parameter,wait_result_t result) {
 (void)parameter;(void)result;ui_collect();thread_terminate_self();
}
const char *native_t970_ui_wait_text(void)
{
 unsigned enabled=0;
 unsigned stackMode=PE_parse_boot_argn("t970-ui-stack",&enabled,sizeof(enabled)) && enabled==1;
 if(!stackMode){readUserStacks=0;ui_collect();return capture.text;}
 static char pending[128];
 if(!__atomic_exchange_n(&captureStarted,1,__ATOMIC_ACQ_REL)) {
  readUserStacks=1;
  __atomic_store_n(&captureDone,0,__ATOMIC_RELAXED);
  thread_t worker=THREAD_NULL;
  kern_return_t error=kernel_thread_start(ui_stack_worker,NULL,&worker);
  if(error!=KERN_SUCCESS){snprintf(pending,sizeof(pending),"UI stack worker start error=%d",error);return pending;}
  thread_deallocate(worker);
 }
 for(unsigned i=0;i<20 && !__atomic_load_n(&captureDone,__ATOMIC_ACQUIRE);++i) {
  uint64_t deadline=0;clock_interval_to_deadline(100,NSEC_PER_MSEC,&deadline);
  if(assert_wait_deadline((event_t)&captureStarted,THREAD_UNINT,deadline)==THREAD_WAITING)
   (void)thread_block(THREAD_CONTINUE_NULL);
 }
 if(__atomic_load_n(&captureDone,__ATOMIC_ACQUIRE))return capture.text;
 snprintf(pending,sizeof(pending),"UI stack worker busy phase=%u pid=%u (partial rows hidden)",
  __atomic_load_n(&capturePhase,__ATOMIC_RELAXED),__atomic_load_n(&capturePid,__ATOMIC_RELAXED));
 return pending;
}
/* T970_UI_WAIT_END */
