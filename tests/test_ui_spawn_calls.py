"""ASan exercise of actual optional spawn-return observer with copyinstr stand-in."""
from pathlib import Path
import subprocess,tempfile,unittest
class Calls(unittest.TestCase):
 def test_filter_errors_and_bounds(self):
  text=(Path(__file__).resolve().parents[1]/'patches/xnu/t970-ui-spawn-calls.patch').read_text()
  block='\n'.join(x[1:] for x in text.splitlines() if x.startswith('+') and not x.startswith('+++'))
  block=block[block.index('/* T970_UI_CALLS_BEGIN'):block.index('/* T970_UI_CALLS_END */')]
  harness=r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
typedef unsigned long long user_addr_t;
typedef struct proc {int pid;} *proc_t;
typedef struct ut {uint64_t uu_arg[8];} *uthread_t;
struct posix_spawn_args {user_addr_t pid,path,desc,argv,envp;};
#define SYS_posix_spawn 244
#define os_atomic_inc_orig(p,o) ((*(p))++)
static unsigned enabled,reads;
static int proc_getpid(proc_t p){return p->pid;}
static int PE_parse_boot_argn(const char *key,void *v,unsigned n){assert(!strcmp(key,"t970-ui-spawn-calls")&&n==4);*(unsigned *)v=enabled;return enabled!=0;}
static int copyinstr(user_addr_t address,char *out,size_t size,size_t *copied){
 ++reads;if(!address)return EFAULT;const char *src=(const char *)address;
 for(size_t i=0;i<size;++i){out[i]=src[i];if(!src[i]){*copied=i+1;return 0;}}return ENAMETOOLONG;
}
'''
  main=r'''
int main(void){
 struct proc init={1},other={9};struct ut ut={{0}};
 ut.uu_arg[1]=(uintptr_t)"/usr/libexec/backboardd";
 native_t970_ui_call_note(&init,244,13,&ut);assert(!reads);
 enabled=1;native_t970_ui_call_note(NULL,244,0,&ut);native_t970_ui_call_note(&other,244,0,&ut);native_t970_ui_call_note(&init,1,0,&ut);assert(!reads);
 native_t970_ui_call_note(&init,244,13,&ut);assert(native_t970_ui_calls[0]==1&&native_t970_ui_call_errors[0]==13);
 ut.uu_arg[1]=(uintptr_t)"/System/Library/CoreServices/SpringBoard.app/SpringBoard";
 native_t970_ui_call_note(&init,244,0,&ut);assert(native_t970_ui_calls[1]==1&&native_t970_ui_call_errors[1]==0);
 ut.uu_arg[1]=0;native_t970_ui_call_note(&init,244,0,&ut);
 char longpath[192];memset(longpath,'x',sizeof(longpath));ut.uu_arg[1]=(uintptr_t)longpath;native_t970_ui_call_note(&init,244,0,&ut);
 assert(native_t970_ui_copy_errors==2);assert(strstr(native_t970_ui_calls_text(),"bb=1/e13 sb=1/e0 path-copy-errors=2"));
}
'''
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'check.c';exe=Path(d)/'check';src.write_text(harness+block+main)
   subprocess.run(['xcrun','clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address',str(src),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
