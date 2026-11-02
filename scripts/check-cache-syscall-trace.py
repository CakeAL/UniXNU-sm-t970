#!/usr/bin/env python3
"""Compile the actual bounded initproc trace helpers and check filtering/wraparound."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text()
    helper = source.split('/* T970_CACHE_TRACE_BEGIN', 1)[1]
    helper = '/* T970_CACHE_TRACE_BEGIN' + helper.split('/* T970_CACHE_TRACE_END */', 1)[0]
    assert 'copyin(' not in helper and 'copyinstr(' not in helper
    harness = r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef struct proc { int pid; } *proc_t;
typedef struct uthread { uint64_t uu_arg[8]; int uu_rval[2]; } *uthread_t;
static int proc_getpid(proc_t p) { return p->pid; }
#define os_atomic_inc_orig(pointer, order) ((*(pointer))++)
#define SYS_open 5
#define SYS_open_nocancel 398
#define SYS_openat 463
#define SYS_openat_nocancel 464
#define SYS_fcntl 92
#define SYS_fcntl_nocancel 406
#define SYS_shared_region_check_np 294
#define SYS_shared_region_map_and_slide_2_np 536
'''
    cases = r'''
int main(void)
{
    struct proc init = {1}, other = {2};
    struct uthread ut = { .uu_arg = {7, 92}, .uu_rval = {3, 0} };
    native_t970_cache_path_note(NULL, "ignored");
    native_t970_cache_syscall_note(NULL, SYS_open, 0, &ut);
    native_t970_cache_path_note(&other, "ignored");
    native_t970_cache_syscall_note(&other, SYS_open, 0, &ut);
    native_t970_cache_syscall_note(&init, 999, 0, &ut);
    assert(native_t970_cache_count == 0 && !native_t970_cache_paths[0]);
    native_t970_cache_path_note(&init, "dyld_shared_cache_arm64");
    native_t970_cache_syscall_note(&init, SYS_fcntl, 85, &ut);
    assert(strstr(native_t970_cache_trace_text(), "sc92 e85 r3 a7 c92 dyld_shared_cache_arm64"));
    char longpath[300]; memset(longpath, 'x', sizeof(longpath));
    strcpy(longpath + 260, "/dyld_shared_cache_arm64");
    native_t970_cache_path_note(&init, longpath);
    assert(strlen(native_t970_cache_paths) == 63);
    assert(strstr(native_t970_cache_paths, "/dyld_shared_cache_arm64"));
    for (int i = 0; i < 50; ++i) {
        ut.uu_rval[0] = i;
        native_t970_cache_syscall_note(&init, SYS_openat, i, &ut);
    }
    const char *text = native_t970_cache_trace_text();
    assert(strstr(text, "syscalls=51"));
    assert(strstr(text, "sc463 e49 r31 a7 c0"));
    assert(!strstr(text, "sc463 e37 "));
    unsigned lines = 0;
    for (const char *p = text; *p; ++p) if (*p == '\n') ++lines;
    assert(lines == 12 && strlen(text) < 1664);
    native_t970_cache_paths[0] = '\0';
    native_t970_cache_syscall_note(&init, SYS_shared_region_map_and_slide_2_np, 22, &ut);
    assert(strstr(native_t970_cache_trace_text(), "(no path note)"));
    puts("PASS: PID filtering, null process, numeric errors, long path, ring wrap, output bound");
}
'''
    with tempfile.TemporaryDirectory(prefix='t970-cache-trace-') as directory:
        path = Path(directory)
        (path / 'check.c').write_text(harness + helper + cases)
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        str(path / 'check.c'), '-o', str(path / 'check')], check=True)
        subprocess.run([str(path / 'check')], check=True)


if __name__ == '__main__':
    main()
