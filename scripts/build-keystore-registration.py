#!/usr/bin/env python3
"""Build the pinned AppleKeyStoreState and board callbacks in an isolated tree."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tomllib

DEVICE = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('tree', 'framework', 'output'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    tree, fw, out = a.tree.resolve(), a.framework.resolve(), a.output.resolve()
    if out.exists():
        raise ValueError('Preserve earlier outputs')
    catalog = tomllib.loads((fw / 'components.toml').read_text())
    component = next(c for c in catalog['component'] if c['id'] == 'AppleKeyStoreState')
    assert component['revision'] == '42ff83e08b2265fe741d4adaf084bebe003452ba'
    assert component['os_abi'] == ['ipados-17.7.11-21H461'] and not component['dependencies']
    source = fw / component['path']
    assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() == component['revision']
    assert not subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'], text=True)
    out.mkdir(parents=True)
    stage = out / 'tree'
    for path in ('scripts', 'drivers', '.cache', 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT'):
        (stage / path).mkdir(parents=True)
    (stage / 'drivers/AppleKeyStoreState').symlink_to(source)
    (stage / '.cache/xnu-work').symlink_to(tree / '.cache/xnu-work')
    shutil.copyfile(fw / 'components.toml', stage / 'components.toml')
    shutil.copyfile(fw / 'scripts/build-arm-driver.py', stage / 'scripts/build-arm-driver.py')
    recipe_path = Path('build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json')
    recipe_bytes = (tree / recipe_path).read_bytes()
    recipe = json.loads(recipe_bytes.decode().strip().rstrip(','))
    # Redirect only compilation sidecars; the canonical builder keeps ABI flags/includes.
    for i, arg in enumerate(recipe['arguments'][:-1]):
        if arg in ('-MF', '-MJ'):
            recipe['arguments'][i + 1] = str(out / ('component' + ('.d' if arg == '-MF' else '.json')))
    (stage / recipe_path).write_text(json.dumps(recipe))
    command = ['python3.14', str(stage / 'scripts/build-arm-driver.py'), 'AppleKeyStoreState']
    with (out / 'component-build.log').open('w') as log:
        subprocess.run(command, cwd=stage, stdout=log, stderr=subprocess.STDOUT, check=True)
    component_out = stage / 'build/apple-key-store-state'
    original = component_out / 'NativeKeyStoreEvents.o'
    late = out / 'NativeKeyStoreEvents.late.o'
    subprocess.run(['llvm-objcopy', '--remove-section=__DATA,__mod_init_func',
                    '--globalize-symbol=__GLOBAL__sub_I_NativeKeyStoreEvents.cpp', str(original), str(late)], check=True)
    board = DEVICE / 'package/T970Display/KeyStoreRegistration.cpp'
    obj = out / 'KeyStoreRegistration.o'
    args, i, cmd = recipe['arguments'], 0, []
    while i < len(args):
        value = args[i]
        if value == recipe['file']:
            cmd.append(str(board))
        elif value == '-o':
            cmd += ['-o', str(obj)]
            i += 1
        elif value in ('-MF', '-MJ'):
            i += 1
        elif value == '-Xclang' and args[i + 1].startswith('-W'):
            i += 1
        elif value not in ('-MD', '-MP') and not value.startswith('-W'):
            cmd.append(value)
        i += 1
    cmd += ['-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter', '-Wno-c99-designator',
            '-Wno-reorder-init-list', '-Wno-deprecated-enum-enum-conversion',
            '-Wno-unnecessary-virtual-specifier', '-Wno-missing-include-dirs',
            '-I', str(tree / '.cache/xnu-work/osfmk')]
    (out / 'board-command.json').write_text(json.dumps(cmd, indent=2) + '\n')
    with (out / 'board-build.log').open('w') as log:
        subprocess.run(cmd, cwd=recipe['directory'], stdout=log, stderr=subprocess.STDOUT, check=True)
    undef, defined = set(), set()
    for o in (late, obj):
        undef.update(subprocess.check_output(['xcrun', 'nm', '-u', str(o)], text=True).split())
        defined.update(line.split()[-1] for line in subprocess.check_output(['xcrun', 'nm', '-gU', str(o)], text=True).splitlines() if line.split())
    missing = {n for n in undef - defined if n.startswith(('_native_aks_', '_native_keyevents_', '__GLOBAL__sub_I_NativeKeyStoreEvents'))}
    assert not missing, sorted(missing)
    assert (tree / recipe_path).read_bytes() == recipe_bytes, 'Original compile recipe changed'
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(component=component['id'], revision=component['revision'], repository=component['repository'],
                  source_sha256=sha(source / 'NativeKeyStoreEvents.cpp'), canonical_builder_sha256=sha(stage / 'scripts/build-arm-driver.py'),
                  board_source_sha256=sha(board), component_object_sha256=sha(late), board_object_sha256=sha(obj),
                  compile_recipe_sha256=hashlib.sha256(recipe_bytes).hexdigest(), callbacks_resolved=True,
                  late_initializer=True, canonical_build_command=command, kernel_linked=False, runtime_verified=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: pinned AppleKeyStoreState and T970 RAM-only registration compiled')


if __name__ == '__main__':
    main()
