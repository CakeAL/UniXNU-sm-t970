#!/usr/bin/env python3
"""Locate photographed PCs/LRs using the original arm64 cache and matching locals.

Cache layout: apple-oss-distributions/dyld@a571176, dyld_cache_format.h
blob83ef7357. Offsets verified by compiling offsetof against that header.
Lookup follows UniXNU/scripts/symbolicate-original-user-exception.py;
this tool accepts live register samples, not exception evidence.
"""
import argparse
import json
import mmap
from pathlib import Path
import struct

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--cache', type=Path, required=True)
p.add_argument('--slide', type=lambda x:int(x,0), required=True)
p.add_argument('--output', type=Path, required=True)
p.add_argument('addresses', nargs='+', type=lambda x:int(x,0))
a = p.parse_args()
main = (a.cache/'dyld_shared_cache_arm64').read_bytes()
assert main[:16].rstrip(b'\0') == b'dyld_v1   arm64'
region = struct.unpack_from('<Q',main,224)[0]
maximum = struct.unpack_from('<Q',main,240)[0]
assert 0 <= a.slide <= maximum and a.slide % 4096 == 0
offset,count = struct.unpack_from('<2Q',main,136)
images = []
for i in range(count):
    _,va,size,path = struct.unpack_from('<16sQ2I',main,offset+i*32)
    images.append((va,size,main[path:main.index(b'\0',path)].decode()))
mappings = []
for path in sorted(a.cache.glob('dyld_shared_cache_arm64*')):
    if path.suffix == '.symbols':
        continue
    with path.open('rb') as stream:
        header = stream.read(32)
        assert header[:16].rstrip(b'\0') == b'dyld_v1   arm64'
        at,number = struct.unpack_from('<2I',header,16)
        stream.seek(at)
        for _ in range(number):
            va,size,off,_,prot = struct.unpack('<3Q2I',stream.read(32))
            mappings.append((va,size,off,prot,path))
def read_va(va,size):
    matches = [m for m in mappings if m[0]<=va and va+size<=m[0]+m[1]]
    assert len(matches)==1, 'Unbacked or ambiguous cache address '+hex(va)
    at,_,off,_,path = matches[0]
    with path.open('rb') as stream:
        stream.seek(off+va-at)
        data = stream.read(size)
    assert len(data)==size
    return data
exports = {}
def image_exports(image):
    if image[0] in exports:return exports[image[0]]
    header = read_va(image[0],32)
    assert struct.unpack_from('<I',header)[0]==0xfeedfacf
    count,size = struct.unpack_from('<2I',header,16)
    commands = read_va(image[0]+32,size)
    at,linkedit,table = 0,None,None
    for _ in range(count):
        command,length = struct.unpack_from('<2I',commands,at)
        assert length>=8 and at+length<=len(commands)
        if command==0x19 and commands[at+8:at+24].rstrip(b'\0')==b'__LINKEDIT':
            linkedit = struct.unpack_from('<4Q',commands,at+24)
        if command==2:table=struct.unpack_from('<4I',commands,at+8)
        at += length
    assert at==len(commands) and linkedit and table
    symoff,nsyms,stroff,strsize = table
    strings = read_va(linkedit[0]+stroff-linkedit[2],strsize)
    symbols = read_va(linkedit[0]+symoff-linkedit[2],nsyms*16)
    result = []
    for i in range(nsyms):
        string,kind,section,_,value = struct.unpack_from('<IBBHQ',symbols,i*16)
        if not kind&0xe0 and kind&0xe==0xe and section and kind&1:
            assert string < len(strings)
            result.append((value,strings[string:strings.index(b'\0',string)].decode()))
    exports[image[0]]=result
    return result
rows = []
with (a.cache/'dyld_shared_cache_arm64.symbols').open('rb') as stream, mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as symbols:
    assert symbols[88:104] == main[400:416], 'Original symbols UUID mismatch'
    lo = struct.unpack_from('<Q',symbols,72)[0]
    no,nc,so,ss,eo,ec = struct.unpack_from('<6I',symbols,lo)
    entries = {struct.unpack_from('<Q',symbols,lo+eo+i*16)[0]:
               struct.unpack_from('<2I',symbols,lo+eo+i*16+8) for i in range(ec)}
    for pc in a.addresses:
        va = pc-a.slide
        image = next((im for im in images if im[0]<=va<im[0]+im[1]),None)
        row = dict(address=hex(pc),unslid_va=hex(va),image=image[2] if image else None)
        if image and image[0]-region in entries:
            start,count = entries[image[0]-region]
            assert start+count <= nc
            best = None
            for i in range(start,start+count):
                string,kind,section,_,value = struct.unpack_from('<IBBHQ',symbols,lo+no+i*16)
                if not kind&0xe0 and kind&0xe==0xe and section and image[0]<=value<=va and (best is None or value>best[0]):
                    best = value,string
            if best:
                value,string = best
                assert string < ss
                pos = lo+so+string
                row.update(nearest_local_symbol=symbols[pos:symbols.find(b'\0',pos)].decode(),offset=va-value)
        if image:
            candidates = [(v,n) for v,n in image_exports(image) if image[0]<=v<=va]
            if candidates:
                value,name = max(candidates)
                if 'offset' not in row or va-value <= row['offset']:
                    row.pop('nearest_local_symbol',None)
                    row.update(nearest_symbol=name,symbol_table='exported',offset=va-value)
            if 'nearest_symbol' not in row and 'nearest_local_symbol' in row:
                row.update(nearest_symbol=row['nearest_local_symbol'],symbol_table='local')
            row['original_instruction_bytes'] = read_va(va,8).hex()
        rows.append(row)
result = dict(cache_slide=hex(a.slide),cache_uuid=main[88:104].hex(),
              local_symbols_uuid_matches=True,live_sample=True,frames=rows)
a.output.parent.mkdir(parents=True,exist_ok=True)
assert not a.output.exists(), 'Preserve previous analysis'
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
