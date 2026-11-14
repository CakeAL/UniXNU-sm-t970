#!/usr/bin/env python3
"""Generate local A650 firmware C from hash-matched T970 inputs."""
import argparse
import hashlib
from pathlib import Path
import struct


FIRMWARE = {
    'a650_gmu.bin': 'df79fa8482fcc7587bb239b9c9e2b24bce4729893b990fe3f82b30da8175b01c',
    'a650_sqe.fw': 'b4c27420fd6a5c6b511b254cc0fad8cdd40eea38ceb3418f895a1084f4460487',
    'a650_zap.b00': 'ec9b9d5a67456384809624b14a00d15d36297e5f2e75728504cd872bc95e0947',
    'a650_zap.b02': 'a415e5452fa8f597670a6e51010e97bfabca7d20fbce8044caed64d9d5873113',
}
# The stock capture and the reference use two distinct signed MDT/b01 pairs.
ZAP_PAIRS = (
    ('56ed13adffa9af0bd8a39eefe025318312b734c3741badf1adc8f5a91ae0bb02',
     '83cd3f4e3886a5e509173a22c0de0009a7c73f956e636c7d792ca7feac49a68b'),
    ('d6dcaa62d18bfe6c93b787d0976cd0154fae9cb88f61f6c7dee0096eac9129e3',
     'b18f249c9c36495daf6adfa21870beb6339586932ae04f03ef8ddf7fb99583a0'),
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_pinned(directory, name):
    data = (directory / name).read_bytes()
    if digest(data) != FIRMWARE[name]:
        raise ValueError(f'{name}: SHA-256 does not match the T970 inventory')
    return data


def zap_image(directory):
    mdt = (directory / 'a650_zap.mdt').read_bytes()
    signed_hash = (directory / 'a650_zap.b01').read_bytes()
    if (digest(mdt), digest(signed_hash)) not in ZAP_PAIRS:
        raise ValueError('ZAP MDT and b01 must match one recorded T970 pair')
    parts = (read_pinned(directory, 'a650_zap.b00'), signed_hash,
             read_pinned(directory, 'a650_zap.b02'))
    if mdt[:6] != b'\x7fELF\x01\x01':
        raise ValueError('ZAP metadata is not little-endian ELF32')
    phoff, = struct.unpack_from('<I', mdt, 28)
    size, count = struct.unpack_from('<HH', mdt, 42)
    if size != 32 or not len(parts) <= count <= 16 or phoff + size * count > len(mdt):
        raise ValueError('Unexpected ZAP program header table')
    image = bytearray()
    for index in range(count):
        _, offset, _, _, length, _, _, _ = struct.unpack_from('<8I', mdt, phoff + index * size)
        if index >= len(parts):
            if length:
                raise ValueError(f'Missing ZAP segment {index}')
            continue
        part = parts[index]
        # Qualcomm's header-only segment can declare zero file bytes.
        if index == 0 and not length:
            offset, length = 0, len(part)
        if length != len(part) or offset > 1 << 20 or offset + length > 1 << 20:
            raise ValueError(f'Unexpected ZAP segment {index} extent')
        if offset + length > len(image):
            image.extend(bytes(offset + length - len(image)))
        image[offset:offset + length] = part
    if image[:len(parts[0])] != parts[0]:
        raise ValueError('ZAP ELF header was overwritten during assembly')
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--host-check', action='store_true', help='generate GMU and SQE only for compile verification')
    args = parser.parse_args()
    try:
        images = {'gmu': read_pinned(args.inputs, 'a650_gmu.bin'),
                  'sqe': read_pinned(args.inputs, 'a650_sqe.fw')}
        if not args.host_check:
            images['zap'] = zap_image(args.inputs)
        with args.output.open('x') as output:
            output.write('#include <stdint.h>\n')
            for name, data in images.items():
                output.write(f'const uint8_t native_gpu_{name}_firmware[] = {{\n')
                for offset in range(0, len(data), 24):
                    output.write(','.join(str(byte) for byte in data[offset:offset + 24]) + ',\n')
                output.write(f'}};\nconst uint32_t native_gpu_{name}_firmware_size = {len(data)};\n')
    except (OSError, ValueError, struct.error) as error:
        parser.exit(1, f'{error}\n')


if __name__ == '__main__':
    main()
