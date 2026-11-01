#!/usr/bin/env python3
"""Continuous reviewed USERDATA write followed by full readback; requires explicit --write."""
import argparse
import hashlib
import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

EXPECTED = 'fd43ee7035ce185ce4215ac93fdc006fd784a54b3b7442e21457c226cbe03093'
IMAGE_BYTES = 9382658048
TARGET = '/dev/block/sda36'
ROOT = Path(__file__).resolve().parents[1]


def stream_hash(source):
    h = hashlib.sha256(); count = 0
    while chunk := source.read(8*1024*1024):
        h.update(chunk); count += len(chunk)
    return h.hexdigest(), count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--write', action='store_true', help='Execute already authorized exact-image overwrite')
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Choose a new receipt directory')
    if not args.write:
        raise SystemExit('Plan only: use --write only for the already authorized exact image')
    args.output.mkdir(parents=True)
    with args.image.open('rb') as source:
        digest, size = stream_hash(source)
    if digest != EXPECTED or size != IMAGE_BYTES:
        raise ValueError('Source differs from reviewed complete root image')
    # Runtime read-only gate immediately before opening the target for writing.
    subprocess.run([sys.executable, str(ROOT/'scripts/check-recovery-storage.py'),
                    '--serial', args.serial, '--output', str(args.output/'readiness.json')], check=True)
    receipt = dict(scope='Authorized exact-image USERDATA overwrite and full readback',
                   started_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   source_sha256=digest, image_bytes=size, target=TARGET, partition='USERDATA',
                   userdata_written=False, boot_written=False, recovery_written=False,
                   write_exit_code=None, read_exit_code=None, readback_sha256=None, verified=False)
    report = args.output/'receipt.json'
    report.write_text(json.dumps(receipt,indent=2)+'\n')
    command = ['adb','-s',args.serial,'shell','-T',f'dd of={TARGET} bs=1048576 && sync']
    receipt['write_command'] = ['adb','-s','<selected-device>','shell','-T',command[-1]]
    with (args.output/'write.log').open('wb') as log, args.image.open('rb') as source:
        process = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT)
        receipt['userdata_written'] = True
        report.write_text(json.dumps(receipt,indent=2)+'\n')
        sent = 0; last = time.monotonic()
        try:
            while chunk := source.read(1048576):
                process.stdin.write(chunk); sent += len(chunk)
                if time.monotonic()-last>=15:
                    print(f'Writing {sent}/{IMAGE_BYTES} bytes',flush=True);last=time.monotonic()
            process.stdin.close()
            code = process.wait(timeout=180)
        except BaseException:
            process.terminate()
            process.wait(timeout=20)
            receipt.update(write_interrupted=True,bytes_sent=sent)
            report.write_text(json.dumps(receipt,indent=2)+'\n')
            raise
    receipt.update(write_exit_code=code,bytes_sent=sent)
    report.write_text(json.dumps(receipt,indent=2)+'\n')
    if code or sent!=IMAGE_BYTES:
        raise RuntimeError('Write did not complete; do not retry automatically')
    subprocess.run(['adb','-s',args.serial,'shell','-T',f'blockdev --flushbufs {TARGET}'], check=True, timeout=60)
    receipt['readback_cache_method']='sync then successful BLKFLSBUF on unmounted target; direct flag unsupported by this recovery dd'
    print('Write, sync and block cache flush completed; reading entire image back',flush=True)
    read_command=['adb','-s',args.serial,'exec-out',f'dd if={TARGET} bs=1048576 iflag=count_bytes count={IMAGE_BYTES} 2>/dev/null']
    with (args.output/'read.log').open('wb') as log:
        process=subprocess.Popen(read_command,stdout=subprocess.PIPE,stderr=log)
        h=hashlib.sha256();count=0;last=time.monotonic()
        while chunk:=process.stdout.read(1048576):
            h.update(chunk);count+=len(chunk)
            if count>IMAGE_BYTES:
                process.terminate();raise RuntimeError('Read exceeded intended image length')
            if time.monotonic()-last>=15:
                print(f'Verifying {count}/{IMAGE_BYTES} bytes',flush=True);last=time.monotonic()
        code=process.wait(timeout=60)
    receipt.update(finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),read_exit_code=code,readback_bytes=count,readback_sha256=h.hexdigest(),
                   verified=code==0 and count==IMAGE_BYTES and h.hexdigest()==EXPECTED)
    report.write_text(json.dumps(receipt,indent=2)+'\n')
    if not receipt['verified']:
        raise RuntimeError('Full readback mismatch; do not publish or mount root')
    print('PASS: complete USERDATA image readback matches exact source SHA256',flush=True)


if __name__=='__main__':
    main()
