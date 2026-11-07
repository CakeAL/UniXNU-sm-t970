#!/usr/bin/env python3
"""v88: request a real 3840 MiB EFI allocation with the pre-v87 kernel."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess

DEVICE = Path(__file__).resolve().parents[3]
BASE = DEVICE / 'out/data-bringup/setup-8g-v85/boot-partition.img'
OUTPUT = DEVICE / 'out/data-bringup/owned-window-v88'
REQUEST = 3840 * 1024**2
PREFIX = '::/EFI/UniXNU/'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    # Bind the base to its committed preparation, including the complete hash.
    baseline = json.loads((DEVICE / 'evidence/memory/8g-v85/preparation.json').read_text())
    boot = BASE.read_bytes()
    if sha(boot) != baseline['boot_sha256'] or len(boot) != 71303168:
        raise ValueError('Expected the preserved v85 partition image')
    kernel_size, = struct.unpack_from('<I', boot, 8)
    payload_size, = struct.unpack_from('<I', boot, 16)
    page, version = struct.unpack_from('<II', boot, 36)
    if boot[:8] != b'ANDROID!' or (page, version) != (4096, 2):
        raise ValueError('Require Android v2/4096')
    start = page + ((kernel_size + page - 1) // page) * page
    end = start + payload_size
    if not start < end < len(boot):
        raise ValueError('Invalid payload bounds')
    OUTPUT.mkdir(parents=True, exist_ok=False)
    fat = OUTPUT / 'payload.img'
    fat.write_bytes(boot[start:end])

    def read(name):
        return subprocess.check_output(['mcopy', '-i', str(fat), PREFIX + name, '-'])

    names = ['unixnu.toml', 'Payloads/kernel.macho', 'Payloads/kernel.macho.adt',
             'Payloads/scratch-data.img', 'Payloads/kernel.macho.trustcache']
    before = {name: read(name) for name in names}
    if sha(before['Payloads/kernel.macho']) != baseline['kernel_sha256']:
        raise ValueError('Require the v85 kernel without managed-range override')
    spec = importlib.util.spec_from_file_location('owned', DEVICE / 'scripts/prepare-owned-window.py')
    owned = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(owned)
    adt = before['Payloads/kernel.macho.adt']
    patched = owned.replace_request(adt, REQUEST, expected_size=0x80000000)
    target = OUTPUT / 'kernel.macho.adt'
    target.write_bytes(patched)
    subprocess.run(['mcopy', '-o', '-i', str(fat), str(target),
                    PREFIX + 'Payloads/kernel.macho.adt'], check=True)
    for name in names:
        expected = patched if name.endswith('.adt') else before[name]
        if read(name) != expected:
            raise ValueError('Unexpected payload change: ' + name)
    result = boot[:start] + fat.read_bytes() + boot[end:]
    if len(result) != len(boot) or result[:start] != boot[:start] or result[end:] != boot[end:]:
        raise ValueError('Firmware/header/DTB/partition tail changed')
    (OUTPUT / 'boot-partition.img').write_bytes(result)
    report = dict(base_boot_sha256=sha(boot), boot_sha256=sha(result), boot_bytes=len(result),
                  kernel_sha256=baseline['kernel_sha256'], adt_sha256=sha(patched),
                  owned_memory_size=hex(REQUEST), physical_envelope_size='0x200000000',
                  unchanged_kernel_seed_config_trust=True, unchanged_header_firmware_dtb_tail=True,
                  source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=DEVICE, text=True).strip(),
                  device_verified=False, uploaded=False)
    (OUTPUT / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
