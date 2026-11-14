#!/usr/bin/env python3
"""Build the in-repository DSP and wireless-baseline drivers into libT970Dsp.a.

The sources live in package/T970Dsp and are compiled with the flags recorded for
the XNU objects they replace, so the archive links into the prelinked kernel the
same way as the other board packages.
"""
import argparse
import json
from pathlib import Path
import subprocess

SOURCES = (
    'QcomMdt.c', 'QcomSmem.c', 'QcomSmp2p.c', 'QcomGlink.c', 'QcomQmp.c',
    'QcomRpmh.c', 'T970Apr.c', 'T970Ssc.c',
    'T970Audio.cpp', 'T970AudioService.cpp', 'T970Adsp.cpp', 'T970Sensors.cpp',
)


def command_for(recipe, source, obj, extra_includes):
    arguments = iter(recipe['arguments'])
    command = []
    for value in arguments:
        if value == recipe['file']:
            command.append(str(source))
        elif value in ('-o', '-MF', '-MT', '-MJ'):
            next(arguments)
            if value == '-o':
                command += ['-o', str(obj)]
        elif value == '-Xclang':
            following = next(arguments)
            if not following.startswith('-W'):
                command += [value, following]
        elif value not in ('-MD', '-MP') and not value.startswith('-W'):
            command.append(value)
    command += ['-I', str(extra_includes), '-mgeneral-regs-only']
    return command


def build(tree, package, out):
    build_dir = tree / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837'
    recipes = {'.c': build_dir / 'bsd/DEVELOPMENT/kern_exec.o.json',
               '.cpp': build_dir / 'iokit/DEVELOPMENT/IOPlatformExpert.cpo.json'}
    tree = tree.resolve()
    xnu = tree / ".cache/xnu-work"
    objects = []
    for name in SOURCES:
        source = package / name
        obj = out / (source.stem + '.o')
        recipe = json.loads(recipes[source.suffix].read_text().strip().rstrip(','))
        command = command_for(recipe, source, obj, xnu / 'osfmk')
        subprocess.run(command, cwd=recipe['directory'], check=True)
        if name == 'T970AudioService.cpp':
            late = obj.with_suffix('.late.o')
            subprocess.run(['/opt/homebrew/opt/llvm/bin/llvm-objcopy',
                            '--remove-section=__DATA,__mod_init_func',
                            '--globalize-symbol=__GLOBAL__sub_I_T970AudioService.cpp',
                            obj, late], check=True)
            obj = late
        objects.append(obj)
    archive = out / 'libT970Dsp.a'
    subprocess.run(['/opt/homebrew/opt/llvm/bin/llvm-ar', 'rcs', archive, *map(str, objects)], check=True)
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, required=True, help='XNU build tree of the dual-system output')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    package = Path(__file__).resolve().parent.parent / 'package/T970Dsp'
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    archive = build(args.tree, package, args.output)
    print('PASS', archive)


if __name__ == '__main__':
    main()
