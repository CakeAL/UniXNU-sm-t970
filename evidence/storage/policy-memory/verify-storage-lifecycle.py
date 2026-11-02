from pathlib import Path
import subprocess,tempfile
source=Path('package/ShengUfs/NativeUfs.cpp').read_text()
helpers=source.split('// Boot-lifetime ownership stays with the carrier.',1)[1].split('static bool readOwnerEnvelope',1)[0]
helpers='// Boot-lifetime ownership stays with the carrier.'+helpers
configure='bool NativeUfsBlock::configureVerification ()'+source.split('bool NativeUfsBlock::configureVerification ()',1)[1].split('bool NativeUfsBlock::authenticatesVolume',1)[0]
free='void NativeUfsBlock::free ()'+source.split('void NativeUfsBlock::free ()',1)[1].split('// Select the whole GPT',1)[0]
prefix=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <vector>
#include <sys/mman.h>
using vm_offset_t=uintptr_t;using vm_size_t=size_t;using kma_flags_t=int;
#define NATIVE_VERIFIED_BLOCK 1
#define PAGE_SIZE 4096
#define PAGE_MASK 4095
#define VM_PROT_READ 1
#define TRUE 1
#define KERN_SUCCESS 0
#define KMA_KOBJECT 1
#define KMA_DATA 2
#define VM_KERN_MEMORY_SECURITY 0
#define VR_HEADER_BYTES 160
#define VR_SIGNATURE_BYTES 384
#define VR_KEY_BYTES 395
#define VR_OK 0
static void *kernel_map;
static const unsigned char verified_root_key[395]={42};
static const int vr_xnu_crypto=0;
struct vr_view {const uint8_t *hashes;uint64_t image_bytes;};
struct NativeVerifiedBlockPolicy {const uint8_t *manifest;uint64_t manifestBytes;};
static NativeVerifiedBlockPolicy verified_root_policies[2];static uint64_t verified_root_policy_count;
static struct {const char *stage;uint64_t windowBytes,policyCount;uint32_t verify;} gRootDiagnostic;
struct Mapping {uintptr_t p;size_t n;bool ro;};static std::vector<Mapping> mappings;
static unsigned allocated,freed,auths;static bool protect_fail,alloc_fail,auth_fail;
static size_t round_page(size_t n){return(n+4095)&~size_t(4095);}
static uintptr_t allocate(size_t n){void*p=mmap(nullptr,n,PROT_READ|PROT_WRITE,MAP_ANON|MAP_PRIVATE,-1,0);assert(p!=MAP_FAILED);mappings.push_back({uintptr_t(p),n,false});return uintptr_t(p);}
static int kmem_alloc(void*,vm_offset_t*p,size_t n,kma_flags_t,int){if(alloc_fail)return 5;*p=allocate(n);++allocated;return 0;}
static int vm_map_protect(void*,uintptr_t p,uintptr_t end,int,int){if(protect_fail)return 5;for(auto &m:mappings)if(m.p==p&&m.n==end-p){assert(mprotect((void*)p,m.n,PROT_READ)==0);m.ro=true;return 0;}assert(false);return 5;}
static void kmem_free(void*,uintptr_t p,size_t n){for(auto it=mappings.begin();it!=mappings.end();++it)if(it->p==p&&it->n==n){assert(munmap((void*)p,n)==0);mappings.erase(it);++freed;return;}assert(false);}
static bool protected_range(const void*p,size_t n){for(const auto&m:mappings)if(m.ro&&uintptr_t(p)>=m.p&&uintptr_t(p)+n<=m.p+m.n)return true;return false;}
static int vr_open(const uint8_t *p,uint64_t n,const uint8_t *key,int,const int*,vr_view*out){++auths;assert(protected_range(p,n)&&protected_range(key,395));assert(key!=verified_root_key&&!memcmp(key,verified_root_key,395));if(auth_fail)return 7;out->hashes=p+544;memcpy(&out->image_bytes,p+24,8);return 0;}
static void IOFree(void*,size_t){assert(false);}static void IOLockFree(void*){assert(false);}static const size_t kDataMax=131072;
struct IOBlockStorageDevice {void free(){}};
struct NativeUfsBlock:IOBlockStorageDevice {
 uint64_t bytes=8192;vr_view verified={};uintptr_t verifiedStorage=0;size_t verifiedStorageBytes=0;
 bool verifiedStorageBorrowed=false;uintptr_t verifiedKeyStorage=0;void*bounce=nullptr;void*windowLock=nullptr;
 bool configureVerification();void free();
};
'''
tests=r'''
static uint8_t* fixture(bool registered){
 auto*p=(uint8_t*)allocate(4096);uint64_t n=8192;memcpy(p+24,&n,8);
 verified_root_policy_count=1;verified_root_policies[0]={p,608};
 if(registered)gOwnerCarrierStorage[0]={p,608,4096};return p;
}
static void reset(){while(!mappings.empty())kmem_free(nullptr,mappings.back().p,mappings.back().n);gOwnerCarrierStorage[0]={};gOwnerCarrierStorage[1]={};verified_root_policy_count=0;allocated=freed=auths=0;protect_fail=alloc_fail=auth_fail=false;native_ufs_policy_borrowed_bytes=native_ufs_policy_copied_bytes=0;}
int main(){
 {
 auto*p=fixture(true);size_t n=0;assert(ownerCarrierAllocation(p,608,&n)&&n==4096);
 assert(!ownerCarrierAllocation(p+1,608,&n));assert(!ownerCarrierAllocation(p,607,&n));assert(!ownerCarrierAllocation(nullptr,608,&n));
 NativeUfsBlock d;assert(d.configureVerification());assert(d.verifiedStorage==(uintptr_t)p&&d.verifiedStorageBorrowed);
 assert(allocated==1&&auths==1&&native_ufs_policy_borrowed_bytes==4096&&native_ufs_policy_copied_bytes==0);
 d.free();assert(freed==1&&mappings.size()==1&&protected_range(p,608));reset();
 }
 {
 auto*p=fixture(false);NativeUfsBlock d;assert(d.configureVerification());assert(!d.verifiedStorageBorrowed&&d.verifiedStorage!=(uintptr_t)p);
 assert(allocated==1&&auths==1&&native_ufs_policy_copied_bytes==4096);d.free();assert(freed==1&&mappings.size()==1);reset();
 }
 {
 fixture(true);protect_fail=true;NativeUfsBlock d;assert(!d.configureVerification());assert(auths==0);d.free();assert(freed==1&&mappings.size()==1);reset();
 }
 {
 fixture(true);auth_fail=true;NativeUfsBlock d;assert(!d.configureVerification());assert(auths==1&&native_ufs_policy_borrowed_bytes==0);d.free();assert(freed==1&&mappings.size()==1);reset();
 }
 {
 fixture(true);alloc_fail=true;NativeUfsBlock d;assert(!d.configureVerification());assert(auths==0);d.free();assert(freed==0&&mappings.size()==1);reset();
 }
}
'''
with tempfile.TemporaryDirectory() as directory:
 p=Path(directory);(p/'check.cpp').write_text(prefix+helpers+configure+free+tests)
 subprocess.run(['c++','-std=c++17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(p/'check.cpp'),'-o',str(p/'check')],check=True)
 subprocess.run([str(p/'check')],check=True)
print('PASS: actual configure/free functions; borrowed RO/private-key lifecycle, fallback ownership, protection/auth/allocation failures')
