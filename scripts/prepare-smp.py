#!/usr/bin/env python3
"""Prepare an isolated SMP BOOT from a verified CPU0 runtime-sampler image.

Only CPU enablement/ADT topology and explicit SMP arguments change. No flashing.
"""
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tomllib
import tempfile

DEVICE = Path(__file__).resolve().parents[1]
FRAMEWORK = DEVICE.parent / 'UniXNU'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpus', type=int, choices=(2, 4, 8), required=True)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--base-validation', type=Path, required=True)
    parser.add_argument('--hardware-dtb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--armcpu-source', type=Path, default=FRAMEWORK / 'drivers/ArmCpu')
    args = parser.parse_args()
    require(not args.output.exists(), 'Preserve previous images; output must be new')
    base = args.base.read_bytes()
    validation = json.loads(args.base_validation.read_text())
    require(sha(base) == validation['boot_sha256'] and validation['exact_fd_dtb'] and
            validation['watchdog_policy_requested'] and
            (5 <= validation['runtime_report_target_seconds'] <= 300 or
             (validation.get('continuous_cpu_present') is True and validation['runtime_report_target_seconds'] == 0 and not validation['terminal_diagnostic'])),
            'Require a verified CPU0 policy/runtime-sampler base')
    sys.path.insert(0, str(FRAMEWORK / 'scripts'))
    from unixnu import devicetree as dt
    from unixnu.cli import parser as cli_parser
    from unixnu.config import Context
    ctx = Context(cli_parser().parse_args(['build', 'payload', '-D', str(DEVICE),
                                          '--out', str(DEVICE / 'out/data-bringup')]))
    spec = importlib.util.spec_from_file_location('platform_check', DEVICE / 'scripts/check-platform.py')
    check = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check)
    board_before = (DEVICE / 'board.toml').read_bytes()
    source_tree = ctx.tree / '.cache/xnu-work'
    config = (source_tree / 'pexpert/pexpert/arm64/board_config.h').read_text()
    require('#define MAX_CPUS                       8' in config, 'Kernel must support eight CPUs')
    require('#if HAS_CLUSTER || defined(BCM2837)' in (source_tree / 'osfmk/arm64/start.s').read_text(),
            'Reset entry must preserve Affinity1')
    armcpu = args.armcpu_source.resolve()
    armcpu_revision = subprocess.check_output(['git', '-C', str(armcpu), 'rev-parse', 'HEAD'], text=True).strip()
    reviewed = {'9066b53bbc82e92a98ec44a11dd50fd13eaf1a1b', 'b5f9775777aafe850a4ec8778b03154dfcabbd2b'}
    require(armcpu_revision in reviewed, 'Unreviewed ArmCpu source')
    require(not subprocess.check_output(['git', '-C', str(armcpu), 'status', '--porcelain'], text=True),
            'ArmCpu source must be clean')
    armcpu_text = (armcpu / 'ArmCpu.cpp').read_text()
    compiled_source = ctx.tree / 'drivers/ArmCpu/ArmCpu.cpp'
    require(compiled_source.resolve() == (armcpu / 'ArmCpu.cpp').resolve(), 'Resolved build tree uses another ArmCpu source')
    require('psciCall (hvc, 0xc4000003ULL, affinity & 0xff00ffffffULL, entry, 0)' in armcpu_text,
            'Unexpected PSCI CPU_ON implementation')
    for region, length in [('LowResetVectorBase', '0x10000'), ('ResetHandlerData', '0x1000'), ('const_boot_args', '0x1000')]:
        require(f'cleanToMemory ({region}, {length})' in armcpu_text, 'Missing reset cache cleaning: ' + region)
    expression = re.search(r'uint64_t sgi = (.*?);', armcpu_text[armcpu_text.index('void ArmCpu::signalCPU ('):], re.S).group(1)
    with tempfile.TemporaryDirectory(prefix='t970-sgi-') as temporary:
        c, executable = Path(temporary) / 'sgi.c', Path(temporary) / 'sgi'
        c.write_text('#include <stdint.h>\n#include <assert.h>\nint main(void){for(unsigned i=0;i<8;++i){uint64_t aff=(uint64_t)i<<8;uint64_t sgi='
                     + expression + ';assert(sgi==(((uint64_t)i<<16)|1));}return 0;}\n')
        subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                        str(c), '-o', str(executable)], check=True)
        subprocess.run([str(executable)], check=True)
    args.output.mkdir(parents=True)
    out = args.output
    kernel_bytes = struct.unpack_from('<I', base, 8)[0]
    payload_bytes = struct.unpack_from('<I', base, 16)[0]
    page, version = struct.unpack_from('<II', base, 36)
    require((page, version, len(base)) == (4096, 2, 71303168), 'Unexpected BOOT geometry')
    offset = page + ((kernel_bytes + page - 1) // page) * page
    image = out / 'payload.img'
    image.write_bytes(base[offset:offset + payload_bytes])
    originals = {}
    for name in ('kernel.macho', 'kernel.macho.adt', 'kernel.macho.trustcache', 'scratch-data.img'):
        path = out / name
        subprocess.run(['mcopy', '-i', str(image), '::/EFI/UniXNU/Payloads/' + name, str(path)], check=True)
        originals[name] = path.read_bytes()
    require(sha(originals['kernel.macho']) == validation['payload_kernel_sha256'], 'Wrong source kernel')
    old = check.decode_adt(originals['kernel.macho.adt'])
    require([p for p in old if p.startswith('/cpus/')] == ['/cpus/cpu0'], 'Base must be CPU0 only')
    hardware = dt.read_fdt(args.hardware_dtb.read_bytes())
    cpus = next(n for n in hardware.children if n.name == 'cpus')
    require([dt.registers(n)[0][0] for n in cpus.children] == [i << 8 for i in range(8)],
            'Unexpected board affinities')
    captured = subprocess.check_output(['dtc', '-I', 'dts', '-O', 'dtb',
                                       str(DEVICE / 'evidence/adb-2026-11-01/live-device-tree.dts')], stderr=subprocess.DEVNULL)
    live = dt.read_fdt(captured)
    live_cpus = next(n for n in live.children if n.name == 'cpus')
    require(sorted(dt.registers(n)[0][0] for n in live_cpus.children if 'reg' in n.properties) ==
            [i << 8 for i in range(8)], 'Affinity differs from captured T970')
    require(cpus.scalar('timebase-frequency') == 19200000, 'Unexpected architectural timer rate')
    hardware_path = out / 'hardware.dtb'
    shutil.copyfile(args.hardware_dtb, hardware_path)
    before = {n.name: dict(n.properties) for n in cpus.children}
    for i, n in enumerate(cpus.children):
        subprocess.run(['fdtput', '-t', 's', str(hardware_path), '/cpus/' + n.name, 'status',
                        'okay' if i < args.cpus else 'disabled'], check=True)
    altered = dt.read_fdt(hardware_path.read_bytes())
    altered_cpus = next(n for n in altered.children if n.name == 'cpus')
    for i, n in enumerate(altered_cpus.children):
        expected = dict(before[n.name], status=(b'okay\0' if i < args.cpus else b'disabled\0'))
        require(n.properties == expected, 'CPU properties changed beyond status')
    identity = struct.unpack('<Q', old['/chosen']['unique-chip-id'])[0]
    generated = check.decode_adt(dt.generate(hardware_path, ctx.board, unique_chip_id=hex(identity),
                                           data=True, trust=True))
    new = {}
    for path, props in old.items():
        if path == '/cpus':
            new.update({p: v for p, v in generated.items() if p == '/cpus' or p.startswith('/cpus/')})
            if '/psci' not in old:
                new['/psci'] = generated['/psci']
        elif not path.startswith('/cpus/'):
            new[path] = props

    def encode(nodes, path='/'):
        props = nodes[path]
        children = [p for p in nodes if p != '/' and (p.rsplit('/', 1)[0] or '/') == path]
        return dt.node(props['name'].rstrip(b'\0').decode(),
                       [(k, v) for k, v in props.items() if k != 'name'], [encode(nodes, p) for p in children])

    require(encode(old) == originals['kernel.macho.adt'], 'ADT does not round-trip losslessly')
    adt = encode(new)
    decoded = check.decode_adt(adt)
    require(decoded['/cpus'] == old['/cpus'] and decoded['/cpus/cpu0'] == old['/cpus/cpu0'],
            'Boot CPU or parent properties changed')
    require({p: v for p, v in decoded.items() if not p.startswith('/cpus') and p != '/psci'} ==
            {p: v for p, v in old.items() if not p.startswith('/cpus') and p != '/psci'}, 'Unrelated ADT changed')
    actual_cpus = [p for p in decoded if p.startswith('/cpus/')]
    require(len(actual_cpus) == args.cpus, 'Wrong ADT CPU count')
    for i, p in enumerate(actual_cpus):
        require(decoded[p]['reg'] == struct.pack('<I', i << 8) and
                decoded[p]['state'] == (b'running\0' if i == 0 else b'waiting\0'), 'Wrong CPU affinity/state')
    require(decoded['/psci']['method'] == b'smc\0', 'Expected captured SMC conduit')
    (out / 'kernel.macho.adt').write_bytes(adt)
    config_text = subprocess.check_output(['mtype', '-i', str(image), '::/EFI/UniXNU/unixnu.toml'], text=True)
    conf = tomllib.loads(config_text)
    entry = next(e for e in conf['entry'] if e['id'] == 'xnu')
    old_args = entry['args'].split()
    require(old_args.count('cpus=1') == 1 and not any(a.startswith(('sheng-smp=', 'armcpu-')) for a in old_args),
            'Base has unexpected SMP overrides')
    new_args = [f'cpus={args.cpus}' if a == 'cpus=1' else a for a in old_args]
    new_args += ['sheng-smp=1', 'armcpu-self-ipi=1', 'armcpu-spi-ipi=0']
    updated_config = config_text.replace('args = "' + entry['args'] + '"', 'args = "' + ' '.join(new_args) + '"')
    require(updated_config != config_text, 'Configuration replacement failed')
    (out / 'unixnu.toml').write_text(updated_config)
    for name, destination in [('kernel.macho.adt', 'Payloads/kernel.macho.adt'), ('unixnu.toml', 'unixnu.toml')]:
        subprocess.run(['mcopy', '-o', '-i', str(image), str(out / name), '::/EFI/UniXNU/' + destination], check=True)
    independent = out / 'independent'
    independent.mkdir()
    for name in originals:
        path = independent / name
        subprocess.run(['mcopy', '-i', str(image), '::/EFI/UniXNU/Payloads/' + name, str(path)], check=True)
        require(path.read_bytes() == (adt if name.endswith('.adt') else originals[name]), 'FAT mismatch: ' + name)
    require(subprocess.check_output(['mtype', '-i', str(image), '::/EFI/UniXNU/unixnu.toml'], text=True) == updated_config,
            'Configuration round-trip failed')
    payload = image.read_bytes()
    require(len(payload) == payload_bytes, 'Payload resized')
    result = bytearray(base)
    result[offset:offset + payload_bytes] = payload
    require(result[:offset] == base[:offset] and result[offset + payload_bytes:] == base[offset + payload_bytes:],
            'Header/FD/DTB/tail changed')
    require((DEVICE / 'board.toml').read_bytes() == board_before, 'Board default changed')
    (out / 'boot-partition.img').write_bytes(result)
    report = dict(cpus_requested=args.cpus, boot_sha256=sha(result), base_boot_sha256=sha(base),
                  kernel_sha256=validation['kernel_sha256'], payload_kernel_sha256=validation['payload_kernel_sha256'],
                  adt_sha256=sha(adt), args=' '.join(new_args), unrelated_adt_unchanged=True, psci_method='smc',
                  kernel_trust_seed_unchanged=True, header_fd_dtb_tail_unchanged=True, board_default_unchanged=True,
                  captured_affinities_verified=True, ipi='Standard SGI0; self test on, SPI fallback off',
                  armcpu_revision=armcpu_revision, armcpu_source_sha256=sha(armcpu_text.encode()),
                  actual_sgi_expression_host_cases=8, psci_and_cache_clean_source_verified=True,
                  terminal_runtime_report=validation['terminal_diagnostic'], target_wait_seconds=validation['runtime_report_target_seconds'], hardware_result_pending=True)
    (out / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
