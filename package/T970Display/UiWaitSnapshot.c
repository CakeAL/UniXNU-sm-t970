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
 * most20 scheduler deadlines (40 in batch mode) and never consumes a partially published buffer. */
#define T970_UI_WAIT_THREADS 8
#define T970_UI_STACK_FRAMES 16
struct native_t970_ui_wait_row {
 uint64_t tid,wait; int priority,base;
 uint64_t pc,lr,fp,trap,arg0,arg1,arg3,frames[T970_UI_STACK_FRAMES];
 unsigned index,kstate,frames_used,frame_error;
};
struct native_t970_ui_wait_buffer { char text[8192]; unsigned used,selected; };
static struct native_t970_ui_wait_buffer capture;
/* Pinned XNU bsd/sys/proc_info.h ABI; avoid mixing BSD and Mach private headers. */
struct proc_workqueueinfo { uint32_t pwq_nthreads,pwq_runthreads,pwq_blockedthreads,pwq_state; };
_Static_assert(sizeof(struct proc_workqueueinfo)==16,"proc workqueue ABI");
int fill_procworkqueue(proc_t,struct proc_workqueueinfo *);
int native_t970_workqueue_detail(proc_t,uint64_t *);
static unsigned readUserStacks,captureStarted,captureDone,capturePhase,capturePid;
static unsigned censusTotal,censusRun,censusWait,censusUnint,censusOther,censusBusy;
const char *native_t970_ui_wait_text(void);
static int ui_user_address(uint64_t address,unsigned size) {
 return address>=4096 && address<(UINT64_C(1)<<39) && size<=(UINT64_C(1)<<39)-address;
}
static int ui_stack_selected(const char *name,unsigned index) {
 return readUserStacks==5 || readUserStacks==7 || readUserStacks==8 || readUserStacks==9 || readUserStacks==10 ? 1 : readUserStacks==1 ? index==1 : readUserStacks==4 ? 1 : readUserStacks==3 ? index<=2 : readUserStacks==2 && name[0]=='b' && index>1;
}
static void ui_stack_read(struct native_t970_ui_wait_row *row,vm_map_t map) {
 uint64_t fp=row->fp;
 if(!map){row->frame_error=4;return;}
 unsigned limit=(readUserStacks==9 || readUserStacks==10)?4:(readUserStacks==1 || readUserStacks==7)?8:T970_UI_STACK_FRAMES;
 for(unsigned i=0;i<limit && fp;++i) {
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
/* Mode6 takes two snapshots per process, sleeping with no task/workqueue locks. */
static void ui_queue_line(struct native_t970_ui_wait_buffer *out,proc_t p,unsigned sample) {
 uint64_t d[28]={0};int rc=native_t970_workqueue_detail(p,d);
 uint64_t age=0,interval=0;
 absolutetime_to_nanoseconds(d[6]>=d[5]?d[6]-d[5]:0,&age);
 absolutetime_to_nanoseconds(d[7],&interval);
 unsigned left=sizeof(out->text)-out->used;
 int n=snprintf(out->text+out->used,left,
  "\nW%u rc=%d req=%llu f=%llx idle=%llu sched=%llu con=%llu creator=%llx age_ms=%llu int_ms=%llu made=%llu done=%llu"
  "\nQ%u C(q/f/n)=%llu/%llx/%llu cap/active/busy=%llu/%llu/%llu limit=%llu O=%llu/%llx/%llu S=%llu/%llx/%llu mgr=%llu coop(q/run/lim)=%llu/%llu/%llu",
  sample,rc,(unsigned long long)d[0],(unsigned long long)d[1],(unsigned long long)d[2],(unsigned long long)d[3],(unsigned long long)d[4],(unsigned long long)d[8],
  (unsigned long long)(age/NSEC_PER_MSEC),(unsigned long long)(interval/NSEC_PER_MSEC),(unsigned long long)d[10],(unsigned long long)d[9],sample,
  (unsigned long long)d[11],(unsigned long long)d[12],(unsigned long long)d[13],(unsigned long long)d[14],(unsigned long long)d[15],(unsigned long long)d[16],(unsigned long long)d[17],
  (unsigned long long)d[18],(unsigned long long)d[19],(unsigned long long)d[20],(unsigned long long)d[21],(unsigned long long)d[22],(unsigned long long)d[23],
  (unsigned long long)d[24],(unsigned long long)d[25],(unsigned long long)d[26],(unsigned long long)d[27]);
 if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
}
static int native_t970_ui_wait_collect(proc_t p,void *context)
{
 struct native_t970_ui_wait_buffer *out=context;
 char name[17]={0};int pid=proc_pid(p);proc_name(pid,name,sizeof(name));name[sizeof(name)-1]=0;
 {task_t ct=proc_task(p);if(ct && task_lock_try(ct)){thread_t t;queue_iterate(&ct->threads,t,thread_t,task_threads){++censusTotal;if(t->state & TH_RUN)++censusRun;else if(t->state & TH_WAIT){if(t->state & TH_UNINT)++censusUnint;else ++censusWait;}else ++censusOther;}task_unlock(ct);}else ++censusBusy;}
 unsigned gestalt=!strncmp(name,"MobileGestalt",13) || !strncmp(name,"mobilegestalt",13);
 if(readUserStacks==8) {
  if(strcmp(name,"lsd"))return PROC_RETURNED;
 } else if(readUserStacks==10) {
  if(strcmp(name,"SpringBoard") && strcmp(name,"backboardd") && strcmp(name,"lsd"))return PROC_RETURNED;
 } else if(readUserStacks==7) {
  if(strcmp(name,"SpringBoard") && strcmp(name,"lsd"))return PROC_RETURNED;
 } else if(readUserStacks==5 || readUserStacks==6) {
  if(!gestalt && strcmp(name,"SpringBoard") && strcmp(name,"backboardd"))return PROC_RETURNED;
 } else if(readUserStacks==3 || readUserStacks==4) {
  if(strncmp(name,"MobileGestalt",13) && strncmp(name,"mobilegestalt",13))return PROC_RETURNED;
 } else if(strcmp(name,"SpringBoard") && strcmp(name,"backboardd"))return PROC_RETURNED;
 if(readUserStacks==6) {
  ++out->selected;
  __atomic_store_n(&capturePid,(unsigned)pid,__ATOMIC_RELAXED);
  __atomic_store_n(&capturePhase,5,__ATOMIC_RELAXED);
  unsigned left=sizeof(out->text)-out->used;
  int n=snprintf(out->text+out->used,left,"\n%.12s p%d queue progress (500ms deadline)",name,pid);
  if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
  ui_queue_line(out,p,0);
  uint64_t deadline=0;clock_interval_to_deadline(500,NSEC_PER_MSEC,&deadline);
  if(assert_wait_deadline((event_t)&capturePhase,THREAD_UNINT,deadline)==THREAD_WAITING)
   (void)thread_block(THREAD_CONTINUE_NULL);
  ui_queue_line(out,p,1);
  return out->selected>=3?PROC_RETURNED_DONE:PROC_RETURNED;
 }
 struct proc_workqueueinfo wq={0};int wqStatus=-1;
 uint64_t detail[28]={0};int detailStatus=-1;
 if(readUserStacks==5){wqStatus=fill_procworkqueue(p,&wq);detailStatus=native_t970_workqueue_detail(p,detail);}
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
   unsigned cap=(readUserStacks==4 || readUserStacks==5 || readUserStacks==8 || readUserStacks==9)?8:4;
   if(readUserStacks==10)cap=!strcmp(name,"backboardd")?6:5;
   if(visited>=cap)break;
   ++visited;if((readUserStacks==4 || readUserStacks==8) && visited<=4)continue;
   boolean_t irq=ml_set_interrupts_enabled(FALSE);
   if(!simple_lock_try(&thread->sched_lock,&thread_lck_grp)){++busy;ml_set_interrupts_enabled(irq);continue;}
   arm_saved_state_t *state=thread->machine.upcb;
   if(state && is_saved_state64(state)) {
    struct native_t970_ui_wait_row *r=&rows[count++];r->index=visited;r->kstate=thread->state;
    if(readUserStacks==5){r->tid=thread_tid(thread);r->wait=thread->wait_event;r->priority=thread->sched_pri;r->base=thread->base_pri;}
    if(readUserStacks==9 || readUserStacks==10)r->tid=thread_tid(thread);
    r->wait=thread->wait_event;
    r->pc=get_saved_state_pc(state);r->lr=get_saved_state_lr(state);r->fp=get_saved_state_fp(state);
    r->trap=get_saved_state_reg(state,16);r->arg0=get_saved_state_reg(state,0);r->arg1=get_saved_state_reg(state,1);r->arg3=get_saved_state_reg(state,3);
   }
   thread_unlock(thread);ml_set_interrupts_enabled(irq);
  }
  task_unlock(task);
 }
 for(unsigned i=0;i<count;++i)if(ui_stack_selected(name,rows[i].index)) {
  __atomic_store_n(&capturePhase,3,__ATOMIC_RELAXED);
  ui_stack_read(&rows[i],map);
 }
 if(map)vm_map_deallocate(map);
 __atomic_store_n(&capturePhase,4,__ATOMIC_RELAXED);
 /* No formatting or user reads while task/scheduler locks or IRQ masking remain. */
 unsigned left=sizeof(out->text)-out->used;
 int n=snprintf(out->text+out->used,left,"\n%.12s p%d status=%d threads=%u visited=%u busy=%u slide=%x",name,pid,status,total,visited,busy,slide);
 if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
 if(readUserStacks==5 && out->used<sizeof(out->text)-1) {
  left=sizeof(out->text)-out->used;
  n=snprintf(out->text+out->used,left," wq=%d:%u/%u/%u/%x",wqStatus,wq.pwq_nthreads,wq.pwq_runthreads,wq.pwq_blockedthreads,wq.pwq_state);
  if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
 }
 if(readUserStacks==5 && out->used<sizeof(out->text)-1) {
  left=sizeof(out->text)-out->used;
  n=snprintf(out->text+out->used,left,"\nW rc=%d req=%llu f=%llx idle=%llu sched=%llu con=%llu creator=%llx age=%llx int=%llx made=%llu done=%llu",detailStatus,
   (unsigned long long)detail[0],(unsigned long long)detail[1],(unsigned long long)detail[2],(unsigned long long)detail[3],(unsigned long long)detail[4],
   (unsigned long long)detail[8],(unsigned long long)(detail[6]>=detail[5]?detail[6]-detail[5]:0),(unsigned long long)detail[7],(unsigned long long)detail[10],(unsigned long long)detail[9]);
  if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
 }
 for(unsigned i=0;i<count && out->used<sizeof(out->text)-1;++i) {
  struct native_t970_ui_wait_row *r=&rows[i];left=sizeof(out->text)-out->used;
  if(readUserStacks==9 || readUserStacks==10) {
   n=snprintf(out->text+out->used,left,"\n%c%u id=%llx st=%x pc=%llx lr=%llx a0=%llx a1=%llx e=%u F",
    name[0],r->index,(unsigned long long)r->tid,r->kstate,(unsigned long long)r->pc,(unsigned long long)r->lr,(unsigned long long)r->arg0,(unsigned long long)r->arg1,r->frame_error);
   if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   for(unsigned j=0;j<r->frames_used && out->used<sizeof(out->text)-1;++j) {
    left=sizeof(out->text)-out->used;
    n=snprintf(out->text+out->used,left," %llx",(unsigned long long)r->frames[j]);
    if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   }
   if(r->kstate & 0x8) {
    left=sizeof(out->text)-out->used;
    n=snprintf(out->text+out->used,left,"\n%c%u w=%llx x16=%llx",name[0],r->index,(unsigned long long)r->wait,(unsigned long long)r->trap);
    if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   }
   continue;
  }
  if(readUserStacks==5) {
   n=snprintf(out->text+out->used,left,"\n%c%u id=%llx st=%x w=%llx p=%d/%d pc=%llx lr=%llx",name[0],r->index,(unsigned long long)r->tid,r->kstate,(unsigned long long)r->wait,r->priority,r->base,(unsigned long long)r->pc,(unsigned long long)r->lr);
   if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   unsigned same=i;
   for(unsigned k=0;k<i;++k)if(r->pc==rows[k].pc && r->lr==rows[k].lr && r->trap==rows[k].trap && r->frames_used==rows[k].frames_used && r->frame_error==rows[k].frame_error && !memcmp(r->frames,rows[k].frames,r->frames_used*sizeof(uint64_t))){same=k;break;}
   left=sizeof(out->text)-out->used;
   if(same<i) {
    n=snprintf(out->text+out->used,left," same=%c%u",name[0],rows[same].index);
    if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
    continue;
   }
   n=snprintf(out->text+out->used,left," n=%u/e%u\nF",r->frames_used,r->frame_error);
   if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   for(unsigned j=0;j<r->frames_used && out->used<sizeof(out->text)-1;++j) {
    left=sizeof(out->text)-out->used;n=snprintf(out->text+out->used,left," %llx",(unsigned long long)r->frames[j]);
    if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   }
   continue;
  }
  n=snprintf(out->text+out->used,left,"\n%c%u st=%x pc=%llx lr=%llx x16=%llx",name[0],r->index,r->kstate,(unsigned long long)r->pc,(unsigned long long)r->lr,(unsigned long long)r->trap);
  if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
  if(ui_stack_selected(name,r->index) && out->used<sizeof(out->text)-1) {
   left=sizeof(out->text)-out->used;
   n=snprintf(out->text+out->used,left,"\n%c%u FP=%llx n=%u e=%u",name[0],r->index,(unsigned long long)r->fp,r->frames_used,r->frame_error);
   if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   for(unsigned j=0;j<r->frames_used && out->used<sizeof(out->text)-1;++j) {
    left=sizeof(out->text)-out->used;n=snprintf(out->text+out->used,left," %llx",(unsigned long long)r->frames[j]);
    if(n>0)out->used+=(unsigned)n<left?(unsigned)n:left-1;
   }
  }
 }
 return out->selected>=(readUserStacks==5 || readUserStacks==10?3U:readUserStacks==8?1U:2U)?PROC_RETURNED_DONE:PROC_RETURNED;
}
static void ui_collect(void) {
 memset(&capture,0,sizeof(capture));
 capture.used=(unsigned)snprintf(capture.text,sizeof(capture.text),"UI saved-regs: queue order; live/best-effort; stacks=%u",readUserStacks);
 __atomic_store_n(&capturePhase,1,__ATOMIC_RELAXED);
 proc_iterate(PROC_ALLPROCLIST|PROC_NOWAITTRANS,native_t970_ui_wait_collect,&capture,NULL,NULL);
 if(readUserStacks>=5) {
  unsigned clipped=capture.used>=sizeof(capture.text)-96;
  if(clipped)capture.used=sizeof(capture.text)-96;
  snprintf(capture.text+capture.used,sizeof(capture.text)-capture.used,"\nUI batch end processes=%u clipped=%u",capture.selected,clipped);
  if(capture.used<sizeof(capture.text)-96) {
   unsigned left=sizeof(capture.text)-capture.used;
   int n=snprintf(capture.text+capture.used,left,"\nT tot=%u run=%u wait=%u unint=%u other=%u busy=%u",censusTotal,censusRun,censusWait,censusUnint,censusOther,censusBusy);
   if(n>0)capture.used+=(unsigned)n<left?(unsigned)n:left-1;
  }
 }
 __atomic_store_n(&capturePhase,0,__ATOMIC_RELAXED);
 __atomic_store_n(&captureDone,1,__ATOMIC_RELEASE);
}
static void ui_stack_worker(void *parameter,wait_result_t result) {
 (void)parameter;(void)result;ui_collect();thread_terminate_self();
}
const char *native_t970_ui_wait_text(void)
{
 unsigned enabled=0;
 unsigned stackMode=PE_parse_boot_argn("t970-ui-stack",&enabled,sizeof(enabled)) && (enabled>=1 && enabled<=10);
 if(!stackMode){readUserStacks=0;ui_collect();return capture.text;}
 static char pending[128];
 if(!__atomic_exchange_n(&captureStarted,1,__ATOMIC_ACQ_REL)) {
  readUserStacks=enabled;
  __atomic_store_n(&captureDone,0,__ATOMIC_RELAXED);
  thread_t worker=THREAD_NULL;
  kern_return_t error=kernel_thread_start(ui_stack_worker,NULL,&worker);
  if(error!=KERN_SUCCESS){snprintf(pending,sizeof(pending),"UI stack worker start error=%d",error);return pending;}
  thread_deallocate(worker);
 }
 for(unsigned i=0;i<(readUserStacks>=5?40U:20U) && !__atomic_load_n(&captureDone,__ATOMIC_ACQUIRE);++i) {
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
