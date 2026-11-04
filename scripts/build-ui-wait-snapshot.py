#!/usr/bin/env python3
"""Compile the bounded UI register sampler in the Mach-private header universe."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

device = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--tree', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
tree, out = a.tree.resolve(), a.output.resolve()
assert not out.exists(), 'Preserve previous outputs'
out.mkdir(parents=True)
recipe = tree / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/osfmk/DEVELOPMENT/clock.o.json'
raw = recipe.read_bytes()
r = json.loads(raw.decode().strip().rstrip(','))
assert 'MACH_KERNEL_PRIVATE' in r['arguments'], 'Require real Mach-private compile flags'
source = device / 'package/T970Display/UiWaitSnapshot.c'
obj = out / 'UiWaitSnapshot.o'
args, cmd, i = r['arguments'], [], 0
while i < len(args):
    arg = args[i]
    if arg == r['file']:
        cmd.append(str(source))
    elif arg == '-o':
        cmd += ['-o', str(obj)]
        i += 1
    elif arg in ('-MF', '-MJ'):
        i += 1
    elif arg not in ('-MD', '-MP'):
        cmd.append(arg)
    i += 1
(out / 'command.json').write_text(json.dumps(cmd, indent=2) + '\n')
with (out / 'compile.log').open('w') as log:
    subprocess.run(cmd, cwd=r['directory'], stdout=log, stderr=subprocess.STDOUT, check=True)
assert recipe.read_bytes() == raw
sha = lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
(out / 'report.json').write_text(json.dumps(dict(source_sha256=sha(source),object_sha256=sha(obj),
    compile_recipe_sha256=hashlib.sha256(raw).hexdigest(),mach_private_recipe=True,
    reads_user_memory="opt-in t970-ui-stack=1/2/3/4/5/7/8, isolated worker",suspends_tasks=False,
    stack_frames_per_selected_thread="mode1/7:8; mode2/3/4/5/8:16",stack_selection="mode1: first UI threads; mode2: other BB threads; mode3: Gestalt helper first2; mode4: helper threads5-8; mode5: all UI/helper first8; mode6: queue-only two samples 500ms apart, no user reads; mode7: SpringBoard and lsd first4 each; mode8: lsd threads5-8",report_wait_deadlines=40,report_wait_interval_ms=100,thread_limit_per_process=8,runtime_verified=False),indent=2)+'\n')
print('PASS: bounded saved-register sampler compiled against current Mach-private ABI')
