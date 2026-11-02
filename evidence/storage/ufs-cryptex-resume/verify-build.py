import json, subprocess, hashlib, re
from pathlib import Path
base=Path('../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970').resolve()
out=Path('out/step7/cryptex-resume-verification').resolve()
out.mkdir(exist_ok=True)
records=json.loads((base/'tree/build/xnu/ios-obj/DEVELOPMENT_ARM64_BCM2837/compile_commands.json').read_text())
checks={}
for filename in ['kern_exec.c','vm_unix.c']:
    record=next(r for r in records if r['file'].endswith('/'+filename))
    args=record['arguments'][:]
    flags=[a for a in args if a.startswith('XNU_OWNER_')]
    if filename=='kern_exec.c':
        assert 'XNU_OWNER_UNION_SYSTEMOS=0' in flags, flags
        assert 'XNU_OWNER_CACHE_STARTUP=1' in flags, flags
        assert 'XNU_OWNER_BOOT_MANIFEST=1' in flags, flags
    else:
        assert 'XNU_OWNER_CACHE_CARRIER=1' in flags, flags
    target=out/(filename+'.i')
    args.remove('-c');args[args.index('-o')+1]=str(target)
    args.extend(['-E','-P'])
    result=subprocess.run(args,cwd=record['directory'],capture_output=True,text=True)
    (out/(filename+'.stderr')).write_text(result.stderr)
    assert result.returncode==0, result.stderr[-2000:]
    text=target.read_text()
    if filename=='kern_exec.c':
        function=text.split('native_owner_cache_prepare(proc_t p,',1)[1].split('native_owner_data_prepare',1)[0]
        assert 'const char *mountpoint = "/System/Cryptexes/OS";' in function
        assert 'const char *mountpoint = "/";' not in function
        assert 'request.flags |= ' not in function
        assert 'DYLD_SHARED_CACHE_DIR=/System/Cryptexes/OS/System/Library/Caches/com.apple.dyld' in function
        assert '*envp = scratch + 0x500;' in function
        guard = text.split('if (cache_error || looked[1] != 0) {', 1)[1].split('\n  }', 1)[0]
        assert '(panic)("offline owner cache:' in guard
    else:
        function=text.split('native_owner_shared_cache_carrier(vnode_t process_root,',1)[1].split('shared_region_map',1)[0]
        assert 'const char *directory = "/System/Cryptexes/OS/System/Library/Caches/com.apple.dyld";' in function
        assert '8846FE78-2910-4297-AF97-D59BB6F8FC16' in function
    checks[filename]={'owner_flags':flags,'preprocessed_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'source_sha256':hashlib.sha256(Path(record['file']).read_bytes()).hexdigest(),'pass':True}
report={'command':'PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 out/step7/verify-cryptex-build.py','checks':checks,'kernel_sha256':hashlib.sha256((base/'kernel/kernel.macho').read_bytes()).hexdigest(),'pass':True,'scope':'Real compiler records replayed with -E -P; checks active mount, environment, carrier and conditional panic branches. Host verification only.'}
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
