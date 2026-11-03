"""Check actual read-only workqueue helper lock failures and snapshot bounds."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class WorkqueueDetail(unittest.TestCase):
    def test_trylock_and_snapshot(self):
        patch = (Path(__file__).resolve().parents[1] / 'patches/xnu/t970-ui-batch-detail.patch').read_text()
        added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
        helper = added[added.index('/* T970_WQ_DETAIL_BEGIN'):added.index('/* T970_WQ_DETAIL_END')]
        prelude = r'''
#include <stdint.h>
#include <stddef.h>
#include <assert.h>
#include <errno.h>
#define WORKQ_THREAD_QOS_MIN 1
#define WORKQ_THREAD_QOS_MAX 6
#define WORKQ_NUM_QOS_BUCKETS 6
struct workq_threadreq_s {unsigned tr_qos,tr_flags,tr_count;};
typedef struct workq_threadreq_s *workq_threadreq_t;
#define priority_queue_max(queue,type,entry) (*(queue))
static unsigned wq_max_parallelism[6]={8,8,8,8,8,8},wq_max_constrained_threads=64;
static unsigned _wq_bucket(unsigned qos){assert(qos>=1&&qos<=6);return qos-1;}
struct uthread { uint64_t uu_thread; };
struct workqueue {
 uint64_t wq_reqcount,wq_flags,wq_thidlecount,wq_threads_scheduled,wq_constrained_threads_scheduled;
 uint64_t wq_thread_call_last_run,wq_timer_interval,wq_fulfilled,wq_creations;
 struct uthread *wq_creator;
 workq_threadreq_t wq_constrained_queue,wq_overcommit_queue,wq_special_queue,wq_event_manager_threadreq;
 unsigned wq_cooperative_queue_best_req_qos,wq_cooperative_queue_scheduled_count[6],wq_cooperative_queue_has_limited_max_size;
};
typedef struct proc {struct workqueue *wq;} *proc_t;
static int held,busy,unlocks;
static unsigned _wq_thactive(struct workqueue *w){(void)w;assert(held);return 2;}
static unsigned _wq_thactive_aggregate_downto_qos(struct workqueue *w,unsigned active,unsigned qos,unsigned *b,void *m){(void)w;assert(held&&qos==4&&!m);*b=1;return active;}
static struct workqueue *proc_get_wqptr(proc_t p){return p->wq;}
static int workq_lock_try(struct workqueue *w){(void)w;assert(!held);if(busy)return 0;held=1;return 1;}
static void workq_unlock(struct workqueue *w){(void)w;assert(held);held=0;++unlocks;}
static uint64_t mach_absolute_time(void){assert(held);return 100;}
static uint64_t uthread_tid(struct uthread *uth){assert(held);return uth->uu_thread;}
static uint64_t _wq_flags(struct workqueue *w){assert(held);return w->wq_flags;}
'''
        main = r'''
int main(void){
 struct proc p={0};struct {uint64_t out[28],guard;} s={{0},0x1234};
 assert(native_t970_workqueue_detail(&p,s.out)==EINVAL&&!held&&!unlocks);
 struct uthread creator={77};struct workqueue w={.wq_reqcount=2,.wq_flags=0x10,.wq_thidlecount=1,.wq_threads_scheduled=6,.wq_constrained_threads_scheduled=5,
 .wq_thread_call_last_run=40,.wq_timer_interval=20,.wq_fulfilled=8,.wq_creations=9,.wq_creator=&creator};
 struct workq_threadreq_s c={4,1,3},o={5,4,2};w.wq_constrained_queue=&c;w.wq_overcommit_queue=&o;p.wq=&w;
 busy=1;assert(native_t970_workqueue_detail(&p,s.out)==EBUSY&&!held&&!unlocks&&!s.out[0]);
 busy=0;assert(!native_t970_workqueue_detail(&p,s.out)&&!held&&unlocks==1);
 assert(s.out[0]==2&&s.out[1]==0x10&&s.out[2]==1&&s.out[3]==6&&s.out[4]==5);
 assert(s.out[5]==40&&s.out[6]==100&&s.out[7]==20&&s.out[8]==77&&s.out[9]==8&&s.out[10]==9&&s.guard==0x1234);
 assert(s.out[11]==4&&s.out[12]==1&&s.out[13]==3&&s.out[14]==8&&s.out[15]==2&&s.out[16]==1&&s.out[17]==64);
 assert(s.out[18]==5&&s.out[19]==4&&s.out[20]==2&&!s.out[21]&&!s.out[24]&&s.guard==0x1234);
 w.wq_constrained_queue=0;w.wq_creator=0;assert(!native_t970_workqueue_detail(&p,s.out)&&!s.out[8]&&!held&&unlocks==2);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source, executable = Path(directory) / 'test.c', Path(directory) / 'test'
            source.write_text(prelude + helper + main)
            subprocess.run(['xcrun', 'clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
