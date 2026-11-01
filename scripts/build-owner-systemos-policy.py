#!/usr/bin/env python3
"""Sign and fully verify the original SystemOS raw volume without expanding it.

Mirror of the framework's build-owner-os-policy.py for the Cryptex1,SystemOS
member. The member is an uncompressed raw image, so its compressed digest and
its image digest are the same value.
"""
import ctypes
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
FW = ROOT.parent / 'UniXNU'
source = FW / '.cache/firmware/target-volumes/044-76034-038.dmg'
volume = FW / 'build/verified-root-systemos-mount'
out = FW / 'build/verified-root-systemos'
expected_sha256 = 'b4908cde41d23e6bc05e6af51a2c9eeb00cf0f863a6a18b1600c96a3fd70414f'
expected_bytes = 3303014400

if not source.is_file() or source.stat().st_size != expected_bytes:
    raise SystemExit('Require the exact original SystemOS member')
digest = hashlib.sha256(source.read_bytes()).hexdigest()
if digest != expected_sha256:
    raise SystemExit('The SystemOS member digest differs')

images = plistlib.loads(subprocess.check_output(['hdiutil', 'info', '-plist']))['images']
found = [i for i in images if Path(i['image-path']).resolve() == source.resolve() and i.get('writeable') is False]
if len(found) != 1:
    raise SystemExit('Require one existing exact read-only image attachment')
entities = found[0]['system-entities']
volume_info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', volume]))
volume_device = volume_info.get('DeviceNode', '')
whole = [volume_device[:volume_device.rfind('s')] if 's' in volume_device else volume_device]
if len(whole) != 1 or not whole[0]:
    raise SystemExit('Require one actual whole virtual media mapping')
info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', whole[0]]))
if (info.get('BusProtocol') != 'Disk Image' or info.get('Writable') is not False or
        info.get('DeviceNode') != whole[0] or info.get('TotalSize') != expected_bytes or
        volume_info.get('Writable') is not False or
        volume_info.get('DeviceNode') not in [e['dev-entry'] for e in entities]):
    raise SystemExit('Only the actual matching read-only Disk Image/SystemOS volume is accepted')
expected_uuid = uuid.UUID(volume_info['VolumeUUID'])
disk = Path('/dev/r' + Path(whole[0]).name)

spec = importlib.util.spec_from_file_location('verified_manifest', FW / 'kits/VerifiedRoot/tools/manifest.py')
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)
keys = FW / 'build/verified-root-host/keys'
with disk.open('rb', buffering=1024 * 1024) as stream:
    record = manifest.make(stream, info['TotalSize'], keys / 'owner.pem', keys / 'owner-public.pem', expected_uuid, 1, out)


class View(ctypes.Structure):
    _fields_ = [('hashes', ctypes.c_void_p), ('image_bytes', ctypes.c_uint64), ('block_count', ctypes.c_uint64),
                ('generation', ctypes.c_uint64), ('volume_uuid', ctypes.c_uint8 * 16), ('image_sha256', ctypes.c_uint8 * 32)]


native = ctypes.CDLL(str(FW / 'build/verified-root-host/verified-root.dylib'))
native.vr_host_open.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_uint64, ctypes.POINTER(View)]
native.vr_host_block.argtypes = [ctypes.POINTER(View), ctypes.c_uint64, ctypes.c_void_p, ctypes.c_size_t]
encoded = ctypes.create_string_buffer((out / 'manifest.bin').read_bytes())
anchor = ctypes.create_string_buffer((out / 'trusted-key.bin').read_bytes())
view = View()
if native.vr_host_open(encoded, len(encoded) - 1, anchor, 1, ctypes.byref(view)) or bytes(view.volume_uuid) != expected_uuid.bytes:
    raise SystemExit('Real C signature/volume authentication failed')
if view.block_count != 806400 or view.image_bytes != expected_bytes:
    raise SystemExit('Unexpected SystemOS block geometry')
complete = hashlib.sha256()
indices = [0, 1, view.block_count // 2, view.block_count - 1]
samples, lengths = [], []
with disk.open('rb', buffering=1024 * 1024) as stream:
    for index in range(view.block_count):
        block = stream.read(min(4096, view.image_bytes - index * 4096))
        if native.vr_host_block(ctypes.byref(view), index, block, len(block)) != 0:
            raise SystemExit('Actual C block verification failed at ' + str(index))
        complete.update(block)
        if index in indices:
            samples.append(block.ljust(4096, b'\0'))
            lengths.append(len(block))
    if stream.read(1):
        raise SystemExit('Virtual media exceeded its authenticated exact bounds')
if complete.digest() != bytes(view.image_sha256) or complete.hexdigest() != record['image_sha256']:
    raise SystemExit('Actual complete original SystemOS digest differs')
(out / 'original-samples.bin').write_bytes(b''.join(samples))
report = dict(image_bytes=view.image_bytes, blocks_verified=view.block_count, image_sha256=complete.hexdigest(),
              volume_uuid=str(expected_uuid).upper(), generation=view.generation,
              source_compressed_sha256=digest, source_format='RAW',
              host_bus_protocol='Disk Image', host_media_writable=False,
              trusted_key_sha256=record['trusted_key_sha256'], actual_sample_indices=indices,
              actual_sample_lengths=lengths, real_c_signature_and_block_verification=True,
              original_image_modified=False, host_only=True, boot_root_authenticated=False,
              qemu_tested=False, hardware_tested=False)
(out / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
print('PASS: original SystemOS signature and every', view.block_count, 'block verified by real C/RSA; no expanded image')
