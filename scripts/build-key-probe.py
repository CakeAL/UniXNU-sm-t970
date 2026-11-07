#!/usr/bin/env python3
"""Compile the opt-in PMIC observer using the audited IOKit compile recipe."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

DEVICE = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registration', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = DEVICE / 'package/T970Input/KeyProbe.cpp'
    obj = out / 'KeyProbe.o'
    cmd = json.loads((a.registration / 'command.json').read_text())
    cmd[cmd.index(str(DEVICE / 'package/T970Display/DisplayRegistration.cpp'))] = str(source)
    cmd[cmd.index('-o') + 1] = str(obj)
    recipe = DEVICE / 'out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json'
    cwd = json.loads(recipe.read_text().strip().rstrip(','))['directory']
    (out / 'command.json').write_text(json.dumps(cmd, indent=2) + '\n')
    with (out / 'compile.log').open('w') as log:
        subprocess.run(cmd, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, check=True)
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = dict(source_sha256=sha(source), core_sha256=sha(source.with_name('KeyProbeCore.h')),
                  object_sha256=sha(obj), command_sha256=sha(out / 'command.json'),
                  pmic_writes=False, observer_commands=True, hid_enabled_by_default=False, hid_boot_arg="t970-keys-hid=1", runtime_verified=False)
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: T970 PMIC observer compiled')


if __name__ == '__main__':
    main()
