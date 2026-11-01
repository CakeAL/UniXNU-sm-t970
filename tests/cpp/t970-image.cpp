#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "T970ImageTest.h"
struct Port {
 unsigned calls=0,current=0,mode=0;bool poisoned=false;uint8_t dummy[1]={};
 bool healthy(){return !poisoned;}
 bool read(uint32_t lba,unsigned blocks){
   assert(!poisoned);current=calls/2;assert(current<7);
   const auto &s=t970_image::samples[current];assert(lba==s.lba&&blocks==s.blocks);
   assert(lba>=2969600&&lba+blocks-1<=62458874&&blocks<=32);
   ++calls;if(mode==1&&calls==4){poisoned=true;return false;}return true;
 }
 const uint8_t *data(){return dummy;}
 void sha(const uint8_t *,unsigned bytes,uint8_t out[32]){
  assert(bytes==t970_image::samples[current].blocks*4096);
  memcpy(out,t970_image::samples[current].digest,32);
  if(mode==2&&calls==3)out[0]^=1;
  if(mode==3&&calls==2)out[31]^=1;
 }
};
int main(){for(unsigned mode=0;mode<4;++mode){Port p;p.mode=mode;auto r=t970_image::run(p);
 if(mode==0)assert(r.success&&r.reads==14&&p.calls==14);
 else assert(!r.success&&p.calls<=4);
 if(mode==1)assert(p.poisoned&&p.calls==4);
 }puts("PASS: image sample sequence, mismatch refusal, timeout quarantine");}
