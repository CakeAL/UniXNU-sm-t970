#!/usr/bin/env python3
"""Replace the two board display members and prelink the v42 uninterruptible-wait kernel."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

device = Path(__file__).resolve().parents[3]
os.chdir(device)
out = Path('out/data-bringup')
work = out / 'sm-t970/ipados-17.7.11-21H461/sm-t970_data'
live = work / 'tree/build/native-legacy-display'
obj = out / 'ls-peer-v42-object'
backup = out / 'pre-ls-peer-v42'
if not obj.exists():
    subprocess.run(['python3.14', 'scripts/build-display-registration.py', '--tree', str(work / 'tree'),
                    '--gop-object', str(out / 'display-object-cf3b429/NativeLegacyDisplay.o'),
                    '--output', str(obj)], check=True)
ui = out / 'ls-peer-v42-sampler'
subprocess.run(['python3.14', 'scripts/build-ui-wait-snapshot.py', '--tree', str(work / 'tree'),
                '--output', str(ui)], check=True)
backup.mkdir()
archive = 'libNativeLegacyDisplay.late.a'
report_name = 'build-report.json'
for name in (archive, report_name):
    shutil.copy2(live / name, backup / name)
for name in ('kernel.macho', 'kernel.json'):
    shutil.copy2(work / 'kernel' / name, backup / name)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


before = json.loads((backup / report_name).read_text())
compiled = json.loads((obj / 'report.json').read_text())
source = device / 'package/T970Display/DisplayRegistration.cpp'
assert sha(source) == compiled['source_sha256']
assert sha(backup / archive) == before['archive_sha256']
assert sha(obj / 'DisplayRegistration.o') == compiled['object_sha256']


def ar(option, path, *args):
    return subprocess.check_output(['xcrun', 'ar', option, str(path), *args])


members = ar('-t', backup / archive).decode().splitlines()
replacements = {p.name: p for p in (obj / 'DisplayRegistration.o', ui / 'UiWaitSnapshot.o')}
assert all(members.count(name) == 1 for name in replacements)
shutil.copy2(backup / archive, obj / archive)
ar('-r', obj / archive, *(str(path) for path in replacements.values()))
assert members == ar('-t', obj / archive).decode().splitlines()
for member in members:
    if member.startswith('__.SYMDEF'):
        continue
    expected = (replacements[member].read_bytes() if member in replacements
                else ar('-p', backup / archive, member))
    assert ar('-p', obj / archive, member) == expected
before.update(archive_sha256=sha(obj / archive), registration_object_sha256=compiled['object_sha256'])
before['source_sha256'][str(source)] = compiled['source_sha256']
sampler = json.loads((ui / 'report.json').read_text())
assert sha(ui / 'UiWaitSnapshot.o') == sampler['object_sha256']
before['source_sha256'][str(source.with_name('UiWaitSnapshot.c'))] = sampler['source_sha256']
(obj / report_name).write_text(json.dumps(before, indent=2) + '\n')
for name in (archive, report_name):
    shutil.copy2(obj / name, live / name)
env = dict(os.environ)
env['PATH'] = str(device / '.cache/bin') + ':/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:' + env['PATH']
command = ['python3.14', '../UniXNU/unixnu', 'build', 'kernel', '-D', '.', '--out', str(out),
           '--local-module', 'driver:ArmCpu=' + str(device / '.cache/armcpu-sgi-asm')]
with (out / 'ls-peer-v42-kernel.log').open('w') as log:
    subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)