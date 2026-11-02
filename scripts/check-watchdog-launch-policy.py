#!/usr/bin/env python3
"""Fault-inject the actual prepared policy helper; no APFS or device execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
source = args.source.read_text()
start = source.index('static const char native_t970_watchdog_override[]')
function_start = source.index('static int\nnative_t970_watchdog_policy_prepare(', start)
brace = source.index('{', function_start)
depth = 1
end = brace + 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
end += 1
actual = source[start:end]
literal = re.search(r'native_t970_watchdog_override\[\] = (".*");', actual).group(1)
policy = json.loads(literal)
expected = Path(__file__).resolve().parents[1] / 'evidence/storage/watchdogd/disabled.plist'
assert policy.encode() == expected.read_bytes()
prelude = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/types.h>
#define XNU_NATIVE_RAM_BLOCK 1
#ifndef FWRITE
#define FWRITE 2
#endif
#define VNODE_LOOKUP_NOFOLLOW 1
#define UIO_WRITE 1
#define UIO_SYSSPACE 1
#define IO_UNIT 1
#define MNT_WAIT 1
#define VREG 1
#define VDIR 2
#define NULLVP NULL
typedef void *proc_t;
#ifndef __APPLE__
typedef uintptr_t user_addr_t;
#endif
typedef void *vfs_context_t;
struct node { int type; };
typedef struct node *vnode_t;
struct vnode_attr { unsigned va_uid,va_gid,va_mode; };
#define VATTR_INIT(v) memset(v,0,sizeof(*(v)))
#define VATTR_SET(v,f,x) ((v)->f=(x))
struct mkdir_args { user_addr_t path; unsigned mode; };
int native_owner_data_stage=4,native_owner_data_readonly=0;
static int mode,uid,scenario,events,fail_at,open_files,policy_closed,marker_opened,writes,refs;
static unsigned char scratch[4096];
static struct node dir={VDIR},file={VREG};
static const char *base="/private/var/db/com.apple.xpc.launchd";
static int event(void){return ++events==fail_at?EIO:0;}
unsigned native_ufs_store_mode(void){return (unsigned)mode;}
static vfs_context_t vfs_context_current(void){return (void*)1;}
static void *vfs_context_ucred(vfs_context_t c){assert(c==(void*)1);return c;}
static proc_t vfs_context_proc(vfs_context_t c){return c;}
static unsigned kauth_cred_getuid(void *c){(void)c;return (unsigned)uid;}
static int vnode_lookup(const char *p,int flags,vnode_t *v,vfs_context_t c){
 assert(flags==VNODE_LOOKUP_NOFOLLOW&&c==(void*)1);int e=event();if(e)return e;
 if(!strcmp(p,base)){*v=&dir;++refs;return 0;}
 assert(!strcmp(p,"/private/var/db/com.apple.xpc.launchd/disabled.plist")||
        !strcmp(p,"/private/var/db/com.apple.xpc.launchd/disabled.migrated"));
 if((scenario==1&&strstr(p,"disabled.plist"))||(scenario==2&&strstr(p,"disabled.migrated"))){*v=&file;++refs;return 0;}
 return ENOENT;
}
static void vnode_put(vnode_t v){assert(v);assert(refs>0);--refs;}
static int vnode_vtype(vnode_t v){return v->type;}
static int copyout(const void *p,user_addr_t to,size_t n){
 assert(to==(uintptr_t)scratch+0xa00&&n<sizeof(scratch)-0xa00);int e=event();if(!e)memcpy((void*)to,p,n);return e;
}
static int mkdir(proc_t p,struct mkdir_args *a,int32_t *r){
 (void)p;(void)r;assert(a->mode==0755&&!strcmp((char*)a->path,base));int e=event();return e?e:scenario==3?EEXIST:0;
}
static int vnode_open(const char *p,int flags,int perms,int arg,vnode_t *v,vfs_context_t c){
 assert(flags==(O_CREAT|O_EXCL|FWRITE|O_NOFOLLOW)&&perms==0644&&!arg&&c==(void*)1);
 int marker=strstr(p,"disabled.migrated")!=NULL;
 assert(marker||strstr(p,"disabled.plist"));if(marker){assert(policy_closed);++marker_opened;}
 int e=event();if(e)return e;*v=&file;++open_files;return 0;
}
static int vn_rdwr(int op,vnode_t v,caddr_t data,int size,int offset,int space,int flags,void *cred,int *resid,proc_t p){
 assert(op==UIO_WRITE&&v==&file&&!offset&&space==UIO_SYSSPACE&&flags==IO_UNIT&&cred==p);
 assert(size>0&&strstr(data,"<key>com.apple.watchdogd</key>"));++writes;
 int e=event();*resid=scenario==4?1:0;return e;
}
static int vnode_setattr(vnode_t v,struct vnode_attr *a,vfs_context_t c){
 (void)c;assert(!a->va_uid&&!a->va_gid&&a->va_mode==(v==&dir?0755:0644));return event();
}
static int VNOP_FSYNC(vnode_t v,int flags,vfs_context_t c){assert(v==&file&&flags==MNT_WAIT&&c==(void*)1);return event();}
static int vnode_close(vnode_t v,int flags,vfs_context_t c){
 assert(v==&file&&flags==FWRITE&&c==(void*)1&&open_files==1);--open_files;
 int e=event();if(!e&&!marker_opened)policy_closed=1;return e;
}
'''
main = r'''
static void reset(void){
 events=fail_at=open_files=policy_closed=marker_opened=writes=refs=mode=uid=scenario=0;
 dir.type=VDIR;file.type=VREG;native_owner_data_stage=4;native_owner_data_readonly=0;native_t970_watchdog_policy_stage=0;
}
int main(void){
 reset();assert(native_t970_watchdog_policy_prepare(NULL,(uintptr_t)scratch)==0);
 assert(native_t970_watchdog_policy_stage==4&&marker_opened==1&&writes==1&&!open_files&&!refs);
 int total=events;
 for(int i=1;i<=total;++i){reset();fail_at=i;assert(native_t970_watchdog_policy_prepare(NULL,(uintptr_t)scratch)==EIO);assert(!open_files&&!refs&&native_t970_watchdog_policy_stage!=4);}
 for(int i=0;i<4;++i){reset();if(i==0)mode=2;if(i==1)uid=501;if(i==2)native_owner_data_stage=3;if(i==3)native_owner_data_readonly=1;
  assert(native_t970_watchdog_policy_prepare(NULL,(uintptr_t)scratch)==EPERM&&!events);}
 for(int i=1;i<=2;++i){reset();scenario=i;assert(native_t970_watchdog_policy_prepare(NULL,(uintptr_t)scratch)==EEXIST&&!writes&&!open_files&&!refs);}
 reset();scenario=3;assert(native_t970_watchdog_policy_prepare(NULL,(uintptr_t)scratch)==0);
 reset();scenario=4;assert(native_t970_watchdog_policy_prepare(NULL,(uintptr_t)scratch)==EIO&&!marker_opened&&!open_files&&!refs);
 reset();dir.type=VREG;assert(native_t970_watchdog_policy_prepare(NULL,(uintptr_t)scratch)==ENOTDIR&&!writes&&!refs);
 reset();file.type=VDIR;assert(native_t970_watchdog_policy_prepare(NULL,(uintptr_t)scratch)==EINVAL&&!writes&&!open_files&&!refs);
 printf("PASS: actual policy helper; %d API failure points; persistence/UID/mount guards; existing files; partial write; vnode cleanup\n",total);
 return 0;
}
'''
args.output.mkdir(parents=True, exist_ok=False)
test = args.output / 'test.c'
test.write_text(prelude + actual + main)
subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-g', '-O1',
                '-fsanitize=address,undefined', str(test), '-o', str(args.output / 'test')], check=True)
result = subprocess.run([str(args.output / 'test')], check=True, capture_output=True, text=True)
report = dict(helper_sha256=hashlib.sha256(actual.encode()).hexdigest(), policy_sha256=hashlib.sha256(policy.encode()).hexdigest(),
              passed=True, actual_source=True, os_apis_mocked=True, actual_apfs=False, hardware_tested=False, result=result.stdout.strip())
(args.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(result.stdout, end='')
