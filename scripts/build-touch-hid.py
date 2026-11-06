#!/usr/bin/env python3
"""Compile the T970 digitizer and bind it to the original iPadOS 21H461 HID ABI."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

DEVICE = Path(__file__).resolve().parents[1]
SOURCE = DEVICE / 'package/T970Touch/TouchHid.cpp'
V75 = DEVICE / 'out/data-bringup/touch-events-v75-build/kernel.macho'
SLIDE = -0x1000000
HID = 'com.apple.iokit.IOHIDFamily'
HID_HASH = '7e4c5104814f2e773d5be13d092dec53ee44ba5a61a81264b229780406e86b72'
VPTR = 0xfffffff005d045c0
CONSTRUCTOR = 0xfffffff004ad94f8
SLOTS = 207


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_hid(path, prelink):
    data = path.read_bytes()
    plan = json.loads(path.with_suffix('.json').read_text())
    if plan['candidate_sha256'] != digest(data) or plan['slide'] != SLIDE:
        raise ValueError('Expected a prelinked 21H461 candidate with the reviewed slide')
    image = prelink.macho(data)

    def read(address, size):
        offset = prelink.backed_offset(image['segments'], address, size, len(data))
        return data[offset:offset + size]

    text, = [e for e in plan['extents'] if e['module'] == HID and e['segment'] == '__TEXT_EXEC']
    if digest(read(text['va'], text['size'])) != HID_HASH:
        raise ValueError('Original HID instructions changed')
    ctor = 'fd7bbfa9fd0300912bd90094489100f008011791080000f9fd7bc1a8c0035fd6'
    if read(CONSTRUCTOR, 32) != bytes.fromhex(ctor):
        raise ValueError('Original IOHIDDevice constructor changed')
    if read(VPTR + SLOTS * 8, 24) != bytes(24):
        raise ValueError('Original IOHIDDevice vtable terminator changed')
    return struct.unpack(f'<{SLOTS}Q', read(VPTR, SLOTS * 8))


def object_bindings(path, methods, prelink):
    data = path.read_bytes()
    image = prelink.macho(data)
    table, = [offset for command, offset, _ in image['commands'] if command == 2]
    start, count, strings, _ = struct.unpack_from('<4I', data, table + 8)
    symbols = []
    for index in range(count):
        name, kind, _, _, address = struct.unpack_from('<IBBHQ', data, start + index * 16)
        end = data.index(b'\0', strings + name)
        symbols.append((data[strings + name:end].decode(), kind, address))

    vtable, = [address for name, _, address in symbols if name == '__ZTV12T970TouchHid']
    section, = [sec for seg in image['segments'] for sec in seg['sections']
                if sec['va'] <= vtable < sec['va'] + sec['size']]
    start, count = struct.unpack_from('<2I', data, section['command_offset'] + 56)
    relocations = {}
    for index in range(count):
        offset, bits = struct.unpack_from('<2I', data, start + index * 8)
        if bits >> 27 & 1 and bits >> 28 == 0 and bits >> 25 & 3 == 3:
            relocations[section['va'] + offset] = symbols[bits & 0xffffff][0]

    bindings = {
        '__ZN11IOHIDDeviceC2EPK11OSMetaClass': CONSTRUCTOR,
        '__ZN11IOHIDDeviceD2Ev': 0xfffffff004ad9518,
        '__ZN11IOHIDDevice10gMetaClassE': 0xfffffff006ae6fa0,
        '__ZTV11IOHIDDevice': VPTR - 16,
    }
    owned = []
    for slot, address in enumerate(methods):
        name = relocations[vtable + 16 + slot * 8]
        if name.startswith(('__ZN12T970TouchHid', '__ZNK12T970TouchHid')):
            owned.append(slot)
        elif '11IOHIDDevice' in name:
            if name in bindings and bindings[name] != address:
                raise ValueError('Conflicting HID symbol binding: ' + name)
            bindings[name] = address
    undefined = {name for name, kind, _ in symbols if kind == 1 and '11IOHIDDevice' in name}
    if undefined != set(bindings) or owned != [0, 1, 7, 14, 86, 111, 171, 173, 180]:
        raise ValueError(f'Unexpected IOHIDDevice imports or overrides: {undefined ^ set(bindings)}, {owned}')
    if vtable + 16 + SLOTS * 8 in relocations:
        raise ValueError('Unexpected additional IOHIDDevice slot')
    return bindings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registration', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--verify', type=Path, help='Verify bindings against the newly linked kernel')
    args = parser.parse_args()
    out = args.output.resolve()
    sys.path.insert(0, str(DEVICE.parent / 'UniXNU/kits/XnuPrelink'))
    import native_prelink as prelink

    obj = out / 'TouchHid.o'
    if args.verify:
        report = json.loads((out / 'bindings.json').read_text())
        actual = object_bindings(obj, checked_hid(args.verify, prelink), prelink)
        if report['bindings'] != actual:
            raise ValueError('Original HID binding addresses changed during link')
        print('PASS: linked 21H461 HID bindings')
        return

    out.mkdir()
    command = json.loads((args.registration / 'command.json').read_text())
    command[command.index(str(DEVICE / 'package/T970Display/DisplayRegistration.cpp'))] = str(SOURCE)
    command[command.index('-o') + 1] = str(obj)
    tree = DEVICE / 'out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree'
    recipe = tree / 'build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/iokit/DEVELOPMENT/IOPlatformExpert.cpo.json'
    cwd = json.loads(recipe.read_text().strip().rstrip(','))['directory']
    subprocess.run(command, cwd=cwd, check=True)
    bindings = object_bindings(obj, checked_hid(V75, prelink), prelink)
    assembly = out / 'touch-hid-bindings.S'
    assembly.write_text(''.join(f'.globl {name}\n.set {name}, {address:#x}\n'
                                for name, address in sorted(bindings.items())))
    subprocess.run(['xcrun', 'clang', '-target', 'arm64-apple-ios17.0', '-c',
                    str(assembly), '-o', str(out / 'touch-hid-bindings.o')], check=True)
    llvm = Path(subprocess.check_output(['brew', '--prefix', 'llvm'], text=True).strip()) / 'bin'
    subprocess.run([str(llvm / 'llvm-objcopy'), '--remove-section=__DATA,__mod_init_func',
                    '--globalize-symbol=__GLOBAL__sub_I_TouchHid.cpp', str(obj),
                    str(out / 'TouchHid.late.o')], check=True)
    (out / 'bindings.json').write_text(json.dumps(dict(bindings=bindings, original_text_sha256=HID_HASH),
                                                  indent=2) + '\n')


if __name__ == '__main__':
    main()
