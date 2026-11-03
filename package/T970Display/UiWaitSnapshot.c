// SPDX-License-Identifier: MIT
// T970 bounded diagnostic adapted from UniXNU-umi@3eb7257 BootUiTraceProbe.c.
#include <kern/task.h>
#include <kern/thread.h>
#include <kern/simple_lock.h>
#include <machine/machine_routines.h>
#include <arm/thread.h>
#include <kern/misc_protos.h>
#include <string.h>
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
/* T970_UI_WAIT_BEGIN: kernel-owned saved registers only, no VM reads or suspension.
 * Lock/copy pattern: UniXNU-umi@3eb7257 BootUiTraceProbe.c (MIT). */
#define T970_UI_WAIT_THREADS 4
struct native_t970_ui_wait_row { uint64_t pc,lr,trap,arg1,arg3; unsigned index; };
struct native_t970_ui_wait_buffer { char text[1408]; unsigned used,selected; };
const char *native_t970_ui_wait_text(void);
static int native_t970_ui_wait_collect(proc_t p,void *context)
{
 struct native_t970_ui_wait_buffer *out=context;
 char name[17]={0};int pid=proc_pid(p);proc_name(pid,name,sizeof(name));name[sizeof(name)-1]=0;
 if(strcmp(name,"SpringBoard") && strcmp(name,"backboardd"))return PROC_RETURNED;
 ++out->selected;
 struct native_t970_ui_wait_row rows[T970_UI_WAIT_THREADS]={0};
 unsigned count=0,visited=0,busy=0,total=0,slide=0;int status=0;task_t task=proc_task(p);
 if(!ml_get_interrupts_enabled())status=1;
 else if(!task)status=2;
 else if(!task_lock_try(task))status=3;
 else {
  total=(unsigned)task->thread_count;slide=task->task_shared_region_slide;thread_t thread;
  queue_iterate(&task->threads,thread,thread_t,task_threads) {
   if(visited>=T970_UI_WAIT_THREADS)break;
   ++visited;boolean_t irq=ml_set_interrupts_enabled(FALSE);
   if(!simple_lock_try(&thread->sched_lock,&thread_lck_grp)){++busy;ml_set_interrupts_enabled(irq);continue;}
   arm_saved_state_t *state=thread->machine.upcb;
   if(state && is_saved_state64(state)) {
    struct native_t970_ui_wait_row *r=&rows[count++];r->index=visited;
    r->pc=get_saved_state_pc(state);r->lr=get_saved_state_lr(state);r->trap=get_saved_state_reg(state,16);
    r->arg1=get_saved_state_reg(state,1);r->arg3=get_saved_state_reg(state,3);
   }
   thread_unlock(thread);ml_set_interrupts_enabled(irq);
  }
  task_unlock(task);
 }
 /* Formatting occurs after every task/thread lock has been released and IRQ state restored. */
 unsigned left=sizeof(out->text)-out->used;
 int n=snprintf(out->text+out->used,left,"\n%.12s p%d status=%d threads=%u visited=%u busy=%u slide=%x",name,pid,status,total,visited,busy,slide);
 if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
 for(unsigned i=0;i<count && out->used<sizeof(out->text)-1;++i) {
  struct native_t970_ui_wait_row *r=&rows[i];left=sizeof(out->text)-out->used;
  n=snprintf(out->text+out->used,left,"\n%c%u pc=%llx lr=%llx x16=%llx x1=%llx x3=%llx",name[0],r->index,
   (unsigned long long)r->pc,(unsigned long long)r->lr,(unsigned long long)r->trap,
   (unsigned long long)r->arg1,(unsigned long long)r->arg3);
  if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
 }
 return out->selected>=2?PROC_RETURNED_DONE:PROC_RETURNED;
}
const char *native_t970_ui_wait_text(void)
{
 static struct native_t970_ui_wait_buffer out;memset(&out,0,sizeof(out));
 out.used=(unsigned)snprintf(out.text,sizeof(out.text),"UI saved-regs: queue order; live/best-effort; no user stack reads");
 proc_iterate(PROC_ALLPROCLIST|PROC_NOWAITTRANS,native_t970_ui_wait_collect,&out,NULL,NULL);
 return out.text;
}
/* T970_UI_WAIT_END */
