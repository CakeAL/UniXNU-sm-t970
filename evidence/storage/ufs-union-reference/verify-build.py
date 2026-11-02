import json, subprocess, hashlib
from pathlib import Path
base=Path('../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970').resolve()
out=Path('out/step7/union-reference-verification').resolve();out.mkdir(exist_ok=True)
records=json.loads((base/'tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/compile_commands.json').read_text())
record=next(r for r in records if r['file'].endswith('/kern_exec.c'))
flags=[a for a in record['arguments'] if a.startswith('XNU_OWNER_')]
for wanted in ['XNU_OWNER_UNION_SYSTEMOS=1','XNU_OWNER_CACHE_MOUNT=1','XNU_OWNER_CACHE_STARTUP=1','XNU_OWNER_BOOT_MANIFEST=1']:
    assert wanted in flags,(wanted,flags)
args=record['arguments'][:];args.remove('-c');args[args.index('-o')+1]=str(out/'kern_exec.i');args+=['-E','-P']
r=subprocess.run(args,cwd=record['directory'],capture_output=True,text=True);assert r.returncode==0,r.stderr[-2000:]
text=(out/'kern_exec.i').read_text()
function=text.split('native_owner_cache_prepare(proc_t p,',1)[1].split('native_owner_data_prepare',1)[0]
assert 'const char *mountpoint = "/";' in function
assert 'const char *mountpoint = "/System/Cryptexes/OS";' not in function
assert 'DYLD_SHARED_CACHE_DIR=' not in function
assert 'request.flags |= ' in function
assert '*envp = 0ULL;' in function or '*envp = 0;' in function or '*envp = ((user_addr_t)0);' in function or '*envp = ((user_addr_t) 0);' in function,function[function.find('native_owner_cache_stage = 5'):function.find('native_owner_cache_stage = 6')]
assert 'const int expected = 0;' in text
assert 'if (cache_error || looked[expected] != 0) {' in text
assert 'native_owner_shared_cache_carrier' not in function
vfs=base/'tree/.cache/xnu-work/bsd/vfs/vfs_syscalls.c'
subprocess.run(['python3.14','scripts/check-union-root-reference.py','--source',str(vfs)],check=True)
report={'pass':True,'compiler_flags':flags,'preprocessed_sha256':hashlib.sha256((out/'kern_exec.i').read_bytes()).hexdigest(),'vfs_source_sha256':hashlib.sha256(vfs.read_bytes()).hexdigest(),'kernel_sha256':hashlib.sha256((base/'kernel/kernel.macho').read_bytes()).hexdigest(),'checks':['Active root mount with MNT_UNION; no DYLD_SHARED_CACHE_DIR override','Diagnostic requires the actual /System cache path, not an absent later cryptex alias','Five reference-accounting cases compiled from actual patched XNU functions pass'],'scope':'Host build checks only; no runtime launchd/cache claim'}
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
