#!/usr/bin/env python3
"""Compile the board touch core with the kernel's own C++ recipe record."""
import argparse, json, pathlib, subprocess

DEVICE = pathlib.Path(__file__).resolve().parent.parent
SOURCE = {'T970FtsTouch': 'package/T970Touch/T970FtsTouch.cpp',
          'TouchBridge': 'package/T970Touch/TouchBridge.cpp',
          'DisplayRegistration': 'package/T970Display/DisplayRegistration.cpp'}


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--tree', type=pathlib.Path, required=True)
    a.add_argument('--output', type=pathlib.Path, required=True)
    a.add_argument('--units', nargs='*', default=list(SOURCE))
    o = a.parse_args()
    out = o.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    record = o.tree / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOCatalogue.cpo.json'
    raw = record.read_text()
    rec, _ = json.JSONDecoder().raw_decode(raw)
    argv = rec['arguments']
    for unit in o.units:
        cmd, i = [], 0
        while i < len(argv):
            v = argv[i]
            if v == rec['file']:
                cmd.append(str(DEVICE / SOURCE[unit]))
            elif v == '-o':
                cmd += ['-o', str(out / (unit + '.o'))]
                i += 1
            elif v.startswith('-W') or v in ('-MD', '-MP'):
                pass
            elif v == '-Xclang':
                i += 1
            else:
                cmd.append(v)
            i += 1
        if unit == 'DisplayRegistration':
            cmd += ['-DT970_PERIPHERAL_RPMH=1', '-DT970_DSP=1']
        cmd += ['-I', str(DEVICE / 'package/T970Power'),
                '-I', str(DEVICE / 'package/T970Display'),
                '-I', str(DEVICE / 'package/T970Touch'),
                '-Wno-unused-parameter', '-Wno-sign-compare', '-Wno-deprecated-volatile']
        subprocess.run(cmd, cwd=rec['directory'], check=True)
        print('compiled', unit)


if __name__ == '__main__':
    main()
