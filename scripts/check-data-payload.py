#!/usr/bin/env python3
"""Independently unpack Data BOOT inputs and reject the PMGR bootstrap stub.

Host checks only. This neither flashes a device nor proves an APFS mount.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tomllib

DEVICE = Path(__file__).resolve().parents[1]


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--boot', type=Path, required=True)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--watchdog-policy', action='store_true',
                        help='Require the explicit RAM-only watchdog launch policy argument and symbols')
    parser.add_argument('--runtime-report-seconds', type=int, default=0,
                        help='Require the explicit terminal runtime sampler interval (5..300)')
    parser.add_argument('--smp-observer', action='store_true',
                        help='Require per-core counters and the read-only reset-context accessor')
    parser.add_argument('--publish-reset-state', action='store_true',
                        help='Require the explicit reset translation-state publication argument')
    parser.add_argument('--ipi-check', action='store_true', help='Require the explicit bounded CPU1 SGI delivery check')
    parser.add_argument('--cache-trace', action='store_true', help='Require compact runtime PID1 cache trace')
    parser.add_argument('--display-probe', action='store_true', help='Require explicit T970 GOP service probe arguments and linked callbacks')
    parser.add_argument('--cpu-present', action='store_true', help='Require continuous CPU presentation arguments')
    parser.add_argument('--ui-exit-probe', action='store_true', help='Require native XNU UI error-exit trap')
    parser.add_argument('--ui-spawn-calls', action='store_true', help='Require optional bounded spawn-return path observer')
    parser.add_argument('--key-state', action='store_true', help='Require pinned RAM-only KeyStore state service and board registration')
    parser.add_argument('--ui-wait', action='store_true', help='Require bounded saved-register UI diagnostics')
    parser.add_argument('--ui-stack-mode',type=int,choices=(1,2,3,4,5),default=1)
    parser.add_argument('--ui-stack', action='store_true', help='Require opt-in isolated UI stack worker')
    args = parser.parse_args()
    require(args.runtime_report_seconds == 0 or 5 <= args.runtime_report_seconds <= 300,
            'Runtime sampler interval must be 5..300 seconds')
    work, out = args.work.resolve(), args.output.resolve()
    require(not out.exists(), 'Use a new verification output directory')
    # Audit the actual archive and linked source kernel, not just the switch.
    pmgr = work / 'tree/build/sheng-platform-power'
    archive = pmgr / 'libShengPlatformPower.a'
    pmgr_report = json.loads((pmgr / 'build-report.json').read_text())
    require(pmgr_report['virtual_entries'] == 340 and
            pmgr_report['archive_sha256'] == sha(archive.read_bytes()), 'PMGR archive/report mismatch')
    members = subprocess.check_output(['xcrun', 'ar', 't', str(archive)], text=True).splitlines()
    objects = [name for name in members if name not in ('__.SYMDEF', '__.SYMDEF SORTED')]
    require(len(objects) == 2 and set(objects) == {'ShengPlatformPower.late.o', 'original-bindings.o'},
            'PMGR contains a stub/unexpected object')
    kernel = work / 'kernel/kernel.macho'
    symbols = subprocess.check_output(['/opt/homebrew/opt/llvm/bin/llvm-nm', '--defined-only', str(kernel)], text=True)
    names = {line.split()[-1] for line in symbols.splitlines() if line.split()}
    require({'_sheng_pmgr_run', '__GLOBAL__sub_I_ShengPlatformPower.cpp',
             '__ZTV18ShengPlatformPower', '_native_ram_block_volume_seed'} <= names,
            'Kernel lacks the real PMGR bridge or RamBlock')
    if args.watchdog_policy:
        require({'_native_t970_watchdog_policy_stage', '_native_t970_watchdog_policy_status'} <= names,
                'Kernel lacks the opt-in watchdog policy implementation')
    if args.runtime_report_seconds:
        require({'_native_t970_runtime_collect', '_native_t970_runtime_report',
                 '_native_t970_initproc_main'} <= names, 'Kernel lacks the runtime sampler')
    if args.smp_observer:
        require((args.runtime_report_seconds or args.cpu_present) and {'_native_t970_reset_context', '_processor_avail_count',
                '_armcpu_smp_step', '_armcpu_smp_psci_rc', '_armcpu_smp_fail',
                '_armcpu_core_timer', '_armcpu_core_sgi'} <= names, 'Kernel lacks SMP observation interfaces')
    report = json.loads((work / 'payload/payload.json').read_text())
    require(sha(kernel.read_bytes()) == report['kernel_sha256'], 'Source kernel changed after payload build')
    out.mkdir(parents=True)
    for name in ('kernel.macho', 'kernel.macho.adt', 'kernel.macho.trustcache', 'scratch-data.img'):
        subprocess.run(['mcopy', '-i', str(work / 'payload/payload.img'),
                        '::/EFI/UniXNU/Payloads/' + name, str(out / name)], check=True)
    require(sha((out / 'kernel.macho').read_bytes()) == report['payload_kernel_sha256'], 'Packed kernel mismatch')
    base = DEVICE / 'out/step7/probes/policy-release-normal/independent'
    config_text = subprocess.check_output(['mtype', '-i', str(work / 'payload/payload.img'),
                                           '::/EFI/UniXNU/unixnu.toml'], text=True)
    config = tomllib.loads(config_text)
    entry = next(e for e in config['entry'] if e['id'] == 'xnu')
    base_config = tomllib.loads((base.parent / 'unixnu.toml').read_text())
    base_args = next(e for e in base_config['entry'] if e['id'] == 'xnu')['args'].split()
    expected_args = base_args + (['t970-disable-watchdogd=1'] if args.watchdog_policy else [])
    if args.runtime_report_seconds:
        expected_args += [f't970-runtime-report={args.runtime_report_seconds}']
    if args.publish_reset_state:
        expected_args += ['t970-smp-publish-state=1']
        require(b't970-smp-publish-state\0' in kernel.read_bytes(), 'Kernel lacks publication opt-in')
    if args.ipi_check:
        expected_args += ['t970-ipi-check=1']
        require(b't970-ipi-check\0' in kernel.read_bytes(), 'Kernel lacks IPI check opt-in')
    if args.cache_trace:
        expected_args += ['t970-runtime-cache-trace=1']
        require('_native_t970_cache_trace_text' in names and b't970-runtime-cache-trace\0' in kernel.read_bytes(), 'Kernel lacks compact cache trace')
    if args.display_probe:
        expected_args += ['t970-display-start=1','offline-mobile-graphics-load=1','offline-legacy-register=1','offline-legacy-gop=1','offline-legacy-phase=4','offline-legacy-pm=1']
        require(all(n in names for n in ['_native_legacy_display_probe','_native_legacy_display_late_probe','_native_legacy_gop_mapping_observed']), 'Missing display callbacks')
    if args.cpu_present:
        require(args.display_probe, 'CPU presentation requires explicit display probe')
        expected_args += ['offline-legacy-transfer=1','offline-legacy-validate=1','offline-legacy-cpu-present=1','offline-legacy-retire=1','sheng-vsync=60']
    if args.ui_exit_probe:
        require(args.display_probe and args.runtime_report_seconds, 'UI exit trap requires bounded display diagnostics')
        expected_args += ['panic_on_error_exit=backboardd,SpringBoard']
        require(b'panic_on_error_exit\0' in kernel.read_bytes(), 'Kernel lacks native error-exit tunable')
    if args.ui_spawn_calls:
        require(args.runtime_report_seconds and args.display_probe, 'UI call observer requires bounded display diagnostic')
        expected_args += ['t970-ui-spawn-calls=1']
        require('_native_t970_ui_calls_text' in names and b't970-ui-spawn-calls\0' in kernel.read_bytes(), 'Missing UI call observer')
    if args.key_state:
        require(args.display_probe and args.runtime_report_seconds, 'Key state requires bounded display diagnostics')
        expected_args += ['offline-key-events=1', 'sheng-aks=1']
        require({'_t970_keystore_start', '_native_t970_keystore_state', '_native_keyevents_allocate',
                 '_native_aks_state_enabled', '_native_aks_encode_state'} <= names, 'Missing key-state implementation')
        archive = work / 'tree/build/native-legacy-display/libNativeLegacyDisplay.late.a'
        key_report = json.loads(archive.with_name('build-report.json').read_text())
        require(sha(archive.read_bytes()) == key_report['archive_sha256'], 'Display/key-state archive hash mismatch')
        state = key_report.get('key_state') or {}
        require(state.get('component') == 'AppleKeyStoreState' and
                state.get('revision') == '42ff83e08b2265fe741d4adaf084bebe003452ba' and
                state.get('callbacks_resolved'), 'Unqualified key-state component')
    if args.ui_wait:
        require(args.display_probe and args.cache_trace and args.runtime_report_seconds,
                'UI saved registers require bounded display/cache diagnostics')
        expected_args += ['t970-ui-wait=1']
        require('_native_t970_ui_wait_text' in names and b'UI saved-regs:' in kernel.read_bytes(), 'Missing UI saved-register sampler')
    if args.ui_stack:
        require(args.ui_wait, 'UI stack requires UI wait diagnostic')
        expected_args += [f't970-ui-stack={args.ui_stack_mode}']
        require(b'UI stack worker busy' in kernel.read_bytes(), 'Missing isolated stack worker')
    require(sorted(entry['args'].split()) == sorted(expected_args), 'Unexpected effective boot arguments')
    require(config['boot']['default'] == 'xnu' and entry['initrd'] == 'Payloads/scratch-data.img',
            'Wrong default entry/Data initrd')
    require((out / 'kernel.macho.trustcache').read_bytes() == (base / 'kernel.macho.trustcache').read_bytes(),
            'Original trust cache changed')
    require((out / 'scratch-data.img').read_bytes() == args.seed.read_bytes(), 'Data seed mismatch')
    spec = importlib.util.spec_from_file_location('platform_check', DEVICE / 'scripts/check-platform.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    actual = module.decode_adt((out / 'kernel.macho.adt').read_bytes())
    expected = module.decode_adt((base / 'kernel.macho.adt').read_bytes())
    for tree in (actual, expected):
        tree['/chosen'].pop('random-seed')
    expected['/chosen']['darwinboot-memory-size'] = struct.pack('<Q', 0x20000000)
    expected['/chosen']['ephemeral-storage'] = struct.pack('<I', 1)
    expected['/chosen/memory-map']['PackedRAMDisk'] = bytes(16)
    require(actual == expected, 'Unexpected hardware/identity/root/ADT change')
    raw = args.boot.read_bytes()
    require(raw[:8] == b'ANDROID!', 'Missing Android header')
    ks, rs = struct.unpack_from('<I', raw, 8)[0], struct.unpack_from('<I', raw, 16)[0]
    page, version = struct.unpack_from('<II', raw, 36)
    require((page, version) == (4096, 2), 'Wrong Android format')
    align = lambda n: ((n + page - 1) // page) * page
    rd = page + align(ks)
    require(raw[rd:rd + rs] == (work / 'payload/payload.img').read_bytes(), 'BOOT ramdisk mismatch')
    fd = (DEVICE / 'out/step7/ufs-readonly-inputs/SILICIUM_UEFI.fd').read_bytes()
    require(sha(fd) == '515105d758a9d61078dffce5012db0754a71cec351a1bb34b30ee791196b5690'
            and ks == len(fd) + 112 and raw[page + 112:page + ks] == fd, 'Wrong firmware')
    require(struct.unpack_from('<I', raw, 24)[0] == 0 and struct.unpack_from('<I', raw, 1632)[0] == 0,
            'Unexpected second/recovery DTBO section')
    dtb_size = struct.unpack_from('<I', raw, 1648)[0]
    dtb = raw[align(rd + rs):align(rd + rs) + dtb_size]
    require(dtb == (DEVICE / 'out/firmware-inputs/firmware.dtb').read_bytes(), 'Wrong firmware DTB')
    require(report['panic_screen'] and len(raw) <= 71303168, 'Missing panic diagnostics or oversized BOOT')
    full = raw + bytes(71303168 - len(raw))
    (out / 'boot-partition.img').write_bytes(full)
    result = dict(boot_sha256=sha(full), boot_bytes=len(full), raw_boot_sha256=sha(raw),
                  kernel_sha256=report['kernel_sha256'], payload_kernel_sha256=report['payload_kernel_sha256'],
                  pmgr_archive_sha256=pmgr_report['archive_sha256'], pmgr_members=members,
                  real_pmgr_and_ramblock_symbols=True, trustcache_unchanged=True,
                  adt_only_expected_changes=True, exact_fd_dtb=True, zero_tail=True,
                  seed_sha256=sha(args.seed.read_bytes()), hardware_data_mount_verified=False)
    result['watchdog_policy_requested'] = args.watchdog_policy
    result['kernel_args'] = entry['args']
    result['runtime_report_target_seconds'] = args.runtime_report_seconds
    result['terminal_diagnostic'] = bool(args.runtime_report_seconds)
    result['smp_observer'] = args.smp_observer
    result['publish_reset_state_requested'] = args.publish_reset_state
    result['ipi_check_requested'] = args.ipi_check
    result['continuous_cpu_present'] = args.cpu_present and args.runtime_report_seconds == 0
    result['runtime_cache_trace_requested'] = args.cache_trace
    result['key_state_requested'] = args.key_state
    result['ui_wait_requested'] = args.ui_wait
    (out / 'validation.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
