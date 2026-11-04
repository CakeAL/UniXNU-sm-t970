#!/usr/bin/env python3
"""Make a matched RAM-Data control and SpringBoard anti-dimming BOOT pair."""
import argparse
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import plistlib
import struct
import subprocess
import tempfile
import tomllib

DEVICE = Path(__file__).resolve().parents[3]
FRAMEWORK = DEVICE.parent / 'UniXNU'
BASE = DEVICE / 'out/data-bringup/pm-watchdog-v67/boot-partition.img'
BASE_SHA = '32fa945786c2afc6e21ddddde1f629736d90c26416de6629e87e2e786b3ca3cc'
FAT = '::/EFI/UniXNU/'
SEED = 'Payloads/scratch-data.img'
CONFIG = 'unixnu.toml'
UNCHANGED = ('Payloads/kernel.macho', 'Payloads/kernel.macho.adt', 'Payloads/kernel.macho.trustcache')
PREFS = {'SBDisableAutoDim': True, 'SBDisableIdleSleep': True, 'SBDontDimOrLockOnAC': True}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def seed_with_preferences(original, output):
    # Reuse the framework's packed-Data parser and preference merge helper without
    # invoking its Setup-skip entry point.
    spec = spec_from_file_location('data_seed', FRAMEWORK / 'scripts/seed-data-skip-setup.py')
    helper = module_from_spec(spec)
    spec.loader.exec_module(helper)
    logical, extents = helper.packed_ramdisk.regions(original)
    with tempfile.TemporaryDirectory(dir=output.parent) as tmp:
        mount = Path(tmp) / 'mount'
        mount.mkdir()
        raw = Path(tmp) / 'seed.raw'
        with raw.open('wb') as stream:
            stream.truncate(logical)
            for offset, data in extents:
                stream.seek(offset)
                stream.write(data)
        attach = plistlib.loads(subprocess.check_output([
            'hdiutil', 'attach', '-imagekey', 'diskimage-class=CRawDiskImage',
            '-nobrowse', '-owners', 'on', '-mountpoint', str(mount), '-plist', str(raw)]))
        device = attach['system-entities'][0]['dev-entry']
        try:
            require(os.path.ismount(mount) and (mount / 'mobile').is_dir(), 'Missing Data mount')
            info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(mount)]))
            uuid = info.get('VolumeUUID')
            require(uuid == 'C25160D3-B586-4C11-9D3A-42CB2741227C', 'Wrong Data seed UUID')
            domain = 'com.apple.springboard'
            pref = mount / 'mobile/Library/Preferences' / (domain + '.plist')
            old = plistlib.loads(pref.read_bytes()) if pref.exists() else {}
            require(all(old.get(key) is not True for key in PREFS), 'Preference already enabled in control')
            helper.merge_pref(mount, domain, PREFS)
            require(plistlib.loads(pref.read_bytes()) == {**old, **PREFS}, 'Unexpected preference difference')
            require(pref.stat().st_uid == 501 and (pref.stat().st_mode & 0o777) == 0o600,
                    'Preference must be readable by iPadOS mobile (UID 501)')
        finally:
            subprocess.run(['hdiutil', 'detach', device], check=True)
        metadata = helper.packed_ramdisk.pack(raw, output)
    require(metadata['bytes'] == logical and metadata['packed'], 'Data seed geometry changed')
    return dict(metadata, volume_uuid=uuid, preferences=PREFS, previous_values={key: old.get(key) for key in PREFS})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    root = parser.parse_args().output.resolve()
    boot = BASE.read_bytes()
    require(sha(boot) == BASE_SHA and boot[:8] == b'ANDROID!', 'Wrong v67 BOOT')
    kernel_size, = struct.unpack_from('<I', boot, 8)
    payload_size, = struct.unpack_from('<I', boot, 16)
    page, version = struct.unpack_from('<II', boot, 36)
    require((page, version) == (4096, 2), 'Unexpected BOOT format')
    start = page + ((kernel_size + page - 1) // page) * page
    end = start + payload_size
    require(start < end < len(boot), 'Invalid FAT bounds')
    root.mkdir(parents=True)
    original_fat = root / 'baseline.fat'
    original_fat.write_bytes(boot[start:end])

    def read(fat, path):
        return subprocess.check_output(['mcopy', '-i', str(fat), FAT + path, '-'])

    cfg = read(original_fat, CONFIG).decode()
    entries = tomllib.loads(cfg)
    xnu = [e for e in entries['entry'] if e['type'] == 'xnu']
    require(len(xnu) == 1 and xnu[0]['initrd'] == SEED, 'Unexpected XNU boot entry')
    args = xnu[0]['args'].split()
    require(args.count('sheng-data-persist=2') == 1, 'Expected persistent v67 base')
    require(args.count('t970-runtime-report=240') == 1, 'Expected v67 runtime report')
    line = 'args = "' + xnu[0]['args'] + '"'
    require(cfg.count(line) == 1, 'Ambiguous XNU boot arguments')
    # Both images use disposable RAM Data and the same longer report deadline.
    args[args.index('sheng-data-persist=2')] = 'sheng-data-persist=0'
    args[args.index('t970-runtime-report=240')] = 't970-runtime-report=360'
    xnu[0]['args'] = ' '.join(args)
    updated = cfg.replace(line, 'args = "' + xnu[0]['args'] + '"')
    require(tomllib.loads(updated) == entries, 'Unexpected boot argument change')
    config = root / CONFIG
    config.write_text(updated)
    original_seed = read(original_fat, SEED)
    seed = root / 'springboard-dim.dbr'
    seed_metadata = seed_with_preferences(original_seed, seed)
    fixed = {name: sha(read(original_fat, name)) for name in UNCHANGED}

    images = {}
    for name in ('control', 'anti-dim'):
        case = root / name
        case.mkdir()
        fat = case / 'payload.img'
        fat.write_bytes(original_fat.read_bytes())
        subprocess.run(['mcopy', '-o', '-i', str(fat), str(config), FAT + CONFIG], check=True)
        if name == 'anti-dim':
            subprocess.run(['mcopy', '-o', '-i', str(fat), str(seed), FAT + SEED], check=True)
        require(fat.stat().st_size == payload_size, 'FAT size changed')
        packed = case / 'boot-partition.img'
        packed.write_bytes(boot[:start] + fat.read_bytes() + boot[end:])
        result = packed.read_bytes()
        require(result[:start] == boot[:start] and result[end:] == boot[end:], 'Unexpected BOOT difference')
        fat.write_bytes(result[start:end])
        expected_seed = seed.read_bytes() if name == 'anti-dim' else original_seed
        require(read(fat, CONFIG) == config.read_bytes() and read(fat, SEED) == expected_seed,
                'Final FAT settings or Data seed mismatch')
        require(all(sha(read(fat, path)) == digest for path, digest in fixed.items()),
                'Final FAT changed a common input')
        images[name] = dict(boot_sha256=sha(result), boot_bytes=len(result), seed_sha256=sha(expected_seed))
    report = dict(base_boot_sha256=BASE_SHA, data_mode=0, report_seconds=360,
                  shared_payload_sha256={**fixed, CONFIG: sha(config.read_bytes())},
                  treatment_seed=seed_metadata, images=images)
    (root / 'preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
