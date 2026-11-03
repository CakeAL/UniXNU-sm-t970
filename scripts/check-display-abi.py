#!/usr/bin/env python3
"""Audit the exact 21H461 Legacy dispatch and IOSurface getters before linking.

Read-only host qualification. Does not create or publish a display service.
Addresses follow the reviewed UniXNU-sheng/T733 21H461 bindings; both original
and current relocated candidate bytes are checked rather than trusting labels.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--framework', type=Path, required=True)
    p.add_argument('--original', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--layout', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    require(not a.output.exists(), 'Preserve previous audit outputs')
    sys.path.insert(0, str(a.framework.resolve() / 'kits/XnuPrelink'))
    from native_prelink import macho, backed_offset, exports
    original, candidate = a.original.read_bytes(), a.candidate.read_bytes()
    plan = json.loads(a.layout.read_text())
    sha = lambda b: hashlib.sha256(b).hexdigest()
    require(sha(original) == plan['original_sha256'] ==
            'f18b4df865405f2a287b84977d7aca745e056d656d9fc9df1662970ce2969de7',
            'Exact original iPad7,1 21H461 kernelcache required')
    require(sha(candidate) == plan['candidate_sha256'], 'Candidate/layout mismatch')
    om, cm = macho(original), macho(candidate)
    slide = plan['slide']
    reference_slide = -0x1000000

    def read(blob, image, va, n):
        at = backed_offset(image['segments'], va, n, len(blob))
        return blob[at:at+n]

    def both(reference, n):
        original_va = reference - reference_slide
        before = read(original, om, original_va, n)
        after = read(candidate, cm, original_va + slide, n)
        require(before == after, 'Original instructions changed at ' + hex(reference))
        return before

    pc = 0xfffffff0057865d8
    x, y, z = struct.unpack('<3I', both(pc, 12))
    require(x & 0x9f00001f == 0x90000008 and y & 0xffc003ff == 0x91000108
            and z == 0x91004108, 'Legacy constructor dispatch sequence')
    imm = ((x >> 5) & 0x7ffff) * 4 + ((x >> 29) & 3)
    if imm & (1 << 20):
        imm -= 1 << 21
    vp = (pc & ~4095) + (imm << 12) + ((y >> 10) & 4095) + 16
    ovp = vp - reference_slide
    methods = struct.unpack('<358Q', read(original, om, ovp, 358 * 8))
    relocated = struct.unpack('<358Q', read(candidate, cm, ovp + slide, 358 * 8))
    original_names = exports(original, om)
    native_names = {n: v for v, ns in exports(candidate, cm).items() for n in ns}
    rebound = []
    require(all(methods), 'Nonnull original dispatch')
    for i, (v, w) in enumerate(zip(methods, relocated)):
        if v + slide == w:
            continue
        require(any(native_names.get(n) == w for n in original_names.get(v, [])),
                'Unqualified native symbol rebound at slot ' + str(i))
        rebound.append(i)
    require(read(original, om, ovp + 358 * 8, 24) == bytes(24), 'Dispatch extent')
    names = {n: v for v, ns in exports(candidate, cm).items() for n in ns}
    pure = [i for i, v in enumerate(relocated) if v == names['___cxa_pure_virtual']]
    require(pure == [211, 213, 245, 246, 306, 307, 337, 338, 345], 'Abstract slots')
    getters = []
    for name, address, field, wide in [
        ('descriptor', 0xfffffff004b9ead0, 48, True),
        ('width', 0xfffffff004b9ebbc, 88, True),
        ('height', 0xfffffff004b9ebc4, 96, True),
        ('stride', 0xfffffff004b9ebd4, 104, True),
        ('allocation', 0xfffffff004b9ebfc, 144, True),
        ('format', 0xfffffff004b9ebac, 128, False),
        ('planes', 0xfffffff004b9ebf4, 152, False),
    ]:
        load = (0xf9400000 if wide else 0xb9400000) | ((field // (8 if wide else 4)) << 10)
        require(both(address, 8) == struct.pack('<2I', load, 0xd65f03c0),
                'Exact IOSurface getter ' + name)
        getters.append(dict(name=name, address=hex(address-reference_slide+slide)))
    family = 'com.apple.iokit.IOMobileGraphicsFamily'
    ext = next(e for e in plan['extents'] if e['module'] == family and e['segment'] == '__TEXT_EXEC')
    digest = sha(read(candidate, cm, ext['va'], ext['size']))
    require(digest == plan['original_executable_sha256'][family] ==
            '2e044ee68c1650397e1435234ca6459206262e4c7ed709cb7131c6f664f9bd9b',
            'Complete original graphics executable unchanged')
    result = dict(original_sha256=sha(original), candidate_sha256=sha(candidate),
                  layout_sha256=sha(a.layout.read_bytes()), slide=slide,
                  legacy_vptr=hex(ovp+slide), virtual_entries=358, abstract_slots=pure,
                  methods=[dict(slot=i, address=hex(v)) for i, v in enumerate(relocated)],
                  surface_getters=getters, native_symbol_rebound_slots=rebound, original_family_text_sha256=digest,
                  display_archive_built=False, runtime_display_verified=False)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: 358 relocated Legacy slots, nine abstract leaves, seven IOSurface getters, unchanged graphics text')


if __name__ == '__main__':
    main()
