#!/usr/bin/env python3
"""Pack and independently check the key-state diagnostic; does not flash."""
from pathlib import Path
import json
import os
import subprocess

device = Path(__file__).resolve().parents[3]
os.chdir(device)
out = device / 'out/data-bringup'
for name in ('ui-queue-progress-v1.img', 'ui-queue-progress-verified-v1', 'ui-queue-progress-cpu8-v1', 'ui-queue-progress-image-build-v1.log'):
    assert not (out / name).exists(), 'Preserve earlier outputs: ' + name
args = json.loads((device / 'evidence/display/ui-call-v9/preparation.json').read_text())['args'].split()
args = ['t970-runtime-report=90' if arg=='t970-runtime-report=60' else arg for arg in args]
exclude = {'t970-novc','sheng-pmgr=2','t970-ufs-publish=1','-v','cpus=8',
           'sheng-smp=1','armcpu-self-ipi=1','armcpu-spi-ipi=0'}
env = dict(os.environ)
env['PATH'] = str(device / '.cache/bin') + ':/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:' + env['PATH']
common = ['-D','.', '--out','out/data-bringup','--local-module',
          'driver:ArmCpu=' + str(device / '.cache/armcpu-sgi-asm')]
work = 'out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data'
cmd = ['python3.14','../UniXNU/unixnu','build','payload'] + common + [
    '--data-ramdisk','out/step7/data-seed-512/data-512.dbr']
for arg in args + ['offline-key-events=1','sheng-aks=1','t970-ui-wait=1','t970-ui-stack=6']:
    if arg not in exclude:
        cmd += ['--kernel-arg',arg]
commands = [cmd,
    ['python3.14','../UniXNU/unixnu','bootimg'] + common + [
        '--uefi','.cache/uefi-source/Mu-Silicium','--fd','out/step7/ufs-readonly-inputs/SILICIUM_UEFI.fd',
        '--dtb','out/firmware-inputs/firmware.dtb','--ramdisk',work+'/payload/payload.img',
        '--output','out/data-bringup/ui-queue-progress-v1.img'],
    ['python3.14','scripts/check-data-payload.py','--work',work,'--boot','out/data-bringup/ui-queue-progress-v1.img',
        '--seed','out/step7/data-seed-512/data-512.dbr','--watchdog-policy','--smp-observer',
        '--publish-reset-state','--display-probe','--cpu-present','--runtime-report-seconds','90',
        '--cache-trace','--ui-exit-probe','--ui-spawn-calls','--key-state','--ui-wait','--ui-stack','--ui-stack-mode','6','--workqueue-detail',
        '--output','out/data-bringup/ui-queue-progress-verified-v1'],
    ['python3.14','scripts/prepare-smp.py','--cpus','8','--armcpu-source','.cache/armcpu-sgi-asm',
        '--base','out/data-bringup/ui-queue-progress-verified-v1/boot-partition.img',
        '--base-validation','out/data-bringup/ui-queue-progress-verified-v1/validation.json',
        '--hardware-dtb',work+'/device-tree/hardware.dtb','--output','out/data-bringup/ui-queue-progress-cpu8-v1']]
(out / 'ui-queue-progress-image-commands-v1.json').write_text(json.dumps(commands,indent=2)+'\n')
with (out / 'ui-queue-progress-image-build-v1.log').open('w') as log:
    for command in commands:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)


# Reuse the reviewed ADT walker; only the explicit512MiB request becomes768MiB.
import hashlib, importlib.util, struct
spec = importlib.util.spec_from_file_location('owned',device/'scripts/prepare-owned-window.py')
owned = importlib.util.module_from_spec(spec);spec.loader.exec_module(owned)
spec = importlib.util.spec_from_file_location('platform_check',device/'scripts/check-platform.py')
platform = importlib.util.module_from_spec(spec);spec.loader.exec_module(platform)
base = out/'ui-queue-progress-cpu8-v1'
raw = (base/'boot-partition.img').read_bytes()
prep = json.loads((base/'preparation.json').read_text())
sha = lambda data:hashlib.sha256(data).hexdigest()
assert sha(raw)==prep['boot_sha256'] and prep['target_wait_seconds']==90
final = out/'ui-queue-progress-memory768-v1';assert not final.exists();final.mkdir()
ks,rs = struct.unpack_from('<I',raw,8)[0],struct.unpack_from('<I',raw,16)[0]
page,version = struct.unpack_from('<II',raw,36);assert (page,version)==(4096,2)
start = page+(ks+page-1)//page*page
payload = final/'payload.img';payload.write_bytes(raw[start:start+rs])
def get(name):
    return subprocess.check_output(['mtype','-i',str(payload),'::/EFI/UniXNU/'+name])
names = ['unixnu.toml']+['Payloads/'+n for n in ('kernel.macho','kernel.macho.adt','kernel.macho.trustcache','scratch-data.img')]
original = {n:get(n) for n in names}
adt = original['Payloads/kernel.macho.adt']
new = owned.replace_request(adt,0x30000000,expected_size=0x20000000)
before,after = platform.decode_adt(adt),platform.decode_adt(new)
before['/chosen']['darwinboot-memory-size']=struct.pack('<Q',0x30000000)
assert before==after
path = final/'kernel.macho.adt';path.write_bytes(new)
subprocess.run(['mcopy','-o','-i',str(payload),str(path),'::/EFI/UniXNU/Payloads/kernel.macho.adt'],check=True)
packed = bytearray(raw);packed[start:start+rs]=payload.read_bytes()
assert len(packed)==len(raw)==71303168 and packed[:start]==raw[:start] and packed[start+rs:]==raw[start+rs:]
image = final/'boot-partition.img';image.write_bytes(packed)
payload.write_bytes(image.read_bytes()[start:start+rs])
assert all(get(n)==(new if n.endswith('.adt') else b) for n,b in original.items())
prep.update(boot_sha256=sha(packed),base_512_boot_sha256=sha(raw),owned_bytes=0x30000000,
            adt_sha256=sha(new),only_owned_request_changed_after_smp=True,final_boot_fat_roundtrip=True,
            ui_wait_requested=True,hardware_result_pending=True,uploaded=False)
(final/'preparation.json').write_text(json.dumps(prep,indent=2)+'\n')
print('PASS: UI saved-register target90, eight CPUs,768MiB BOOT '+prep['boot_sha256'])
