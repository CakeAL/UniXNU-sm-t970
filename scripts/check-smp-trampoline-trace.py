#!/usr/bin/env python3
"""Execute linked pre-branch capture and first high-entry marker with fake MMU regs.

The emulator does not validate real page tables, cache coherence or CPU startup.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import unicorn
from unicorn import arm64_const as r

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--kernel',type=Path,required=True)
p.add_argument('--packed',type=Path)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
f=Path(__file__).resolve().parents[2]/'UniXNU/scripts/patch-xnu-entry-probe.py'
spec=importlib.util.spec_from_file_location('entry',f);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
raw=a.kernel.read_bytes();m.load_segments(raw)
symbols={z[2]:int(z[0],16) for line in subprocess.check_output(['/opt/homebrew/opt/llvm/bin/llvm-nm','-n',str(a.kernel)],text=True).splitlines() if len(z:=line.split())==3}
lo=symbols['_native_t970_trampoline_before_branch'];hi=symbols['_native_t970_trampoline_high_alias']
# The final BR x0 must be the immediately preceding instruction.
code=raw[m.file_offset(lo):m.file_offset(hi)]
entry=raw[m.file_offset(hi):m.file_offset(hi)+12]
assert struct.unpack_from('<I',code,len(code)-4)[0]==0xd61f0000
assert entry==struct.pack('<III',0x52800185,0xb90000c5,0xd5033f9f)
for turn,target in enumerate((0x60000000,0xfffffff007408000)):
 u=unicorn.Uc(unicorn.UC_ARCH_ARM64,unicorn.UC_MODE_ARM)
 pc=0x40000000;record=0x50000080
 for addr,size in ((pc,4096),(record&~4095,4096),(target&~4095,4096)):u.mem_map(addr,size)
 u.mem_write(pc,code);u.mem_write(target,entry)
 keep=[r.UC_ARM64_REG_X0,r.UC_ARM64_REG_X1,r.UC_ARM64_REG_X2,r.UC_ARM64_REG_X3]+[getattr(r,'UC_ARM64_REG_X'+str(i)) for i in range(19,31)]+[r.UC_ARM64_REG_SP]
 values={reg:0x100000+reg*16 for reg in keep}
 values.update({r.UC_ARM64_REG_X0:target,r.UC_ARM64_REG_X22:0xfffffff00427c000,r.UC_ARM64_REG_X23:0xc007c000,r.UC_ARM64_REG_X30:0xfffffff007940000})
 for reg,value in values.items():u.reg_write(reg,value)
 u.reg_write(r.UC_ARM64_REG_X6,record)
 mmu=[0x12345678c319a000,0x87654321c2f79000,0x7000803518];mrs_seen=[];writes=[]
 def hook(machine,address,size,_):
  if pc<=address<pc+len(code):
   word=struct.unpack_from('<I',code,address-pc)[0]
   if word in (0xd5382025,0xd5382005,0xd5382045):
    expected=[0xd5382025,0xd5382005,0xd5382045][len(mrs_seen)];assert word==expected
    machine.reg_write(r.UC_ARM64_REG_X5,mmu[len(mrs_seen)]);mrs_seen.append(word)
    machine.reg_write(r.UC_ARM64_REG_PC,address+4)
 def write(machine,access,address,size,value,_):writes.append((address,size,value))
 u.hook_add(unicorn.UC_HOOK_CODE,hook);u.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
 u.emu_start(pc,target+len(entry),count=40)
 assert len(mrs_seen)==3 and all(u.reg_read(reg)==value for reg,value in values.items())
 assert struct.unpack('<I',u.mem_read(record,4))[0]==12
 assert struct.unpack('<7Q',u.mem_read(record+8,56))==(target,values[r.UC_ARM64_REG_X30],values[r.UC_ARM64_REG_X22],values[r.UC_ARM64_REG_X23],*mmu)
 assert all(record<=address and address+size<=record+64 for address,size,_ in writes)
 assert [value for address,size,value in writes if address==record and size==4]==[11,12]
report=dict(kernel_sha256=hashlib.sha256(raw).hexdigest(),passed=True,cases=2,full_width_high_va_branch_executed=True,register_values_mocked=True,physical_record_bounds_checked=True,captured_seven_full_width_values=True,live_registers_preserved=True,real_translation_tables_verified=False,cache_coherence_verified=False)
if a.packed:
 packed=a.packed.read_bytes()
 for va,size in ((lo,len(code)),(hi,len(entry))):
  off=m.file_offset(va);assert packed[off:off+size]==raw[off:off+size]
 report.update(packed_sha256=hashlib.sha256(packed).hexdigest(),packed_branch_and_capture_unchanged=True)
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: linked branch/capture, low and full-width high VA, milestones11/12, seven values and preserved live registers')
