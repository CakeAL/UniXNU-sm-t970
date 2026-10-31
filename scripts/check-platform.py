#!/usr/bin/env python3
"""Check SM-T970 platform bindings against the captured hardware and generated ADT.

Requires Python 3.11+, dtc and the resolved UniXNU/SoC/component sources.
This performs host checks only and never invokes ADB or creates a boot image.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def decode_adt(blob):
    result = {}

    def read(offset, parent, root=False):
        count, children = struct.unpack_from('<II', blob, offset)
        offset += 8
        properties = {}
        for _ in range(count):
            key, size = struct.unpack_from('<32sI', blob, offset)
            offset += 36
            key = key.split(b'\0', 1)[0].decode()
            require(key not in properties, 'Duplicate ADT property: ' + key)
            require(offset + size <= len(blob), 'Truncated ADT property: ' + key)
            properties[key] = blob[offset:offset + size]
            offset += (size + 3) & ~3
        name = properties['name'].rstrip(b'\0').decode()
        path = '' if root else parent + '/' + name
        result[path or '/'] = properties
        for _ in range(children):
            offset = read(offset, path)
        return offset

    require(read(0, '', root=True) == len(blob), 'ADT trailing bytes')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    device = Path(__file__).resolve().parents[1]
    parser.add_argument('--unixnu', type=Path, default=device.parent / 'UniXNU')
    parser.add_argument('--output', type=Path, default=device / 'out/platform-check')
    options = parser.parse_args()
    framework = options.unixnu.resolve()
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(framework / 'scripts'))
    from unixnu.cli import parser as cli_parser
    from unixnu.config import Context
    from unixnu import devicetree as dt, feeds, kernel, patches

    ctx = Context(cli_parser().parse_args(['status', '-D', str(device), '--json']))
    modules = feeds.resolve(ctx)
    selected = {spec['id']: spec for spec in ctx.component_specs}
    require(set(selected) == {'ArmDTPlatform', 'ArmCpu', 'SoftwareAES', 'XnuPrelink', 'DarwinBoot'},
            'Unexpected bootstrap component selection')
    versions = {}
    for name, spec in selected.items():
        module = modules[(spec['kind'], name)]
        require(module.path is not None, name + ': source unavailable; run unixnu fetch')
        revision = git(module.path, 'rev-parse', 'HEAD')
        require(revision == spec['revision'], name + ': checkout differs from selected source pin')
        require(not git(module.path, 'status', '--porcelain', '--', '.'), name + ': source is modified')
        versions[name] = revision
    require(git(ctx.soc.path, 'rev-parse', 'HEAD') == ctx.soc.source['commit'], 'SoC source pin mismatch')
    require(not git(ctx.soc.path, 'status', '--porcelain'), 'SoC source is modified')
    selected_patches = patches.plan(ctx, modules)
    archive_plan = kernel.archive_plan(ctx)
    require(ctx.config.get('XNU_ARMCPU') and ctx.config.get('XNU_ARM_DT_PLATFORM'),
            'Select the defconfig before checking platform bindings')
    require(not ctx.config.get('XNU_NATIVE_UFS') and not ctx.config.get('XNU_NATIVE_ADRENO'),
            'Board-dependent storage/GPU paths must remain disabled')

    hardware = dt.compile_hardware(ctx)
    tree = dt.read_fdt(hardware.read_bytes())
    captured = subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb',
                              str(device / 'evidence/adb-2026-11-01/live-device-tree.dts')],
                             capture_output=True, check=True).stdout
    live = dt.read_fdt(captured)
    cpus = next(n for n in tree.children if n.name == 'cpus')
    live_cpus = next(n for n in live.children if n.name == 'cpus')
    enabled = [n for n in cpus.children if n.enabled()]
    require(len(enabled) == 1 and dt.registers(enabled[0])[0][0] == 0, 'Bootstrap must enable only CPU0')
    measured = {n.name: n for n in live_cpus.children if 'reg' in n.properties}
    require(all(dt.registers(n) == dt.registers(measured[n.name]) for n in cpus.children),
            'CPU affinities differ from captured hardware')
    timer = next(n for n in live.walk() if n.strings('compatible') == ['arm,armv8-timer'])
    require(cpus.scalar('timebase-frequency') == timer.scalar('clock-frequency') == 19200000,
            'CPU timebase differs from captured architectural timer')
    gic = next(n for n in tree.walk() if n.strings('unixnu,adt-name') == ['intc'])
    measured_gic = next(n for n in live.walk() if n.strings('compatible') == ['arm,gic-v3'])
    require(dt.registers(gic) == dt.registers(measured_gic), 'GIC register range mismatch')
    require(gic.cells('redistributor-stride') == measured_gic.cells('redistributor-stride'), 'GIC stride mismatch')
    memory = next(n for n in tree.children if n.strings('device_type') == ['memory'])
    live_memory = next(n for n in live.children if n.strings('device_type') == ['memory'])
    span = dt.registers(memory)
    require(len(span) == 1 and span[0] in dt.registers(live_memory), 'Handoff bank is not a measured contiguous bank')
    reserved = next(n for n in tree.children if n.name == 'reserved-memory')
    live_reserved = next(n for n in live.children if n.name == 'reserved-memory')
    expected = {n.name: n.properties['reg'] for n in live_reserved.children if 'reg' in n.properties}
    actual = {n.name: n.properties['reg'] for n in reserved.children if 'reg' in n.properties}
    require(actual == expected, 'Static firmware reservation changed or was lost')
    for node in reserved.children:
        for base, size in dt.registers(node):
            require(base + size <= span[0][0] or span[0][0] + span[0][1] <= base,
                    'Candidate handoff bank overlaps a static firmware reservation')
    exported = [n for n in tree.walk() if n.enabled() and 'unixnu,adt-name' in n.properties]
    require(exported == [gic], 'Unexpected exported peripheral in the minimal platform tree')

    # Deliberately artificial identity for an offline conversion fixture only.
    adt = dt.generate(hardware, ctx.board, unique_chip_id='1', data=False, trust=False)
    (output / 'host-check.adt').write_bytes(adt)
    decoded = decode_adt(adt)
    for path in ('/chosen', '/cpus', '/arm-io', '/defaults', '/options'):
        require(path in decoded, 'Platform expert node missing: ' + path)
    chosen = decoded['/chosen']
    require(struct.unpack('<QQ', chosen['dram-base'] + chosen['dram-size']) == span[0], 'ADT DRAM encoding mismatch')
    require(len(chosen['nvram-proxy-data']) == 8192, 'NVRAM proxy missing')
    require(decoded['/cpus/cpu0']['reg'] == struct.pack('<I', 0), 'ADT boot affinity encoding mismatch')
    require(decoded['/cpus/cpu0']['timebase-frequency'] == struct.pack('<I', 19200000), 'ADT timer byte order mismatch')
    require('/cpus/cpu1' not in decoded, 'Disabled CPU leaked into ADT')
    base = struct.unpack('<QQQ', decoded['/arm-io']['ranges'])[1]
    encoded_ranges = struct.unpack('<QQQQ', decoded['/arm-io/intc']['reg'])
    require([(base + encoded_ranges[i], encoded_ranges[i + 1]) for i in (0, 2)] == dt.registers(gic),
            'GIC ADT address translation mismatch')
    require(decoded['/arm-io/intc']['redistributor-stride'] == struct.pack('<Q', 0x20000), 'ADT GIC stride mismatch')

    tracked_inputs = ['board.toml', 'feeds.toml', 'configs/sm-t970_defconfig', 'dts/sm-t970.dts',
                      'dts/sm-t970-reserved.dtsi', 'scripts/check-platform.py', 'unixnu.lock']
    git(device, 'ls-files', '--error-unmatch', *tracked_inputs)
    require(not git(device, 'diff', '--name-only', 'HEAD', '--', *tracked_inputs),
            'Commit the platform inputs before archiving a verification report')
    report = {'scope': 'Host configuration and DT/ADT checks only; no kernel compilation or device boot',
              'device_source_revision': git(device, 'rev-parse', 'HEAD'),
              'committed_platform_inputs': True,
              'unixnu_revision': git(framework, 'rev-parse', 'HEAD'),
              'soc_revision': git(ctx.soc.path, 'rev-parse', 'HEAD'), 'components': versions,
              'enabled_cpu_affinities': [0], 'timebase_hz': 19200000,
              'candidate_dram_base': hex(span[0][0]), 'candidate_dram_size': hex(span[0][1]),
              'static_reservations': len(actual), 'patch_count': len(selected_patches),
              'patch_order': [p.name for p in selected_patches], 'archive_recipe_count': len(archive_plan),
              'input_sha256': {p: hashlib.sha256((device / p).read_bytes()).hexdigest() for p in tracked_inputs},
              'result': 'PASS', 'boot_enabled': not ctx.example,
              'limits': ['RAM bank is not verified against a T970 UEFI allocation map.',
                         'Host-check ADT uses artificial identity 1 and must not be used to boot.',
                         'No peripheral DMA, XNU driver execution or SMP test is claimed.']}
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: source pins and archive/patch plans resolve; measured CPU/GIC/timer and 30 static reservations match.')
    print('PASS: single-core DT compiles and ADT platform nodes, byte order and register translations match.')
    print('Kernel build and device boot were not performed. Report: ' + str(output / 'result.json'))


if __name__ == '__main__':
    main()
