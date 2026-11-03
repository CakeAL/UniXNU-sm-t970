#!/usr/bin/env python3
"""Pack and independently check the key-state diagnostic; does not flash."""
from pathlib import Path
import json
import os
import subprocess

device = Path(__file__).resolve().parents[3]
os.chdir(device)
out = device / 'out/data-bringup'
for name in ('key-state.img', 'key-state-verified', 'key-state-cpu8', 'key-state-image-build.log'):
    assert not (out / name).exists(), 'Preserve earlier outputs: ' + name
args = json.loads((device / 'evidence/display/ui-call-v9/preparation.json').read_text())['args'].split()
exclude = {'t970-novc','sheng-pmgr=2','t970-ufs-publish=1','-v','cpus=8',
           'sheng-smp=1','armcpu-self-ipi=1','armcpu-spi-ipi=0'}
env = dict(os.environ)
env['PATH'] = str(device / '.cache/bin') + ':/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:' + env['PATH']
common = ['-D','.', '--out','out/data-bringup','--local-module',
          'driver:ArmCpu=' + str(device / '.cache/armcpu-sgi-asm')]
work = 'out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data'
cmd = ['python3.14','../UniXNU/unixnu','build','payload'] + common + [
    '--data-ramdisk','out/step7/data-seed-512/data-512.dbr']
for arg in args + ['offline-key-events=1','sheng-aks=1']:
    if arg not in exclude:
        cmd += ['--kernel-arg',arg]
commands = [cmd,
    ['python3.14','../UniXNU/unixnu','bootimg'] + common + [
        '--uefi','.cache/uefi-source/Mu-Silicium','--fd','out/step7/ufs-readonly-inputs/SILICIUM_UEFI.fd',
        '--dtb','out/firmware-inputs/firmware.dtb','--ramdisk',work+'/payload/payload.img',
        '--output','out/data-bringup/key-state.img'],
    ['python3.14','scripts/check-data-payload.py','--work',work,'--boot','out/data-bringup/key-state.img',
        '--seed','out/step7/data-seed-512/data-512.dbr','--watchdog-policy','--smp-observer',
        '--publish-reset-state','--display-probe','--cpu-present','--runtime-report-seconds','60',
        '--cache-trace','--ui-exit-probe','--ui-spawn-calls','--key-state',
        '--output','out/data-bringup/key-state-verified'],
    ['python3.14','scripts/prepare-smp.py','--cpus','8','--armcpu-source','.cache/armcpu-sgi-asm',
        '--base','out/data-bringup/key-state-verified/boot-partition.img',
        '--base-validation','out/data-bringup/key-state-verified/validation.json',
        '--hardware-dtb',work+'/device-tree/hardware.dtb','--output','out/data-bringup/key-state-cpu8']]
(out / 'key-state-image-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
with (out / 'key-state-image-build.log').open('w') as log:
    for command in commands:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
print('PASS: key-state target60 image and eight-core packing checked')
