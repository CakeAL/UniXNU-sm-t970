#!/usr/bin/env python3
"""Build one isolated boot checkpoint image without changing board defaults.

No USB/device command is executed. Probe images and their private FDT/identity
inputs remain in ignored storage. Every run has a new output directory.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    device = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unixnu', type=Path, default=device.parent / 'UniXNU')
    parser.add_argument('--target', required=True, help='exact called kernel symbol, e.g. _idle_thread_create')
    parser.add_argument('--function', default='_kernel_bootstrap_thread')
    parser.add_argument('--before', action='store_true', help='reset immediately before the call, not after its return')
    parser.add_argument('--console-state', action='store_true', help='read console state before gc_enable; reset after 4/14/24/34 seconds')
    parser.add_argument('--exec-return-status', action='store_true', help='reviewed init exec: reset6seconds for zero return,16seconds for nonzero')
    parser.add_argument('--shared-map-result', action='store_true', help='display reviewed shared-map return through qualified panic renderer')
    parser.add_argument('--post-map-syscall', action='store_true', help='display a later PID1 syscall after successful cache syscall536')
    parser.add_argument('--initproc-main', action='store_true', help='display genuine launchd-main marker after original sysctl handler')
    parser.add_argument('--panic-kernel', type=Path, help='qualified normal kernel copy for --shared-map-result')
    parser.add_argument('--guard-early-faults', action='store_true', help='classify faults while testing PE_create_console return in arm_init')
    parser.add_argument('--brk-control', action='store_true', help='with --guard-early-faults, trigger BRK after MMU enable instead of running C startup')
    parser.add_argument('--occurrence', type=int, default=1)
    parser.add_argument('--delay', type=int, default=6, help='reset delay for an after-return probe')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--firmware-fd', type=Path, help='explicit reviewed FD instead of the current firmware build output')
    parser.add_argument('--kernel-arg', action='append', default=[], help='explicit diagnostic override added to board args')
    args = parser.parse_args()
    if sum((args.console_state, args.guard_early_faults, args.exec_return_status, args.shared_map_result, args.post_map_syscall, args.initproc_main)) > 1:
        parser.error('Select only one specialized probe')
    if bool(args.panic_kernel) != (args.shared_map_result or args.post_map_syscall or args.initproc_main):
        parser.error('--panic-kernel is required only for a qualified panic-result probe')
    if args.post_map_syscall and (args.target, args.function, args.before, args.occurrence, args.delay) != ('_native_t970_cache_syscall_note', '_unix_syscall', False, 1, 6):
        parser.error('--post-map-syscall requires reviewed unix callback, occurrence1 and default delay6')
    if args.initproc_main and (args.target, args.function, args.before, args.occurrence, args.delay) != ('_sysctl_handle_int', '_sysctl_initproc_spawned', False, 1, 6):
        parser.error('--initproc-main requires reviewed sysctl tail call, occurrence1 and default delay6')
    if args.shared_map_result and (args.target, args.function, args.before, args.occurrence, args.delay) != ('_vm_shared_region_map_file', '__shared_region_map_and_slide', False, 1, 6):
        parser.error('--shared-map-result requires the reviewed mapping call, occurrence1 and default delay6')
    if args.exec_return_status and (args.target, args.function, args.before, args.occurrence, args.delay) != ('___mac_execve', '_load_init_program_at_path', False, 1, 6):
        parser.error('--exec-return-status requires reviewed init exec, after-return occurrence1 and default delay6')
    if args.brk_control and not args.guard_early_faults:
        parser.error('--brk-control requires --guard-early-faults')
    if args.console_state and (args.target, args.function, args.before, args.occurrence) != ('_gc_enable', '_vcattach', True, 1):
        parser.error('--console-state requires --target _gc_enable --function _vcattach --before --occurrence 1')
    if args.guard_early_faults and (args.console_state or (args.target, args.function, args.before, args.occurrence) != ('_PE_create_console', '_arm_init', False, 1) or args.delay > 8):
        parser.error('--guard-early-faults requires PE_create_console after-return in arm_init, occurrence 1, delay 1..8')
    if any(not re.fullmatch(r'_[A-Za-z0-9_]+', value) for value in (args.target, args.function)):
        parser.error('Use exact kernel symbol names')
    if args.occurrence < 1 or not 1 <= args.delay <= 60:
        parser.error('Invalid occurrence or delay')
    output = args.output.resolve()
    ignored = subprocess.run(['git', '-C', str(device), 'check-ignore', str(output / 'probe')], capture_output=True)
    if output.exists() or ignored.returncode:
        parser.error('Choose a new Git-ignored output directory')
    sys.path.insert(0, str(args.unixnu.resolve() / 'scripts'))
    from unixnu.cli import parser as cli_parser
    from unixnu.config import Context
    from unixnu import feeds, tree, payload, bootimg, firmware
    ctx = Context(cli_parser().parse_args(['build', 'payload', '-D', str(device)]))
    # Keep checkpoint execution on the board line, without local default overrides.
    ctx.args.kernel_arg = args.kernel_arg
    ctx.uefi = ctx.option('uefi', 'UNIXNU_UEFI')
    dtb = ctx.option('dtb', 'UNIXNU_DTB')
    if ctx.uefi is None or dtb is None:
        parser.error('Set the dedicated uefi and firmware dtb in unixnu.local.toml')
    kernel = ctx.work / 'kernel/kernel.macho'
    if not kernel.is_file():
        parser.error('Build the source kernel first')
    fd = args.firmware_fd.resolve() if args.firmware_fd else firmware.fd_path(ctx, ctx.uefi, ctx.args.target)
    if not fd.is_file():
        parser.error('Build the matching firmware first')
    board_hash = sha(device / 'board.toml')
    kernel_hash = sha(kernel)
    tree.assemble(ctx, feeds.resolve(ctx))
    ctx.board = copy.deepcopy(ctx.board)
    spec = ctx.board['payload']
    for key in list(spec):
        if key.startswith('entry_probe_reset_') or key == 'panic_screen':
            del spec[key]
    spec.update(entry_probe_reset_delay=args.delay, entry_probe_reset_after=args.target,
                entry_probe_reset_in=args.function, entry_probe_reset_before=args.before,
                entry_probe_reset_occurrence=args.occurrence)
    # Keep the assembled sources and original kernel, but isolate all generated
    # DT/ADT, payload, logs and image output from the preceding experiment.
    output.mkdir(parents=True)
    ctx.work = output
    ctx.logs = output / 'logs'
    state = None
    fault = None
    exec_status = None
    map_result = None
    payload_kernel = kernel
    if args.shared_map_result or args.post_map_syscall or args.initproc_main:
        result_script = ('initproc-main-probe.py' if args.initproc_main else
                         'post-map-syscall-probe.py' if args.post_map_syscall else 'shared-map-result-probe.py')
        result_spec = importlib.util.spec_from_file_location('map_result_probe', device / 'scripts' / result_script)
        result_module = importlib.util.module_from_spec(result_spec)
        result_spec.loader.exec_module(result_module)
        payload_kernel = output / 'diagnostic/kernel.macho'
        map_result = result_module.patch_copy(kernel, args.panic_kernel.resolve(), payload_kernel, args.unixnu.resolve())
        ctx.logs.mkdir(parents=True, exist_ok=True)
        (ctx.logs / 'payload-patch.log').write_text('Qualified normal panic kernel; terminal diagnostic; no reset probe\n')
        for key in list(spec):
            if key.startswith('entry_probe_reset_'):
                del spec[key]
    if args.exec_return_status:
        status_spec = importlib.util.spec_from_file_location('exec_status_probe', device / 'scripts/exec-return-status-probe.py')
        status_module = importlib.util.module_from_spec(status_spec)
        status_spec.loader.exec_module(status_module)
        payload_kernel = output / 'diagnostic/kernel.macho'
        exec_status = status_module.patch_copy(kernel, payload_kernel, args.unixnu.resolve())
        ctx.logs.mkdir(parents=True, exist_ok=True)
        (ctx.logs / 'payload-patch.log').write_text(exec_status['entry_probe_log'] + '\nReplaced terminal cave with exec return status: zero6s/nonzero16s\n')
        for key in list(spec):
            if key.startswith('entry_probe_reset_'):
                del spec[key]
    if args.console_state:
        state_spec = importlib.util.spec_from_file_location('console_state_probe', device / 'scripts/console-state-probe.py')
        state_module = importlib.util.module_from_spec(state_spec)
        state_spec.loader.exec_module(state_module)
        payload_kernel = output / 'diagnostic/kernel.macho'
        state = state_module.patch_copy(kernel, payload_kernel, args.unixnu.resolve())
        ctx.logs.mkdir(parents=True, exist_ok=True)
        (ctx.logs / 'payload-patch.log').write_text(state['entry_probe_log'] + '\nconsole-state reset delays: 4/14/24/34 seconds; no call to gc_enable\n')
        # This copy already has entry bars and the state probe. Avoid patching it twice.
        for key in list(spec):
            if key.startswith('entry_probe_reset_'):
                del spec[key]
    if args.guard_early_faults:
        fault_spec = importlib.util.spec_from_file_location('early_fault_probe', device / 'scripts/early-fault-probe.py')
        fault_module = importlib.util.module_from_spec(fault_spec)
        fault_spec.loader.exec_module(fault_module)
        payload_kernel = output / 'diagnostic/kernel.macho'
        fault = fault_module.patch_copy(kernel, payload_kernel, args.unixnu.resolve(), args.delay, brk_control=args.brk_control)
        ctx.logs.mkdir(parents=True, exist_ok=True)
        (ctx.logs / 'payload-patch.log').write_text(fault['entry_probe_log'] + '\nearly fault classification: sync 20s / SError 30s / panic 40s / BRK 50s\n')
        for key in list(spec):
            if key.startswith('entry_probe_reset_'):
                del spec[key]
    image = payload.build(ctx, kernel=payload_kernel)
    boot = bootimg.build(ctx, ctx.uefi, fd, dtb, ramdisk=image, output=output / 'boot.img')
    gpt = json.loads((device / 'evidence/adb-2026-11-01/gpt.json').read_text())
    sizes = [p['size_bytes'] for lun in gpt.values() for p in lun['partitions'] if p['name'] == 'boot']
    if len(sizes) != 1 or boot.stat().st_size > sizes[0]:
        raise ValueError('Probe image does not fit the measured boot partition')
    if sha(device / 'board.toml') != board_hash or sha(kernel) != kernel_hash:
        raise ValueError('Source kernel or board defaults changed during the probe build')
    report = {'device_revision': subprocess.check_output(['git', '-C', str(device), 'rev-parse', 'HEAD'], text=True).strip(),
              'framework_revision': subprocess.check_output(['git', '-C', str(args.unixnu), 'rev-parse', 'HEAD'], text=True).strip(),
              'probe': {'function': args.function, 'target': args.target, 'occurrence': args.occurrence,
                        'position': 'before-call' if args.before else 'after-return',
                        'reset_delay_seconds': 0 if args.before else args.delay},
              'board_sha256': board_hash, 'source_kernel_sha256': kernel_hash,
              'firmware_sha256': sha(fd), 'firmware_dtb_sha256': sha(dtb),
              'boot_sha256': sha(boot), 'boot_bytes': boot.stat().st_size,
              'boot_partition_bytes': sizes[0], 'hardware_tested': False,
              'note': 'Probe modifies a payload copy only; no flash or reboot performed'}
    if state:
        report['console_state'] = state
        report['probe']['reset_delay_seconds'] = None
        report['generator_sha256'] = sha(device / 'scripts/console-state-probe.py')
    if exec_status:
        report['exec_return_status'] = exec_status
        report['probe']['reset_delay_seconds'] = None
        report['generator_sha256'] = sha(device / 'scripts/exec-return-status-probe.py')
    if map_result:
        result_key = 'initproc_main' if args.initproc_main else 'post_map_syscall' if args.post_map_syscall else 'shared_map_result'
        report[result_key] = map_result
        report['probe']['reset_delay_seconds'] = None
        report['probe']['position'] = 'terminal-panic-after-return'
        report['generator_sha256'] = sha(device / 'scripts' / result_script)
    if fault:
        report['fault_guard'] = fault
        report['generator_sha256'] = sha(device / 'scripts/early-fault-probe.py')
        if args.brk_control:
            report['probe'] = {'function': '_start_first_cpu', 'target': 'BRK #0',
                               'occurrence': 1, 'position': 'after-MMU-control', 'reset_delay_seconds': None}
    report['build_command'] = shlex.join(['python3.14', 'scripts/build-entry-probe.py', *sys.argv[1:]])
    (output / 'probe.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Prepared isolated probe:', output / 'probe.json')


if __name__ == '__main__':
    main()
