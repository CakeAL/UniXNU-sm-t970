#!/usr/bin/env python3
"""Repack the v60 memory control or remove v62's terminal runtime report."""
import argparse
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import struct
import subprocess
import tomllib

DEVICE = Path(__file__).resolve().parents[3]
BASE = DEVICE / 'out/data-bringup/adt-control-v60/boot-partition.img'
BASE_SHA = '33abac1d790f9ee977d27f48f0f40489bcbf1a77b779c3db61cbc30f35d31659'
V62 = DEVICE / 'out/data-bringup/owned-window-2g-v62/boot-partition.img'
V62_SHA = '07f38ad95b31fac15da857c9495f322c327b9509ee6e2b8e330dfb286ea5f800'
OLD_SIZE = 768 * 1024**2
NEW_SIZE = 2 * 1024**3
ADT_PATH = 'Payloads/kernel.macho.adt'
CONFIG_PATH = 'unixnu.toml'
UNCHANGED = (
    'Payloads/kernel.macho',
    'Payloads/kernel.macho.trustcache',
    'Payloads/scratch-data.img',
)


def load_script(name):
    spec = spec_from_file_location(name, DEVICE / 'scripts' / (name + '.py'))
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_fat(image, path):
    return subprocess.check_output(['mcopy', '-i', str(image), '::/EFI/UniXNU/' + path, '-'])


def remove_terminal_report(blob, require):
    text = blob.decode()
    expected = tomllib.loads(text)
    entries = [entry for entry in expected['entry'] if entry['type'] == 'xnu']
    require(len(entries) == 1, 'Expected exactly one XNU boot entry')
    entry = entries[0]
    arguments = entry['args'].split()
    report_args = [arg for arg in arguments if arg.split('=', 1)[0] == 't970-runtime-report']
    require(report_args == ['t970-runtime-report=120'], 'Unexpected runtime report arguments')
    line = 'args = "' + entry['args'] + '"'
    require(text.count(line) == 1, 'Expected exactly one matching XNU args line')
    arguments.remove(report_args[0])
    entry['args'] = ' '.join(arguments)
    updated = text.replace(line, 'args = "' + entry['args'] + '"')
    require(tomllib.loads(updated) == expected, 'Unexpected boot configuration difference')
    return updated.encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--continuous', action='store_true', help='Repack exact uploaded v62')
    args = parser.parse_args()
    window = load_script('prepare-owned-window')
    decode_adt = load_script('check-platform').decode_adt
    base, base_sha = (V62, V62_SHA) if args.continuous else (BASE, BASE_SHA)
    source = base.read_bytes()
    window.require(len(source) == window.PARTITION_BYTES and window.digest(source) == base_sha,
                   'Unqualified source BOOT')
    window.require(source.startswith(b'ANDROID!'), 'Missing Android header')
    kernel_size, = struct.unpack_from('<I', source, 8)
    payload_size, = struct.unpack_from('<I', source, 16)
    page, version = struct.unpack_from('<II', source, 36)
    window.require((page, version) == (4096, 2), 'Requires Android header v2 and 4096-byte pages')
    offset = page + ((kernel_size + page - 1) // page) * page
    end = offset + payload_size
    window.require(end < len(source), 'Invalid ramdisk bounds')

    out = args.output.resolve()
    out.mkdir(parents=True)
    payload = out / 'payload.img'
    payload.write_bytes(source[offset:end])
    if args.continuous:
        adt = decode_adt(read_fat(payload, ADT_PATH))
        window.require(adt['/chosen']['darwinboot-memory-size'] == struct.pack('<Q', NEW_SIZE),
                       'Expected the qualified 2 GiB ADT')
        changed_path = CONFIG_PATH
        original = read_fat(payload, changed_path)
        modified = remove_terminal_report(original, window.require)
        unchanged_paths = (*UNCHANGED, ADT_PATH)
    else:
        changed_path = ADT_PATH
        original = read_fat(payload, changed_path)
        modified = window.replace_request(original, NEW_SIZE, expected_size=OLD_SIZE)
        expected = decode_adt(original)
        expected['/chosen']['darwinboot-memory-size'] = struct.pack('<Q', NEW_SIZE)
        window.require(decode_adt(modified) == expected, 'Unexpected ADT difference')
        unchanged_paths = (CONFIG_PATH, *UNCHANGED)
    unchanged = {path: window.digest(read_fat(payload, path)) for path in unchanged_paths}

    changed_file = out / Path(changed_path).name
    changed_file.write_bytes(modified)
    subprocess.run(['mcopy', '-o', '-i', str(payload), str(changed_file),
                    '::/EFI/UniXNU/' + changed_path], check=True)
    packed_payload = payload.read_bytes()
    window.require(len(packed_payload) == payload_size, 'Ramdisk size changed')
    boot = out / 'boot-partition.img'
    boot.write_bytes(source[:offset] + packed_payload + source[end:])
    result = boot.read_bytes()
    window.require(result[:offset] == source[:offset] and result[end:] == source[end:],
                   'Header, firmware, DTB or partition tail changed')
    verification_payload = out / 'roundtrip-payload.img'
    verification_payload.write_bytes(result[offset:end])
    window.require(read_fat(verification_payload, changed_path) == modified,
                   'Final BOOT input differs: ' + changed_path)
    for path, expected_sha in unchanged.items():
        window.require(window.digest(read_fat(verification_payload, path)) == expected_sha,
                       'Final BOOT input differs: ' + path)
    verification_payload.unlink()

    report = {
        'base_boot_sha256': base_sha,
        'boot_sha256': window.digest(result),
        'boot_bytes': len(result),
        'requested_bytes': NEW_SIZE,
        'unchanged_payload_sha256': unchanged,
        'unchanged_header_firmware_dtb_tail': True,
        'uploaded': False,
    }
    if args.continuous:
        report.update(removed_argument='t970-runtime-report=120',
                      base_config_sha256=window.digest(original),
                      config_sha256=window.digest(modified),
                      terminal_runtime_report=False)
    else:
        report.update(base_adt_sha256=window.digest(original), adt_sha256=window.digest(modified),
                      old_requested_bytes=OLD_SIZE,
                      only_adt_property_changed='/chosen/darwinboot-memory-size',
                      target_report_seconds=120, hardware_allocation_verified=False)
    (out / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
