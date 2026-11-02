#!/usr/bin/env python3
"""Execute the three markers from the linked kernel with mocked MPIDR/CPU data.

This checks instruction writes and live-register preservation, not CPU reset,
cache coherence, exception level, PSCI, or physical device entry.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import unicorn
from unicorn import arm64_const as r

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--kernel',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--packed',type=Path,help='Also verify payload preserves markers and exception vectors')
a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
framework=Path(__file__).resolve().parents[2]/'UniXNU'
spec=importlib.util.spec_from_file_location('entry',framework/'scripts/patch-xnu-entry-probe.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
raw=a.kernel.read_bytes();m.load_segments(raw)
nm='/opt/homebrew/opt/llvm/bin/llvm-nm'
symbols={parts[2]:int(parts[0],16) for line in subprocess.check_output([nm,'-n',str(a.kernel)],text=True).splitlines() if len(parts:=line.split())==3}
trace=symbols['_native_t970_secondary_entry'];reset=symbols['_reset_vector'];start=symbols['_start_first_cpu']
assert trace%128==0
markers=[]
for va in range(reset,start,4):
 word=struct.unpack_from('<I',raw,m.file_offset(va))[0]
 for stage in (1,2,3):
  if word==0x52800005+(stage<<5) and raw[m.file_offset(va+4):m.file_offset(va+12)]==struct.pack('<II',0xb90000c5,0xd5033f9f):
   begin=va-(28 if stage==1 else 24)
   markers.append((stage,begin,raw[m.file_offset(begin):m.file_offset(va+12)]))
assert [s for s,_,_ in markers]==[1,2,3],markers
cases=0
for stage,va,code in markers:
 for cpu in (*range(8),8,255):
  u=unicorn.Uc(unicorn.UC_ARCH_ARM64,unicorn.UC_MODE_ARM)
  pc=va&0xffffffff;data=trace&0xffffffff
  for address,size in ((pc&~4095,8192),(data&~4095,8192),(0x50000000,4096)):
   u.mem_map(address,size)
  u.mem_write(pc,code);u.mem_write(data,b'\0'*1024)
  live=[r.UC_ARM64_REG_X0,r.UC_ARM64_REG_X1,r.UC_ARM64_REG_X2,r.UC_ARM64_REG_X3]+[getattr(r,'UC_ARM64_REG_X'+str(i)) for i in range(19,31)]
  values={reg:0x100000+reg*16 for reg in live}
  values[r.UC_ARM64_REG_X21]=0x50000000
  for reg,value in values.items():u.reg_write(reg,value)
  if stage!=1:
   first=struct.unpack_from('<I',code)[0];assert first&0xffc003ff==0x794002a4
   offset=((first>>10)&0xfff)*2
   u.mem_write(0x50000000+offset,struct.pack('<H',cpu))
  writes=[]
  def hook(machine,address,size,_):
   if stage==1 and address==pc:
    # MPIDR is an input supplied by firmware, not a host hardware result.
    machine.reg_write(r.UC_ARM64_REG_X4,cpu<<8)
    machine.reg_write(r.UC_ARM64_REG_PC,address+4)
  def write(machine,access,address,size,value,_):writes.append((address,size,value))
  u.hook_add(unicorn.UC_HOOK_CODE,hook);u.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
  u.emu_start(pc,pc+len(code),count=30)
  assert writes==([(data+cpu*128,4,stage)] if cpu<8 else []),(stage,cpu,writes)
  assert all(u.reg_read(reg)==value for reg,value in values.items())
  cases+=1
report=dict(kernel_sha256=hashlib.sha256(raw).hexdigest(),passed=True,linked_marker_cases=cases,
            trace_symbol=hex(trace),trace_bytes=1024,per_core_stride=128,
            stages=[dict(stage=s,address=hex(va),sha256=hashlib.sha256(code).hexdigest()) for s,va,code in markers],
            mpidr_and_cpu_data_mocked=True,live_registers_preserved=True,
            actual_secondary_entry_verified=False,cache_coherence_verified=False)
if a.packed:
 packed=a.packed.read_bytes()
 low=symbols['_LowResetVectorBase'];exc=symbols['_LowExceptionVectorBase']
 ranges=[(low+offset,4) for offset in (0,0x200,0x280,0x300,0x380)]+[(exc,0x1000)]+[(va,len(code)) for _,va,code in markers]
 for va,size in ranges:
  offset=m.file_offset(va)
  assert packed[offset:offset+size]==raw[offset:offset+size],hex(va)
 report.update(packed_sha256=hashlib.sha256(packed).hexdigest(),reset_branch_and_exception_vectors_preserved=True,packed_markers_unchanged=True)
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: 30 linked ARM64 marker cases; bounded writes, isolated per-core records, live registers preserved')
