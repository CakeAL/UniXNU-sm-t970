#!/usr/bin/env python3
"""Check the two Step 5 inputs: the XNU hardware description and the firmware DTB.

The board DTS compiles into the ADT that XNU consumes. The captured firmware
DTB is a separate input for boot-image assembly. This host check verifies that
both exist, are distinct, carry what the selected components consume, and that
the firmware configuration includes the required UniXNU integration. It builds
no kernel, firmware or image and touches no device.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys

DEVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE / 'scripts'))
import fdt  # noqa: E402


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unixnu', type=Path, default=DEVICE.parent / 'UniXNU')
    parser.add_argument('--firmware-dtb', type=Path, default=DEVICE / 'out/firmware-inputs/firmware.dtb')
    parser.add_argument('--uefi', type=Path, default=DEVICE / '.cache/uefi-source/Mu-Silicium')
    parser.add_argument('--output', type=Path, default=DEVICE / 'out/hardware-description')
    args = parser.parse_args()
    unixnu, output = args.unixnu.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    # 1. The firmware input is a complete bootloader handoff tree.
    firmware = args.firmware_dtb.resolve()
    require(firmware.is_file(), 'firmware DTB is missing; run scripts/capture-firmware-dtb.py')
    firmware_blob = firmware.read_bytes()
    fw_header, fw_nodes = fdt.parse(firmware_blob)
    chosen = fw_nodes.get('/chosen', {})
    for key in ('bootargs', 'linux,initrd-start', 'linux,initrd-end'):
        require(key in chosen, 'firmware /chosen lacks ' + key)
    memory = fdt.reg_ranges(fw_nodes['/memory']['reg']) if '/memory' in fw_nodes else []
    require(memory, 'firmware DTB lacks /memory')
    require(any(p.startswith('/reserved-memory/') for p in fw_nodes), 'firmware DTB lacks reserved memory')
    require(fdt.strings(fw_nodes['/']['model']), 'firmware DTB lacks /model')

    # 2. The board DTS compiles and produces the ADT the components consume.
    sys.path.insert(0, str(unixnu / 'scripts'))
    from unixnu.cli import parser as cli_parser
    from unixnu.config import Context
    from unixnu import devicetree as dt
    ctx = Context(cli_parser().parse_args(['status', '--json', '-D', str(DEVICE)]))
    hardware = dt.compile_hardware(ctx)
    hardware_blob = hardware.read_bytes()
    board_nodes = fdt.parse(hardware_blob)[1]
    adt = dt.generate(hardware, ctx.board, unique_chip_id='1', data=False, trust=False)
    require(len(adt) > 0, 'ADT generation produced no bytes')
    decode_adt = load('check_platform', DEVICE / 'scripts/check-platform.py').decode_adt
    decoded = decode_adt(adt)
    for path in ('/chosen', '/cpus/cpu0', '/arm-io/intc'):
        require(path in decoded, 'ADT lacks ' + path)
    board_memory_node = next((props for path, props in board_nodes.items()
                              if path == '/memory' or path.startswith('/memory@')), None)
    require(board_memory_node is not None and 'reg' in board_memory_node,
            'board DTS build lacks a memory node')
    board_memory = fdt.reg_ranges(board_memory_node['reg'])
    require(struct.unpack('<QQ', decoded['/chosen']['dram-base'] + decoded['/chosen']['dram-size']) == board_memory[0],
            'ADT DRAM differs from the board DTS memory node')
    require(decoded['/cpus/cpu0']['reg'] == struct.pack('<I', 0), 'ADT boot CPU differs from the board DTS')
    require(decoded['/cpus/cpu0']['timebase-frequency'] == struct.pack('<I', 19200000),
            'ADT timer differs from the board DTS')
    require(decoded['/arm-io/intc']['redistributor-stride'] == struct.pack('<Q', 0x20000),
            'ADT GIC stride differs from the board DTS')

    # 3. The two inputs serve different purposes and must not be conflated.
    require('/chosen' not in board_nodes, 'board DTS unexpectedly carries a firmware /chosen node')
    require(hashlib.sha256(firmware_blob).hexdigest() != hashlib.sha256(hardware_blob).hexdigest(),
            'firmware DTB equals the board DTS build; the two inputs are distinct')

    # 4. The firmware configuration carries the required UniXNU integration.
    platform = DEVICE / 'package/firmware/Platforms/Samsung/gts7xlwifiPkg'
    dsc = (platform / 'gts7xlwifi.dsc').read_text()
    fdf = (platform / 'gts7xlwifi.fdf').read_text()
    required = ['UniXNUPkg/Application/UniXNU/UniXNU.inf',
                'UniXNUPkg/Driver/UniXNUDxe/UniXNUDxe.inf',
                'UniXNUPkg/Driver/UniXNURamDiskDxe/UniXNURamDiskDxe.inf',
                'DarwinBootPkg/Driver/DarwinBoot.inf',
                'UniXNUPkg/Driver/AdvancedLogDxe/AdvancedLogDxe.inf']
    for module in required:
        require(dsc.count(module) == 1, 'DSC is missing ' + module)
        require(fdf.count('INF ' + module) == 1, 'FDF is missing ' + module)
    uefi = args.uefi.resolve()
    boot_files = {}
    if (uefi / 'Mu_Basecore').is_dir():
        basecore = (uefi / 'Mu_Basecore/SiliciumPkg/SiliciumPkg.dsc.inc') if \
            (uefi / 'Mu_Basecore/SiliciumPkg').is_dir() else \
            (uefi / 'Silicon/Silicium/SiliciumPkg/SiliciumPkg.dsc.inc')
        basecore = uefi / 'Silicon/Silicium/SiliciumPkg/SiliciumPkg.dsc.inc' if \
            (uefi / 'Silicon/Silicium/SiliciumPkg/SiliciumPkg.dsc.inc').is_file() else basecore
        require(basecore.is_file(), 'pinned Mu base configuration is missing')
        base = basecore.read_text()
        for component in ('MdeModulePkg/Universal/Disk/DiskIoDxe/DiskIoDxe.inf',
                          'FatPkg/EnhancedFatDxe/Fat.inf',
                          'MdeModulePkg/Universal/Disk/UnicodeCollation/EnglishDxe/EnglishDxe.inf'):
            require(component in base, 'firmware base configuration lacks ' + component)
        boot_files['base_configuration'] = str(basecore)

    # 5. If the firmware was built, its volume must contain the integrations.
    fd = uefi / 'Build/gts7xlwifiPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd'
    fv = uefi / 'Build/gts7xlwifiPkg/DEBUG_CLANGPDB/FV/FVMAIN.Fv'
    built = {}
    if fd.is_file() and fv.is_file():
        files = load('collect_boot_firmware', DEVICE / 'scripts/collect-boot-firmware.py').files
        entries = list(files(fv.read_bytes(), 'FVMAIN'))
        guids = {e['guid'] for e, _ in entries}
        import re
        for label, inf in (
                ('UniXNU', unixnu / 'package/UniXNUPkg/Application/UniXNU/UniXNU.inf'),
                ('UniXNUDxe', unixnu / 'package/UniXNUPkg/Driver/UniXNUDxe/UniXNUDxe.inf'),
                ('RamDisk', unixnu / 'package/UniXNUPkg/Driver/UniXNURamDiskDxe/UniXNURamDiskDxe.inf'),
                ('DarwinBoot', unixnu / 'drivers/DarwinBoot/DarwinBootPkg/Driver/DarwinBoot.inf'),
                ('AdvancedLog', unixnu / 'package/UniXNUPkg/Driver/AdvancedLogDxe/AdvancedLogDxe.inf')):
            guid = re.search(r'FILE_GUID\s*=\s*([^\s]+)', inf.read_text()).group(1).lower()
            require(guid in guids, 'built firmware volume lacks ' + label)
        built = {'fd_bytes': fd.stat().st_size,
                 'fd_sha256': hashlib.sha256(fd.read_bytes()).hexdigest(),
                 'fv_files': len(entries)}

    report = {
        'scope': 'Step 5 host check of the two device-tree inputs and the firmware integration',
        'device_revision': __import__('subprocess').check_output(
            ['git', '-C', str(DEVICE), 'rev-parse', 'HEAD'], text=True).strip(),
        'firmware_dtb': {'path': str(firmware), 'bytes': len(firmware_blob),
                         'sha256': hashlib.sha256(firmware_blob).hexdigest(),
                         'nodes': len(fw_nodes), 'memory': [f'0x{a:x}+0x{s:x}' for a, s in memory],
                         'reserved_memory_entries': fw_header['reserved_map_entries'],
                         'chosen_properties': sorted(chosen)},
        'board_dts': {'bytes': len(hardware_blob), 'sha256': hashlib.sha256(hardware_blob).hexdigest(),
                      'nodes': len(board_nodes), 'memory': [f'0x{a:x}+0x{s:x}' for a, s in board_memory],
                      'adt_bytes': len(adt)},
        'firmware_integration': {'dsc': True, 'fdf': True, **boot_files},
        'built_firmware': built,
        'result': 'PASS',
        'limits': ['The ADT was generated with artificial identity 1 and is not a boot input.',
                   'The firmware DTB is the stock bootloader handoff tree; its /chosen identity values stay in ignored storage.',
                   'Nothing was compiled into a payload, written to the device or booted.'],
    }
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: firmware DTB is a complete handoff tree; board DTS compiles to an ADT with the consumed resources.')
    print('PASS: the two DTBs are distinct and the firmware config/volume carry the required UniXNU integration.')
    print('Report: ' + str(output / 'result.json'))


if __name__ == '__main__':
    main()
