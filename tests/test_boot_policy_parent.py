#!/usr/bin/env python3
"""Exercise the policy's actual parent/child mkdir sequence with injected failures."""
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
source = (root / 'package/BootWatchdogPolicy.c').read_text()
start = source.index(' failed_step="db copyout";')
end = source.index(' failed_step="path copyout";', start)
body = source[start:end]
prefix = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#define EEXIST 17
#define ENOENT 2
struct mkdir_args { uint64_t path; int mode; };
static char target[128]; static int calls, parent_result, child_result, copy_fail;
static int fake_copyout(const void *p, uint64_t q, unsigned long n) {
 (void)q; if(copy_fail) return 14; assert(n<=sizeof(target)); memcpy(target,p,n); return 0;
}
static int fake_mkdir(void *p, struct mkdir_args *a, int *r) {
 (void)p; (void)r; assert(a->mode==0755); ++calls;
 if(calls==1){assert(!strcmp(target,"/private/var/db")); return parent_result;}
 assert(!strcmp(target,"/private/var/db/com.apple.xpc.launchd")); return child_result;
}
#define copyout fake_copyout
#define mkdir fake_mkdir
static int exercise(void) {
 int error=0,result=0; void *p=0; uint64_t scratch=0; const char *failed_step="";
 const char *parent="/private/var/db", *directory="/private/var/db/com.apple.xpc.launchd";
 struct mkdir_args md={.path=scratch,.mode=0755};
'''
suffix = r'''
done: (void)failed_step; return error;
}
int main(void) {
 calls=0;parent_result=0;child_result=0;assert(exercise()==0 && calls==2);
 calls=0;parent_result=EEXIST;child_result=EEXIST;assert(exercise()==EEXIST && calls==2);
 calls=0;parent_result=ENOENT;child_result=0;assert(exercise()==ENOENT && calls==1);
 calls=0;parent_result=0;child_result=ENOENT;assert(exercise()==ENOENT && calls==2);
 calls=0;copy_fail=1;assert(exercise()==14 && calls==0);
}
'''
with tempfile.TemporaryDirectory() as d:
    src=Path(d)/'test.c'; exe=Path(d)/'test'; src.write_text(prefix+body+suffix)
    subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(src),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
