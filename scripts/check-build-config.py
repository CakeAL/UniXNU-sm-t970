#!/usr/bin/env python3
"""Check the resolved SM-T970 build configuration and the assembled source tree.

Step 4 of the porting guide: run defconfig/status/tree and verify that the
declared configuration (board.toml, feeds.toml, profile and series files)
agrees with what UniXNU resolved and assembled. This is a host check: it runs
no kernel build, no firmware build and no device command.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tomllib

DEVICE = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


def clean(path):
    # Untracked macOS metadata is not source; tracked edits still fail.
    return not git(path, 'status', '--porcelain', '--', '.', ':(exclude)*.DS_Store')


def norm(path):
    return Path(os.path.normpath(str(path)))


def run(unixnu, *args):
    env = dict(os.environ)
    env.update({'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'submodule.active',
                'GIT_CONFIG_VALUE_0': '__no_module_submodules__'})
    return subprocess.run([sys.executable, str(unixnu / 'unixnu'), *args, '-D', str(DEVICE)],
                          capture_output=True, text=True, env=env, timeout=600, check=True).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unixnu', type=Path, default=DEVICE.parent / 'UniXNU')
    parser.add_argument('--output', type=Path, default=DEVICE / 'out/build-config')
    args = parser.parse_args()
    unixnu = args.unixnu.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    board_toml = tomllib.loads((DEVICE / 'board.toml').read_text())
    feeds = {(s['kind'], s['name']): s for s in
             tomllib.loads((DEVICE / 'feeds.toml').read_text())['source']}
    lock = tomllib.loads((DEVICE / 'unixnu.lock').read_text())['source']
    status = json.loads(run(unixnu, 'status', '--json'))
    (output / 'status.json').write_text(json.dumps(status, indent=2) + '\n')

    # Identity and the configuration actually selected.
    board = board_toml['board']
    require(status['schema_version'] == 2, 'status schema_version is not 2')
    require(status['name'] == board['name'], 'status name differs from board.toml')
    require(status['configured'] is True, 'device is not configured')
    require(Path(status['config_path']).is_file(), 'generated .config is missing; run unixnu defconfig')
    require(status['configuration'] == board_toml['kernel']['defconfig'],
            'selected configuration differs from kernel.defconfig')
    build_config = status.get('build_config')
    if build_config:
        require(Path(build_config).is_file(), 'build_config path does not exist: ' + build_config)

    # Profiles are the reviewed arm64/SoC/iPadOS/device combination.
    profiles = status['profiles']
    arch = tomllib.loads((Path(profiles['arch']) / 'profile.toml').read_text())
    soc_profile = tomllib.loads((Path(profiles['soc']) / 'soc.toml').read_text())
    os_profile_path = Path(profiles['os'])
    os_profile = tomllib.loads((os_profile_path / 'profile.toml').read_text())
    require(arch['arch']['name'] == 'arm64' and arch['arch']['page_size'] == 4096,
            'unexpected architecture profile')
    require(os_profile_path.name == board['os_profile'], 'OS profile directory differs from board.toml')
    require(soc_profile['soc']['name'].lower() == board['soc_source'], 'SoC profile differs from board.soc_source')
    require(Path(profiles['device']).resolve() == DEVICE, 'device profile is not this repository')
    soc_feed = feeds[('soc', board['soc_source'])]
    require(git(profiles['soc'], 'rev-parse', 'HEAD') == soc_feed['commit'],
            'SoC checkout differs from feeds.toml')
    require(clean(profiles['soc']), 'SoC checkout is modified')

    # Configuration layers are applied in the documented order.
    expected_sources = [Path(profiles['arch']) / 'profile.toml',
                        Path(profiles['soc']) / 'soc.toml',
                        os_profile_path / 'profile.toml',
                        DEVICE / 'board.toml']
    require([norm(p) for p in status['configuration_sources']] == [norm(p) for p in expected_sources],
            'configuration source order differs from arch/SoC/OS/device')

    resolved = status['board']
    require(resolved['components']['include'] == board_toml['components']['include'],
            'component selection changed during resolution')
    require(resolved['kernel']['config_fragments'] == board_toml['kernel']['config_fragments'],
            'config fragment order changed during resolution')
    require(resolved['kernel']['patch_series'] == board_toml['kernel']['patch_series'],
            'patch series order changed during resolution')
    require(resolved['kernel']['prelink']['kernelcache_sha256'] ==
            os_profile['kernel']['prelink']['kernelcache_sha256'],
            'prelink kernelcache hash differs from the OS profile')
    archives = resolved['kernel']['archives']
    require(len(archives) == 8, 'unexpected archive recipe count')
    for entry in archives:
        if entry.startswith('component:'):
            require(entry.split(':', 1)[1] in board_toml['components']['include'],
                    'archive recipe for an unselected component: ' + entry)

    # Every selected component comes from its declared pin.
    catalog = {c['id']: c for c in status['components']}
    require(set(catalog) == set(board_toml['components']['include']),
            'resolved components differ from the board selection')
    for name in board_toml['components']['include']:
        spec = next(s for s in feeds.values() if s['name'] == name)
        component = catalog[name]
        require(component['revision'] == spec['commit'], name + ': revision differs from feeds.toml')
        require(not component['os_abi'] or board['os_profile'] in component['os_abi'],
                name + ': OS profile outside ABI scope')

    # Module checkouts match their pins and the lock file.
    modules = {(m['kind'], m['name']): m for m in status['modules']}
    require(len(status['modules']) == 19, 'unexpected module count')
    for (kind, name), module in modules.items():
        path = module['path']
        if kind in ('driver', 'kit'):
            require(path and Path(path).is_dir(), name + ': missing source checkout')
            spec = next(s for s in feeds.values() if s['name'] == name)
            require(module['pin'] == spec['commit'], name + ': pin differs from feeds.toml')
            require(git(path, 'rev-parse', 'HEAD') == module['pin'], name + ': checkout differs from pin')
            require(clean(path), name + ': checkout is modified')
        elif kind in ('refer', 'soc'):
            require(path and Path(path).is_dir(), name + ': missing fetched source')
            require(git(path, 'rev-parse', 'HEAD') == module['pin'], name + ': fetched source differs from pin')
            require(clean(path), name + ': fetched source is modified')
            require(lock.get(name, {}).get('commit') == module['pin'],
                    name + ': unixnu.lock differs from the resolved pin')
        elif kind == 'package' and name == 'device':
            require(Path(path).resolve() == DEVICE / 'package', 'device package is not this repository')
            require(module['revision'] == git(DEVICE, 'rev-parse', 'HEAD'),
                    'device package revision is not the current commit')

    # Patch order is resolved independently from the four declared series.
    bases = {'arch': Path(profiles['arch']), 'soc': Path(profiles['soc']),
             'os': os_profile_path, 'device': DEVICE}
    expected_patches = []
    groups = {}
    for series in board_toml['kernel']['patch_series']:
        prefix, _, relative = series.partition(':')
        base = bases[prefix]
        series_file = base / relative
        count = 0
        for line in series_file.read_text().splitlines():
            entry = line.strip()
            if not entry or entry.startswith('#'):
                continue
            if entry.startswith('component:'):
                name, _, inner = entry.split(':', 1)[1].partition('/')
                target = Path(modules[('kit', name)]['path']) / inner if ('kit', name) in modules \
                    else Path(modules[('driver', name)]['path']) / inner
            elif entry.startswith('arch:'):
                target = Path(profiles['arch']) / entry.split(':', 1)[1]
            else:
                target = series_file.parent / entry
            expected_patches.append(Path(target).resolve())
            count += 1
        groups[prefix] = count
    actual_patches = [Path(p).resolve() for p in status['patch_order']]
    require(actual_patches == expected_patches, 'resolved patch order differs from the declared series')
    require(len(set(actual_patches)) == len(actual_patches), 'duplicate patch in the resolved order')

    # The assembled tree must link the pinned sources, not stale copies.
    tree_output = run(unixnu, 'tree')
    (output / 'tree.txt').write_text(tree_output)
    tree = Path(status['output']) / 'tree'
    require(tree.is_dir(), 'assembled tree is missing')
    require(Path(tree / 'package').resolve() == unixnu / 'package', 'tree/package is not the framework package')
    require(Path(tree / 'components.toml').resolve() == unixnu / 'components.toml',
            'tree/components.toml is not the framework catalog')
    require(Path(tree / 'kits' / board['kit']).resolve() == DEVICE / 'package',
            'tree/kits/<kit> is not the device package')
    require(Path(tree / 'patches/xnu').resolve() == DEVICE / 'patches/xnu',
            'tree/patches/xnu is not the device patch series directory')
    links = {}
    by_target = {Path(m['path']).resolve(): m for m in modules.values() if m['path']}
    for folder, kinds in (('drivers', {'driver'}), ('kits', {'kit', 'package'}), ('refer', {'refer'})):
        for entry in sorted((tree / folder).iterdir()):
            require(entry.is_symlink(), f'tree/{folder}/{entry.name} is not a source link')
            target = entry.resolve()
            require(target in by_target, f'tree/{folder}/{entry.name} does not point at a resolved source')
            module = by_target[target]
            require(module['kind'] in kinds or (module['kind'] == 'driver' and folder == 'drivers'),
                    f'tree/{folder}/{entry.name} points at a {module["kind"]} source')
            if module['kind'] != 'soc':
                links[f'{folder}/{entry.name}'] = str(target)
    for (kind, name), module in modules.items():
        if kind in ('driver', 'kit', 'refer'):
            expected = {'driver': 'drivers', 'kit': 'kits', 'refer': 'refer'}[kind]
            require(Path(tree / expected / name).is_symlink(), f'tree/{expected}/{name} is missing')
            require(Path(tree / expected / name).resolve() == Path(module['path']).resolve(),
                    f'tree/{expected}/{name} differs from the resolved source')
    # The framework deliberately keeps SoC sources out of tree/refer (tree.py skips kind
    # "soc"); SoC scripts are merged into tree/scripts instead.
    require(not (tree / 'refer' / board['soc_source']).exists(),
            'SoC source was unexpectedly linked into tree/refer')
    for base in (unixnu, Path(profiles['soc']), DEVICE):
        scripts = base / 'scripts'
        if not scripts.is_dir():
            continue
        for path in sorted(p for p in scripts.rglob('*') if p.is_file() and '__pycache__' not in p.parts):
            staged = tree / 'scripts' / path.relative_to(scripts)
            require(staged.is_file(), 'tree/scripts is missing ' + str(path.relative_to(scripts)))
            require(staged.read_bytes() == path.read_bytes(),
                    'tree/scripts copy differs from source: ' + str(path.relative_to(scripts)))
    prelink_tool = tree / resolved['kernel']['prelink']['tool']
    require(prelink_tool.is_file(), 'prelink tool is missing from the assembled tree')

    (output / 'tree.json').write_text(json.dumps(
        {'links': links, 'scripts': len(list((tree / 'scripts').iterdir())),
         'soc_linked': (tree / 'refer' / board['soc_source']).exists()}, indent=2) + '\n')
    report = {
        'scope': 'Step 4 host resolution check; no kernel, firmware, payload or device work',
        'device_revision': git(DEVICE, 'rev-parse', 'HEAD'),
        'unixnu_revision': git(unixnu, 'rev-parse', 'HEAD'),
        'configuration': status['configuration'],
        'build_config': build_config,
        'profiles': {k: str(v) for k, v in profiles.items()},
        'configuration_sources': [str(norm(p)) for p in expected_sources],
        'components': sorted(catalog),
        'archives': archives,
        'patch_count': len(actual_patches),
        'patch_groups': groups,
        'modules': len(modules),
        'lock_sources': sorted(lock),
        'tree': str(tree),
        'tree_links': links,
        'tree_scripts': len(list((tree / 'scripts').iterdir())),
        'config_sha256': {p: hashlib.sha256((DEVICE / p).read_bytes()).hexdigest()
                          for p in ('board.toml', 'feeds.toml', 'unixnu.lock', 'configs/sm-t970_defconfig')},
        'result': 'PASS',
        'limits': ['Tree assembly and source pins are host facts; nothing was compiled or booted.',
                   'No unixnu.local.toml build inputs (kernelcache, trust cache, Data seed, unique chip id) exist yet.'],
    }
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'PASS: {len(actual_patches)} patches in order {groups}; {len(modules)} modules resolve to their pins.')
    print(f'PASS: assembled tree maps drivers, kits, refer, patches and scripts to the pinned sources.')
    print('Report: ' + str(output / 'result.json'))


if __name__ == '__main__':
    main()
