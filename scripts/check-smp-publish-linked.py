#!/usr/bin/env python3
"""Reject compiled-out publication and C-entry markers in the actual linked kernel."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess
import unicorn
from unicorn import arm64_const as r
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--kernel',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
f=Path(__file__).resolve().parents[2]/'UniXNU/scripts/patch-xnu-entry-probe.py'
spec=importlib.util.spec_from_file_location('entry',f);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
raw=a.kernel.read_bytes();m.load_segments(raw)
nm='/opt/homebrew/opt/llvm/bin/llvm-nm';dump='/opt/homebrew/opt/llvm/bin/llvm-objdump'
symbols={z[2]:int(z[0],16) for line in subprocess.check_output([nm,'-n',str(a.kernel)],text=True).splitlines() if len(z:=line.split())==3}
body=subprocess.check_output([dump,'-d','--disassemble-symbols=_cpu_start',str(a.kernel)],text=True)
(a.output/'cpu-start.txt').write_text(body)
assert '<_PE_parse_boot_argn>' in body,'Publication option was compiled out'
assert body.count('<_flush_dcache>')==4,'Expected original two plus two publication flushes'
assert len(re.findall(r'mov\s+w1, #0x8\s',body))==2,'Expected two exact eight-byte publication ranges'
assert body.rindex('<_flush_dcache>')<body.index('<_PE_cpu_start>'),'Publication must precede platform wake'
assert b't970-smp-publish-state\0' in raw
# Resolve the exact ADRP/ADD argument pairs for the two added calls.
instructions=[line for line in body.splitlines() if re.match(r'^[0-9a-f]{16}:',line)]
flush_indices=[i for i,line in enumerate(instructions) if '<_flush_dcache>' in line]
for i,name in zip(flush_indices[-2:],('_cpu_ttep','_sysreg_restore')):
 page=re.search(r'adrp\s+x0, (0x[0-9a-f]+)',instructions[i-4])
 offset=re.search(r'add\s+x0, x0, #(0x[0-9a-f]+)',instructions[i-3])
 assert page and offset and int(page[1],16)+int(offset[1],16)==symbols[name],name
# Run the actual C entry up to its first PAN write, observing the marker store.
start=symbols['_arm_init_cpu'];data=symbols['_native_t970_secondary_entry']&0xffffffff
part=raw[m.file_offset(start):m.file_offset(start)+256]
stop=part.find(struct.pack('<I',0xd500419f));assert stop>0,'Expected pre-PAN C entry region'
code=part[:stop]
for cpu in (*range(9),65535):
 u=unicorn.Uc(unicorn.UC_ARCH_ARM64,unicorn.UC_MODE_ARM)
 pc=start&0xffffffff;stack=0x50000000;cpudata=0x60000000
 for address,size in ((pc&~4095,4096),(data&~4095,8192),(stack,8192),(cpudata,4096)):u.mem_map(address,size)
 u.mem_write(pc,code);u.mem_write(cpudata,struct.pack('<H',cpu))
 u.reg_write(r.UC_ARM64_REG_X0,cpudata);u.reg_write(r.UC_ARM64_REG_SP,stack+8192)
 writes=[]
 def write(machine,access,address,size,value,_):
  if not stack<=address<stack+8192:writes.append((address,size,value))
 u.hook_add(unicorn.UC_HOOK_MEM_WRITE,write);u.emu_start(pc,pc+len(code),count=80)
 assert writes==([(data+cpu*128,4,4)] if cpu<8 else []),(cpu,writes)
report=dict(kernel_sha256=hashlib.sha256(raw).hexdigest(),passed=True,compiled_publication_guard_present=True,
            compiled_publication_flushes=2,total_cpu_start_flushes=4,exact_publication_bytes_each=8,compiled_symbol_addresses_checked=True,
            publication_before_platform_wake=True,actual_c_entry_cases=10,actual_c_marker_present=True,
            cpu_data_mocked=True,hardware_publication_verified=False)
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS: publication opt-in/two 8-byte flushes compiled before wake; ten actual C-entry marker cases')
