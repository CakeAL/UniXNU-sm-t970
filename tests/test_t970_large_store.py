#!/usr/bin/env python3
"""Exercise the actual provider-open function with rejected geometry and headers."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
src = (root/'drivers/ShengUfs/NativeUfs.cpp').read_text()
a=src.index('extern "C" int native_ufs_store_open (')
b=src.index('\n\nextern "C" int native_ufs_store_read',a)
function=src[a:b]
prefix=r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include "T970DataExtent.h"
#include "PersistOverlay.h"
static uint32_t le32(const uint8_t *p){return persist::get32(p);}
static uint64_t le64(const uint8_t *p){return persist::get64(p);}
static uint32_t rootCrc32(const uint8_t *p,size_t n){return persist::crc32(p,n);}
#include "T970LargeData.h"
uint8_t native_ram_block_seed_sha256[32], block[4096], digest[32];
struct { bool valid=true; uint64_t first=37292800,last=62458623,imageBytes=9382658048ULL; } gStoreGeometry;
struct { bool ready=true; } gHost;
uint64_t gStoreRegionFirst=0,gStoreRegionBlocks=0; bool gT970LargeNeedsInit=false;
unsigned mode=2, large=1, direct=0, init=1, reset=0, gpt=0, opens=0;
unsigned storeMode(){return mode;} uint64_t reserveBlocks(){return 262144;}
void t970ApfsProbe(){} unsigned native_ufs_store_gpt_check(){return gpt;}
uint64_t t970DataFirst(unsigned,unsigned,uint64_t,uint64_t,uint64_t,uint64_t,uint64_t){return 0;}
int t970DataHeaderState(const uint8_t *,const uint8_t *){return -1;}
bool PE_parse_boot_argn(const char *n,uint32_t *v,size_t){
 if (!strcmp(n,"t970-large-data")) *v=large; else if (!strcmp(n,"t970-ufs-data")) *v=direct;
 else if (!strcmp(n,"t970-large-init")) *v=init; else if (!strcmp(n,"data-reset") || !strcmp(n,"sheng-data-reset")) *v=reset; else *v=0; return true; }
const int kIOReturnSuccess=0;
int hostRead4k(int,uint64_t l,int n,void *d){assert(l==kT970LargeFirst && n==1);memcpy(d,block,4096);return 0;}
bool hostStoreOpen(uint64_t l,uint64_t n){assert(l==kT970LargeFirst && n==kT970LargeBlocks); ++opens;return true;}
struct SHA256_CTX{}; void SHA256_Init(SHA256_CTX *){} void SHA256_Update(SHA256_CTX *,const void *,size_t){} void SHA256_Final(uint8_t *p,SHA256_CTX *){memcpy(p,digest,32);}
void panic(const char *,...){}
'''
suffix=r'''
int main(){
 memcpy(native_ram_block_seed_sha256,kT970LargeSeed,32); memcpy(digest,kT970DirectHeaderHash,32);
 uint64_t first=0; const char *why=nullptr;
 init=0; assert(!native_ufs_store_open(kT970LargeBlocks,&first,&why) && opens==0);
 init=1; direct=1; assert(!native_ufs_store_open(kT970LargeBlocks,&first,&why) && opens==0);
 direct=0; gpt=1; assert(!native_ufs_store_open(kT970LargeBlocks,&first,&why) && opens==0);
 gpt=0; digest[0]^=1; assert(!native_ufs_store_open(kT970LargeBlocks,&first,&why) && opens==0);
 digest[0]^=1; assert(native_ufs_store_open(kT970LargeBlocks,&first,&why) && first==kT970LargeFirst && opens==1 && gT970LargeNeedsInit);
 gStoreRegionFirst=gStoreRegionBlocks=0; opens=0; persist::encodeHeader(block,kT970LargePages,kT970LargeSeed,1);
 assert(native_ufs_store_open(kT970LargeBlocks,&first,&why) && opens==1 && !gT970LargeNeedsInit);
}
'''
with tempfile.TemporaryDirectory() as temp:
    p=Path(temp)/'test.cpp';p.write_text(prefix+function+suffix)
    exe=Path(temp)/'test'
    subprocess.run(['clang++','-std=c++17','-Wall','-Wextra','-Werror','-Wno-pointer-bool-conversion','-fsanitize=address,undefined','-I',str(root/'drivers/ShengUfs'),'-I',str(root.parent/'UniXNU/drivers/RamBlock'),str(p),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
