#!/usr/bin/env python3
"""Capture the bootloader/handoff FDT and record an identity-free summary.

The blob is the firmware input for `unixnu bootimg --dtb`; it is NOT the board
DTS that produces the XNU ADT. Its /chosen node carries boot arguments, a KASLR
seed and initrd addresses, so the blob stays in ignored local storage and the
JSON report records only hashes, structure and non-identity values.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE / 'scripts'))
import fdt  # noqa: E402
from adb_readonly import read  # noqa: E402


def prop(name):
    result = subprocess.run(['adb', '-d', 'shell', 'getprop', name],
                            capture_output=True, text=True, check=True)
    return result.stdout.strip()


def tracked(path):
    result = subprocess.run(['git', '-C', str(DEVICE), 'ls-files', '--error-unmatch', str(path)],
                            capture_output=True)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEVICE / 'out/firmware-inputs/firmware.dtb')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--compare', type=Path, help='earlier capture to compare against')
    args = parser.parse_args()
    output = args.output.resolve()
    if tracked(output):
        parser.error('refusing to write an identity-bearing blob to a tracked path: ' + str(output))
    blob = read('cat /sys/firmware/fdt')
    header, nodes = fdt.parse(blob)
    report_path = (args.report or output.with_suffix('.json')).resolve()
    chosen = nodes.get('/chosen', {})
    withheld = sorted(k for k in chosen if k in ('bootargs', 'kaslr-seed',
                                                'linux,initrd-start', 'linux,initrd-end'))
    memory = []
    if '/memory' in nodes and 'reg' in nodes['/memory']:
        memory = [f'0x{address:x}+0x{size:x}'
                  for address, size in fdt.reg_ranges(nodes['/memory']['reg'])]
    reserved = [path for path in nodes if path.startswith('/reserved-memory/')]
    reserved_bytes = 0
    for path in reserved:
        reg = nodes[path].get('reg')
        if reg:
            reserved_bytes += sum(size for _, size in fdt.reg_ranges(reg))
    structure = json.dumps(sorted((path, sorted(props)) for path, props in nodes.items()),
                           separators=(',', ':'))
    report = {
        'source': '/sys/firmware/fdt on the connected device (read-only through su)',
        'device': {name: prop(name) for name in
                   ('ro.product.model', 'ro.product.device', 'ro.bootloader',
                    'ro.build.id', 'ro.build.version.release')},
        'size_bytes': len(blob),
        'sha256': hashlib.sha256(blob).hexdigest(),
        'fdt_version': header['version'],
        'node_count': len(nodes),
        'property_count': sum(len(props) for props in nodes.values()),
        'model': fdt.strings(nodes['/']['model'])[0] if 'model' in nodes.get('/', {}) else None,
        'compatible': fdt.strings(nodes['/']['compatible']) if 'compatible' in nodes.get('/', {}) else [],
        'memory': memory,
        'reserved_memory_entries': len(reserved),
        'reserved_memory_bytes': reserved_bytes,
        'chosen_property_names': sorted(chosen),
        'identity_properties_withheld': withheld,
        'structural_sha256': hashlib.sha256(structure.encode()).hexdigest(),
        'note': 'Full blob is local-only because /chosen carries identity and boot state; '
                'withheld values never enter this report.',
    }
    if args.compare and args.compare.is_file():
        previous = hashlib.sha256(args.compare.read_bytes()).hexdigest()
        report['compare'] = {'path': str(args.compare), 'sha256': previous,
                             'identical': previous == report['sha256']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(blob)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    print(f'captured {len(blob)} bytes sha256 {report["sha256"]}')
    print(f'report {report_path}')
    if 'compare' in report:
        print('identical to earlier capture:', report['compare']['identical'])


if __name__ == '__main__':
    main()
