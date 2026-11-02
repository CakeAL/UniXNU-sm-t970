from pathlib import Path
import subprocess,tempfile
s=Path('package/ShengUfs/NativeUfs.cpp').read_text()
helper=s.split('// First rejected verified-block snapshot only;',1)[1].split('bool NativeUfsBlock::configureVerification',1)[0]
helper='// First rejected verified-block snapshot only;'+helper
prefix=r'''#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
struct vr_view { const uint8_t *hashes; uint64_t block_count; };
static unsigned calls;
static int sha(const void *data, size_t, uint8_t *digest) { ++calls; memcpy(digest,data,32); return 1; }
static struct { int (*sha256)(const void*,size_t,uint8_t*); } vr_xnu_crypto={sha};
static volatile uint64_t native_ufs_verified_blocks;
static volatile uint32_t native_ufs_integrity_failures;
'''
main=r'''
int main(){
 uint8_t hashes[64], data[32]; memset(hashes,0x22,sizeof hashes);memset(data,0x11,sizeof data);
 vr_view view{hashes,2};
 assert(strstr(native_ufs_integrity_text(),"no rejected block snapshot"));
 recordIntegrityFailure(&view,1,data,4096,100,6);
 assert(gIntegrityIndex==1 && gIntegrityLba==101 && gIntegrityLength==4096 && calls==1);
 assert(gIntegrityExpected==0x2222222222222222ULL && gIntegrityActual==0x1111111111111111ULL && gIntegrityHashOk==3);
 recordIntegrityFailure(&view,0,data,4096,100,7);assert(gIntegrityIndex==1 && calls==1);
 gIntegrityIndex=UINT64_MAX; recordIntegrityFailure(&view,2,data,5000,100,6);
 assert(gIntegrityHashOk==0 && calls==1);
 assert(strlen(native_ufs_integrity_text())<320);
 puts("PASS: actual diagnostic first-error retention, index/length bounds, no second I/O, prefix encoding");
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'check.cpp').write_text(prefix+helper+main)
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p/'check.cpp'),'-o',str(p/'check')],check=True)
 subprocess.run([str(p/'check')],check=True)
