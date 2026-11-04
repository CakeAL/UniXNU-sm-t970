"""Exercise the real optional capacity sampler with isolated kernel API substitutes."""
from pathlib import Path
import subprocess
import tempfile
import unittest


class DataSpace(unittest.TestCase):
    def test_worker_errors_and_timeout(self):
        patch = (Path(__file__).resolve().parents[1] / 'patches/xnu/t970-data-space-report.patch').read_text()
        added = '\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
        block = added[added.index('/* T970_DATA_SPACE_BEGIN'):added.index('/* T970_DATA_SPACE_END */')]
        stub = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef int wait_result_t; typedef void *event_t; typedef void *thread_t; typedef int kern_return_t;
typedef struct node { int id; } *vnode_t; typedef struct mount { int flags; } *mount_t;
struct vfs_attr { uint64_t f_supported,f_active; uint32_t f_bsize; uint64_t f_blocks,f_bfree,f_bavail; };
struct stat { char f_fstypename[16]; };
static struct node root={1},device={7}; static struct mount mount; static struct stat statfs={"apfs"};
static int native_owner_data_device=7,mode,puts_count,waits;
#define NULLVP NULL
#define MNT_RDONLY 1
#define KERN_SUCCESS 0
#define THREAD_NULL NULL
#define THREAD_WAITING 1
#define THREAD_UNINT 1
#define THREAD_CONTINUE_NULL NULL
#define NSEC_PER_MSEC 1000000
#define VFSATTR_INIT(a) ((a)->f_supported=(a)->f_active=0)
#define VFSATTR_WANTED(a,b) ((a)->f_active|=1)
static void *vfs_context_kernel(void){return &root;}
static int vnode_lookup(const char *p,int f,vnode_t *v,void *c){assert(!strcmp(p,"/private/var")&&!f&&c);if(mode==1)return ENOENT;*v=&root;return 0;}
static mount_t vnode_mount(vnode_t v){assert(v==&root);return &mount;}
static vnode_t vfs_devvp(mount_t m){assert(m==&mount);return &device;}
static int vnode_specrdev(vnode_t v){return v->id;}
static int vfs_flags(mount_t m){return m->flags;}
static struct stat *vfs_statfs(mount_t m){assert(m==&mount);return &statfs;}
static int vfs_getattr(mount_t m,struct vfs_attr *a,void *c){assert(m==&mount&&c);if(mode==2)return EIO;a->f_supported=0x1d0;a->f_bsize=4096;a->f_blocks=100;a->f_bfree=42;a->f_bavail=40;return 0;}
static void vnode_put(vnode_t v){assert(v);++puts_count;}
static void thread_terminate_self(void){}
static int PE_parse_boot_argn(const char *n,void *v,unsigned sz){assert(!strcmp(n,"t970-data-space")&&sz==4);*(unsigned*)v=1;return 1;}
static int kernel_thread_start(void(*fn)(void*,int),void *p,thread_t *t){if(mode==3)return 7;*t=&root;if(mode!=4)fn(p,0);return 0;}
static void thread_deallocate(thread_t t){assert(t==&root);}
static void clock_interval_to_deadline(unsigned n,unsigned s,uint64_t *d){assert(n==100&&s==NSEC_PER_MSEC);*d=1;}
static int assert_wait_deadline(event_t e,int f,uint64_t d){assert(e&&f==THREAD_UNINT&&d);++waits;return THREAD_WAITING;}
static int thread_block(void *p){assert(!p);return 0;}
'''
        main = r'''
int main(void){char out[512];
for(mode=0;mode<=4;++mode){memset(&native_t970_data_space_result,0,sizeof(native_t970_data_space_result));native_t970_data_space_done=0;puts_count=waits=0;out[0]=0;native_t970_data_space_text(out,sizeof(out));
 if(mode==0){assert(strstr(out,"rc=0 phase=1 support=1d0 bsize=4096 blocks=100 free=42 avail=40")&&puts_count==2);}
 if(mode==1){assert(strstr(out,"rc=2 phase=0")&&puts_count==0);}
 if(mode==2){assert(strstr(out,"rc=5 phase=1")&&puts_count==2);}
 if(mode==3)assert(strstr(out,"worker start failed"));
 if(mode==4)assert(strstr(out,"pending")&&waits==20);
}
mode=0;device.id=8;native_t970_data_space_done=0;out[0]=0;native_t970_data_space_text(out,sizeof(out));assert(strstr(out,"rc=22 phase=0"));
return 0;}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source, exe = Path(tmp) / 'test.c', Path(tmp) / 'test'
            source.write_text(stub + block + main)
            subprocess.run(['xcrun', 'clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', str(source), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)
