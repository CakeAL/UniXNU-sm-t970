#!/usr/bin/env python3
"""Package the exact root image for Odin USERDATA. Host-only; never flashes."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'fd43ee7035ce185ce4215ac93fdc006fd784a54b3b7442e21457c226cbe03093'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := source.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--compressed', type=Path, required=True, help='lz4 -l -1 source.img userdata.img.lz4')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or not args.output.name.endswith('.tar.md5'):
        raise ValueError('Choose a new .tar.md5 output')
    if subprocess.run(['git', '-C', str(ROOT), 'check-ignore', str(args.output.resolve())], capture_output=True).returncode:
        raise ValueError('Generated image must be Git-ignored')
    if args.image.stat().st_size != 9382658048 or digest(args.image) != EXPECTED:
        raise ValueError('Source image differs from the reviewed exact root image')
    with args.compressed.open('rb') as source:
        if source.read(4) != bytes.fromhex('02214c18'):
            raise ValueError('Require LZ4 legacy frame')
    if args.compressed.stat().st_size > 0o77777777777:
        raise ValueError('Compressed file exceeds standard ustar size field')
    process = subprocess.Popen(['lz4', '-q', '-d', '-c', str(args.compressed)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    h = hashlib.sha256(); count = 0
    while chunk := process.stdout.read(8 * 1024 * 1024):
        h.update(chunk); count += len(chunk)
    error = process.stderr.read()
    if process.wait() or count != args.image.stat().st_size or h.hexdigest() != EXPECTED:
        raise ValueError('Compressed image round-trip failed: ' + error.decode(errors='replace'))
    print('PASS: full LZ4 decode matches exact 9,382,658,048-byte source image', flush=True)
    compressed_sha = digest(args.compressed)

    class Writer:
        def __init__(self, stream):
            self.stream = stream; self.md5 = hashlib.md5(); self.sha = hashlib.sha256()
        def write(self, data):
            self.md5.update(data); self.sha.update(data)
            return self.stream.write(data)
        def flush(self):
            self.stream.flush()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as output:
        writer = Writer(output)
        with tarfile.open(fileobj=writer, mode='w|', format=tarfile.USTAR_FORMAT) as archive:
            entry = tarfile.TarInfo('userdata.img.lz4')
            entry.size = args.compressed.stat().st_size; entry.mode = 0o644; entry.mtime = 0
            with args.compressed.open('rb') as source:
                archive.addfile(entry, source)
        tar_md5 = writer.md5.hexdigest()
        footer = (tar_md5 + '  ' + args.output.name[:-4] + '\n').encode()
        writer.write(footer)
        output_sha = writer.sha.hexdigest()
    # Independently parse the final package and verify its sole member, including
    # byte-for-byte compressed content. No GNU/PAX extensions or other partitions.
    with tarfile.open(args.output, 'r:') as archive:
        members = archive.getmembers()
        if len(members) != 1 or members[0].name != 'userdata.img.lz4':
            raise ValueError('Unexpected Odin package member')
        h = hashlib.sha256()
        with archive.extractfile(members[0]) as source:
            while chunk := source.read(8 * 1024 * 1024):
                h.update(chunk)
        if h.hexdigest() != compressed_sha:
            raise ValueError('Tar member differs from verified LZ4')
    report = dict(scope='Host package verification only; Odin USB/large-file support and device write/readback pending',
        source_image_sha256=EXPECTED, source_bytes=count, compression='LZ4 legacy',
        compressed_bytes=args.compressed.stat().st_size, compressed_sha256=compressed_sha,
        package_sha256=output_sha, package_bytes=args.output.stat().st_size, tar_content_md5=tar_md5,
        tar_format='ustar', members=['userdata.img.lz4'], odin_slot='USERDATA', target_partition='userdata',
        full_decompression_verified=True, independent_tar_member_verified=True,
        device_written=False, odin_compatibility_device_verified=False)
    args.output.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
