#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <zlib.h>
#include "T970ReadTest.h"
struct Port {
  uint8_t buffer[16384]={},header[4096]={},entries[16384]={};
  unsigned mode=0,calls=0,reads=0;bool poisoned=false,ua=false;
  static void le(uint8_t *p,uint64_t v,unsigned n=4){for(unsigned i=0;i<n;++i)p[i]=uint8_t(v>>(8*i));}
  static void be(uint8_t *p,uint32_t v){for(unsigned i=0;i<4;++i)p[i]=uint8_t(v>>(24-8*i));}
  uint32_t crc(const uint8_t *p,unsigned n,bool hdr){uint8_t tmp[16384];memcpy(tmp,p,n);if(hdr)memset(tmp+16,0,4);return uint32_t(crc32(0,tmp,n));}
  void prepare(unsigned m){
    mode=m;memcpy(header,"EFI PART",8);le(header+8,0x10000);le(header+12,92);le(header+24,1,8);le(header+32,62458879,8);
    le(header+40,6,8);le(header+48,62458874,8);le(header+72,2,8);le(header+80,128);le(header+84,128);
    entries[0]=1;le(entries+32,mode==7?2969601:2969600,8);le(entries+40,62458874,8);
    for(unsigned i=0;i<8;++i)entries[56+2*i]=uint8_t("userdata"[i]);
    if(mode==8)le(header+80,129);
    if(mode==9)le(header+72,0x100000002ULL,8);
    le(header+88,crc(entries,16384,false));le(header+16,crc(header,92,true));
    if(mode==4)header[16]^=1;
  }
  bool healthy(){return !poisoned;}
  uint32_t sense(){return ua?0x62900:0;}
  const uint8_t *data(){return buffer;}
  bool command(const uint8_t *cdb,unsigned length,unsigned bytes){
    assert(!poisoned);++calls;
    assert(cdb[0]==0x12||cdb[0]==0x25||cdb[0]==0x28);
    if(mode==1){poisoned=true;return false;}
    if(mode==2 && !ua){ua=true;return false;}
    if(mode==10)return false;
    memset(buffer,0,sizeof(buffer));
    if(cdb[0]==0x12){assert(length==6&&bytes==36);buffer[4]=31;memcpy(buffer+8,"SAMSUNG T970 TEST DISK  ",24);}
    if(cdb[0]==0x25){assert(length==10&&bytes==8);be(buffer,62458879);be(buffer+4,mode==3?512:4096);}
    if(cdb[0]==0x28){
      assert(length==10);uint32_t lba=uint32_t(cdb[2])<<24|uint32_t(cdb[3])<<16|uint32_t(cdb[4])<<8|cdb[5];
      unsigned blocks=unsigned(cdb[7])<<8|cdb[8];assert(bytes==blocks*4096);
      if(lba==1){assert(blocks==1);memcpy(buffer,header,4096);if(++reads==2&&mode==5)buffer[100]^=1;}
      else {assert(lba==2&&blocks==4);memcpy(buffer,entries,16384);if(mode==6)buffer[0]^=1;}
    }
    return true;
  }
};
int main(){
 for(unsigned mode=0;mode<11;++mode){Port p;p.prepare(mode);uint8_t work[20480];auto r=t970_read::run(p,work);
   assert(p.calls<=6);
   if(mode==0||mode==2){assert(r.stage==6&&r.geometry&&r.repeat&&r.entries);assert(r.commands==(mode==2?6U:5U));}
   else assert(!r.geometry);
   if(mode==1)assert(p.calls==1&&p.poisoned);
   if(mode==10)assert(p.calls==1); // Non-UA completed error is not retried.
   if(mode==3)assert(r.stage==2);if(mode==4||mode==8||mode==9)assert(r.stage==3);
   if(mode==5)assert(r.stage==4);if(mode==6||mode==7)assert(r.stage==5);
 }
 puts("PASS: bounded read sequence, poison stop, UA limit, GPT CRC and board geometry");
}
