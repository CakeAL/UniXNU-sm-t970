"""Run the actual bounded spawn-note helper under host ASan with proc stand-ins."""
from pathlib import Path
import subprocess,tempfile,unittest
class SpawnState(unittest.TestCase):
 def test_kernel_owned_path_and_filters(self):
  patch=(Path(__file__).resolve().parents[1]/'patches/xnu/t970-ui-spawn-state.patch').read_text()
  block='\n'.join(line[1:] for line in patch.splitlines() if line.startswith('+') and not line.startswith('+++'))
  block=block[block.index('/* T970_UI_SPAWN_BEGIN'):block.index('/* T970_UI_SPAWN_END */')]
  code=r'''
#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stddef.h>
#include <stdbool.h>
#define MAXPATHLEN 1024
#define EXECUTABLE_KEY "executable_path="
typedef bool boolean_t;
typedef struct Proc {int pid;} Proc; typedef Proc *proc_t;
int proc_getpid(proc_t p) {return p->pid;}
typedef struct image_params {char *ip_strings,*ip_strendp;} image_params;
'''+block+r'''
int main() {
 Proc parent={1}, other={5}, child={91};
 char buf[256]="executable_path=/usr/libexec/backboardd";
 image_params im={buf,buf+strlen(buf)+1};
 native_t970_ui_spawn_note(&other,&child,&im,0,true);
 assert(native_t970_ui_spawns==0);
 native_t970_ui_spawn_note(&parent,&child,&im,13,false);
 assert(native_t970_ui_seen[0]==1 && native_t970_ui_pid[0]==91 && native_t970_ui_error[0]==13);
 native_t970_ui_spawn_note(&parent,&child,&im,0,true);
 assert(native_t970_ui_seen[0]==2 && native_t970_ui_exec[0]==1);
 strcpy(buf,"executable_path=/System/Library/CoreServices/SpringBoard.app/SpringBoard");
 im.ip_strendp=buf+strlen(buf)+1;
 native_t970_ui_spawn_note(&parent,&child,&im,0,true);
 assert(native_t970_ui_seen[1]==1);
 memset(buf,'X',sizeof(buf)); im.ip_strendp=buf+sizeof(buf);
 native_t970_ui_spawn_note(&parent,&child,&im,0,false);
 native_t970_ui_spawn_note(&parent,&child,NULL,0,false);
 assert(native_t970_ui_seen[0]==2 && native_t970_ui_seen[1]==1);
 char result[256];native_t970_ui_spawn_state(result,sizeof(result));
 assert(strstr(result,"bb seen/pid/err/activated=2/91/0/1"));
 char tiny[3]={'X','X','Y'};native_t970_ui_spawn_state(tiny,2);assert(tiny[1]==0 && tiny[2]=='Y');
 native_t970_ui_spawn_state(NULL,10);
}
'''
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'test.c';binary=Path(d)/'test';src.write_text(code)
   subprocess.run(['xcrun','clang','-std=c11','-fsanitize=address','-Wall','-Wextra','-Werror',str(src),'-o',str(binary)],check=True)
   subprocess.run([str(binary)],check=True)
