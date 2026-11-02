#!/usr/bin/env python3
"""Check the actual first-EACCES signature diagnostic helper on the host."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    text = args.source.read_text()
    helper = '/* T970_CS_STAGE_BEGIN' + text.split('/* T970_CS_STAGE_BEGIN', 1)[1].split('/* T970_CS_STAGE_END */', 1)[0]
    harness = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <errno.h>
static int pid;
static int proc_selfpid(void) { return pid; }
'''
    cases = r'''
int main(void)
{
    unsigned char hash[20];
    for (unsigned i = 0; i < 20; ++i) hash[i] = i;
    pid = 2; native_t970_cs_note(12, EACCES, 0, hash);
    assert(!native_t970_cs_failure[0]);
    pid = 1; native_t970_cs_note(12, 0, 0, hash);
    native_t970_cs_note(17, 85, 0, hash);
    assert(!native_t970_cs_failure[0]);
    native_t970_cs_note(171, EACCES, 0x100000, hash);
    assert(strstr(native_t970_cs_failure_text(), "stage=171 off=100000"));
    assert(strstr(native_t970_cs_failure_text(), "000102030405060708090a0b0c0d0e0f10111213"));
    native_t970_cs_note(2, EACCES, 0, NULL);
    assert(strstr(native_t970_cs_failure_text(), "stage=171"));
    native_t970_cs_failure[0] = 0;
    native_t970_cs_note(1, EACCES, 0x12000, NULL);
    assert(strstr(native_t970_cs_failure_text(), "cd=unavailable"));
    assert(strlen(native_t970_cs_failure_text()) < sizeof(native_t970_cs_failure));
    puts("PASS: PID/error filtering, first-failure retention, offset/hash encoding, null hash");
}
'''
    with tempfile.TemporaryDirectory(prefix='t970-csig-stage-') as directory:
        path = Path(directory)
        (path / 'check.c').write_text(harness + helper + cases)
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        str(path / 'check.c'), '-o', str(path / 'check')], check=True)
        subprocess.run([str(path / 'check')], check=True)


if __name__ == '__main__':
    main()
