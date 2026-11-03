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
#include <assert.h>
#include <errno.h>
struct uthread { uint64_t uu_thread; };
struct workqueue {
 uint64_t wq_reqcount,wq_flags,wq_thidlecount,wq_threads_scheduled,wq_constrained_threads_scheduled;
 uint64_t wq_thread_call_last_run,wq_timer_interval,wq_fulfilled,wq_creations;
 struct uthread *wq_creator;
};
typedef struct proc {struct workqueue *wq;} *proc_t;
static int held,busy,unlocks;
static struct workqueue *proc_get_wqptr(proc_t p){return p->wq;}
static int workq_lock_try(struct workqueue *w){(void)w;assert(!held);if(busy)return 0;held=1;return 1;}
static void workq_unlock(struct workqueue *w){(void)w;assert(held);held=0;++unlocks;}
static uint64_t mach_absolute_time(void){assert(held);return 100;}
static uint64_t uthread_tid(struct uthread *uth){assert(held);return uth->uu_thread;}
static uint64_t _wq_flags(struct workqueue *w){assert(held);return w->wq_flags;}
'''
        main = r'''
int main(void){
 struct proc p={0};struct {uint64_t out[11],guard;} s={{0},0x1234};
 assert(native_t970_workqueue_detail(&p,s.out)==EINVAL&&!held&&!unlocks);
 struct uthread creator={77};struct workqueue w={2,0x10,1,6,5,40,20,8,9,&creator};p.wq=&w;
 busy=1;assert(native_t970_workqueue_detail(&p,s.out)==EBUSY&&!held&&!unlocks&&!s.out[0]);
 busy=0;assert(!native_t970_workqueue_detail(&p,s.out)&&!held&&unlocks==1);
 assert(s.out[0]==2&&s.out[1]==0x10&&s.out[2]==1&&s.out[3]==6&&s.out[4]==5);
 assert(s.out[5]==40&&s.out[6]==100&&s.out[7]==20&&s.out[8]==77&&s.out[9]==8&&s.out[10]==9&&s.guard==0x1234);
 w.wq_creator=0;assert(!native_t970_workqueue_detail(&p,s.out)&&!s.out[8]&&!held&&unlocks==2);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            source, executable = Path(directory) / 'test.c', Path(directory) / 'test'
            source.write_text(prelude + helper + main)
            subprocess.run(['xcrun', 'clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)
