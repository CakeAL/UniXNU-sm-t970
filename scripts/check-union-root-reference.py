#!/usr/bin/env python3
"""Compile the selected XNU's actual checkdirs functions with host vnode counters."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text()
    start = source.index('static int\ncheckdirs_callback(')
    end = source.index('#define ROLE_ACCOUNT_UNMOUNT_ENTITLEMENT', start)
    functions = source[start:end]
    harness = r'''
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
typedef struct vnode { int v_usecount; void *v_mountedhere; } *vnode_t;
struct filedesc { vnode_t fd_cdir, fd_rdir; };
typedef struct proc { struct filedesc p_fd; } *proc_t;
struct cdirargs { vnode_t olddp, newdp; };
typedef void *vfs_context_t;
static struct proc processes[3];
static proc_t kernproc = &processes[0];
static vnode_t rootvnode, target;
static int rootvnode_rw_lock;
#define PROC_RETURNED 0
#define PROC_ALLPROCLIST 1
#define PROC_NOWAITTRANS 2
#define DIAGNOSTIC 0
static int vnode_ref(vnode_t vp) { ++vp->v_usecount; return 0; }
static void vnode_rele(vnode_t vp) { --vp->v_usecount; }
static void vnode_put(vnode_t vp) { (void)vp; }
static void proc_fdlock(proc_t p) { (void)p; }
static void proc_fdunlock(proc_t p) { (void)p; }
static void proc_dirs_lock_exclusive(proc_t p) { (void)p; }
static void proc_dirs_unlock_exclusive(proc_t p) { (void)p; }
static void lck_rw_lock_exclusive(int *lock) { (void)lock; }
static void lck_rw_unlock_exclusive(int *lock) { (void)lock; }
static int VFS_ROOT(void *mount, vnode_t *vp, vfs_context_t ctx)
{ (void)mount; (void)ctx; *vp = target; return 0; }
static void proc_iterate(int flags, int (*fn)(proc_t, void *), void *arg,
                         void *filter, void *filter_arg)
{
    (void)flags; (void)filter; (void)filter_arg;
    for (unsigned i = 0; i < 3; ++i) fn(&processes[i], arg);
}
'''
    cases = r'''
int main(void)
{
    /* kernproc's cwd aliases rootvnode's ref, while other cwd/rdir refs are owned. */
    for (int child_cwd = 0; child_cwd < 2; ++child_cwd)
    for (int child_rdir = 0; child_rdir < 2; ++child_rdir) {
        struct vnode old = { .v_usecount = 2 + child_cwd + child_rdir };
        struct vnode next = {0}, unrelated = { .v_usecount = 1 };
        rootvnode = &old; target = &next;
        processes[0].p_fd = (struct filedesc){ .fd_cdir = &old };
        processes[1].p_fd = (struct filedesc){ .fd_cdir = child_cwd ? &old : NULL,
                                               .fd_rdir = child_rdir ? &old : NULL };
        /* An unrelated process owns the remaining independent old reference. */
        processes[2].p_fd = (struct filedesc){ .fd_cdir = &old, .fd_rdir = &unrelated };
        assert(checkdirs(&old, NULL) == 0);
        assert(old.v_usecount == 0);
        assert(next.v_usecount == 2 + child_cwd + child_rdir);
        assert(rootvnode == &next && kernproc->p_fd.fd_cdir == &next);
        assert(processes[2].p_fd.fd_rdir == &unrelated && unrelated.v_usecount == 1);
    }
    /* A non-root mount must still transfer kernproc's separately owned cwd. */
    {
        struct vnode root = { .v_usecount = 1 }, old = { .v_usecount = 2 }, next = {0};
        rootvnode = &root; target = &next;
        processes[0].p_fd = (struct filedesc){ .fd_cdir = &old };
        processes[1].p_fd = (struct filedesc){ .fd_cdir = &old };
        processes[2].p_fd = (struct filedesc){0};
        assert(checkdirs(&old, NULL) == 0);
        assert(old.v_usecount == 0 && next.v_usecount == 2);
        assert(rootvnode == &root && root.v_usecount == 1);
    }
    puts("PASS: five actual-XNU checkdirs reference-accounting cases");
}
'''
    with tempfile.TemporaryDirectory(prefix='t970-union-refs-') as directory:
        path = Path(directory)
        (path / 'check.c').write_text(harness + functions + cases)
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        str(path / 'check.c'), '-o', str(path / 'check')], check=True)
        subprocess.run([str(path / 'check')], check=True)


if __name__ == '__main__':
    main()
