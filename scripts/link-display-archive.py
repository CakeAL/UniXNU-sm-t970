#!/usr/bin/env python3
"""Bind audited original Legacy imports and make an opt-in late archive."""
import argparse, hashlib, json, struct, subprocess, sys
from pathlib import Path
DEVICE=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('framework','gop-object','registration-object','output'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();out=a.output.resolve()
 if out.exists():raise ValueError('Preserve earlier outputs')
 audit=json.loads((DEVICE/'evidence/display/abi21h461/audit.json').read_text())
 gop=json.loads((DEVICE/'evidence/display/abi21h461/object-check.json').read_text())
 reg=json.loads((DEVICE/'evidence/display/registration-v1/report.json').read_text())
 sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
 if sha(a.gop_object)!=gop['object_sha256'] or sha(a.registration_object)!=reg['object_sha256']:raise ValueError('Unreviewed object')
 sys.path.insert(0,str(a.framework.resolve()/'kits/XnuPrelink'))
 from native_prelink import macho
 raw=a.gop_object.read_bytes();m=macho(raw);at=next(at for c,at,_ in m['commands'] if c==2);sy,n,st,_=struct.unpack_from('<4I',raw,at+8);symbols=[]
 for i in range(n):
  ix,k,_,_,v=struct.unpack_from('<IBBHQ',raw,sy+16*i);symbols.append((raw[st+ix:raw.index(b'\0',st+ix)].decode(),v,k))
 vp=next(v for name,v,_ in symbols if name=='__ZTV19NativeLegacyDisplay');rel={}
 for seg in m['segments']:
  for sec in seg['sections']:
   if sec['va']<=vp<sec['va']+sec['size']:
    ro,rc=struct.unpack_from('<2I',raw,sec['command_offset']+56)
    for i in range(rc):
     off,bits=struct.unpack_from('<2I',raw,ro+i*8)
     if bits>>27&1 and bits>>28==0 and bits>>25&3==3:rel[sec['va']+off]=symbols[bits&0xffffff][0]
 delta=audit['slide']+0x1000000
 bind={'__ZN25IOMobileFramebufferLegacyC2EPK11OSMetaClass':0xfffffff0057865cc+delta,'__ZN25IOMobileFramebufferLegacyD2Ev':0xfffffff005786618+delta,'__ZN25IOMobileFramebufferLegacy10gMetaClassE':0xfffffff006b35940+delta,'__ZTV25IOMobileFramebufferLegacy':int(audit['legacy_vptr'],16)-16,'_native_legacy_vsync_notify':0xfffffff005796720+delta,'_native_legacy_set_refresh_properties':0xfffffff00579ebb8+delta}
 for row in audit['methods']:
  name=rel[vp+16+row['slot']*8]
  if '25IOMobileFramebufferLegacy' in name:
   value=int(row['address'],16)
   if name in bind and bind[name]!=value:raise ValueError('Conflicting alias')
   bind[name]=value
 for row in audit['surface_getters']:bind['_native_legacy_surface_'+row['name']]=int(row['address'],16)
 out.mkdir(parents=True)
 assembly=out/'original-bindings.S';assembly.write_text(''.join(f'.globl {n}\n.set {n}, {v:#x}\n' for n,v in sorted(bind.items())))
 subprocess.run(['xcrun','clang','-target','arm64-apple-ios17.0','-c',str(assembly),'-o',str(out/'original-bindings.o')],check=True)
 subprocess.run(['llvm-objcopy','--remove-section=__DATA,__mod_init_func','--globalize-symbol=__GLOBAL__sub_I_NativeLegacyDisplay.cpp',str(a.gop_object),str(out/'NativeLegacyDisplay.late.o')],check=True)
 archive=out/'libNativeLegacyDisplay.late.a'
 subprocess.run(['xcrun','ar','rcs',str(archive),str(out/'NativeLegacyDisplay.late.o'),str(a.registration_object),str(out/'original-bindings.o')],check=True)
 # Every private class import and native_legacy callback must be supplied by archive members.
 undef=set();defined=set()
 for obj in (out/'NativeLegacyDisplay.late.o',a.registration_object,out/'original-bindings.o'):
  undef.update(subprocess.check_output(['xcrun','nm','-u',str(obj)],text=True).split())
  defined.update(line.split()[-1] for line in subprocess.check_output(['xcrun','nm','-gU',str(obj)],text=True).splitlines() if line.split())
 missing={n for n in undef-defined if n.startswith('_native_legacy_') or '25IOMobileFramebufferLegacy' in n or '__GLOBAL__sub_I_NativeLegacyDisplay' in n}
 if missing:raise ValueError(str(sorted(missing)))
 (out/'build-report.json').write_text(json.dumps(dict(archive_sha256=sha(archive),bindings={k:hex(v) for k,v in bind.items()},gop_object_sha256=sha(a.gop_object),registration_object_sha256=sha(a.registration_object),private_imports_resolved=True,kernel_linked=False,runtime_verified=False),indent=2)+'\n')
 print('PASS: late archive built; private class imports and board callbacks resolved')
if __name__=='__main__':main()
