// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
namespace t970_read {
struct Result {
  unsigned stage = 0, commands = 0, unitAttentions = 0;
  uint32_t lastLba = 0, blockBytes = 0, headerCrc = 0, entriesCrc = 0, entryCount = 0;
  uint64_t userdataFirst = 0, userdataLast = 0;
  bool inquiry = false, capacity = false, header = false, repeat = false, entries = false, geometry = false;
  char vendor[9] = {}, product[17] = {};
};
static uint32_t load32(const uint8_t *p) {
  return uint32_t(p[0]) | uint32_t(p[1])<<8 | uint32_t(p[2])<<16 | uint32_t(p[3])<<24;
}
static uint64_t load64(const uint8_t *p) { return load32(p) | uint64_t(load32(p+4))<<32; }
// Port: command(CDB,length,bytes) uses only device-to-host or no-data,
// data(), healthy(), sense(), and the existing production GPT CRC helper.
// Workspace is CPU-owned, separate from retained DMA, at least 20 KiB.
template <class Port>
static Result run(Port &p, uint8_t *workspace)
{
  Result r;
  auto command = [&](const uint8_t *cdb, unsigned length, unsigned bytes) {
    if (!p.healthy()) return false;
    ++r.commands;
    if (p.command(cdb,length,bytes)) return p.healthy();
    // One completed UNIT ATTENTION may be consumed. Never retry timeout,
    // protocol/fatal failure or NOT READY; healthy() excludes poisoned DMA.
    if (!p.healthy() || (p.sense() >> 16) != 6 || r.unitAttentions) return false;
    ++r.unitAttentions; ++r.commands;
    return p.command(cdb,length,bytes) && p.healthy();
  };
  auto read = [&](uint32_t lba, uint16_t blocks) {
    uint8_t cdb[10] = {0x28,0,uint8_t(lba>>24),uint8_t(lba>>16),uint8_t(lba>>8),uint8_t(lba),0,uint8_t(blocks>>8),uint8_t(blocks),0};
    return blocks && lba <= r.lastLba && uint32_t(blocks-1) <= r.lastLba-lba && command(cdb,10,blocks*4096U);
  };
  r.stage = 1;
  uint8_t inq[6] = {0x12,0,0,0,36,0};
  if (!command(inq,6,36)) return r;
  const uint8_t *data = p.data();
  if (data[0] != 0 || data[4] < 31) return r; // Connected direct-access LUN, full standard fields.
  for(unsigned i=0;i<8;++i) r.vendor[i] = data[8+i]>=32 && data[8+i]<127 ? data[8+i] : '.';
  for(unsigned i=0;i<16;++i) r.product[i] = data[16+i]>=32 && data[16+i]<127 ? data[16+i] : '.';
  r.inquiry = true; r.stage = 2;
  uint8_t cap[10] = {0x25};
  if (!command(cap,10,8)) return r;
  data = p.data();
  r.lastLba = uint32_t(data[0])<<24 | uint32_t(data[1])<<16 | uint32_t(data[2])<<8 | data[3];
  r.blockBytes = uint32_t(data[4])<<24 | uint32_t(data[5])<<16 | uint32_t(data[6])<<8 | data[7];
  if (r.blockBytes != 4096 || r.lastLba == 0xffffffff || r.lastLba < 62458874) return r;
  r.capacity = true; r.stage = 3;
  if (!read(1,1)) return r;
  data = p.data();
  const uint8_t signature[8] = {'E','F','I',' ','P','A','R','T'};
  for(unsigned i=0;i<8;++i) if(data[i]!=signature[i]) return r;
  uint32_t headerBytes = load32(data+12);
  if(load32(data+8)!=0x10000 || headerBytes<92 || headerBytes>4096 || load32(data+20) ||
     load64(data+24)!=1 || load64(data+32)!=r.lastLba ||
     p.crc(data,headerBytes,true)!=load32(data+16)) return r;
  const uint64_t arrayLba = load64(data+72), firstUsable = load64(data+40), lastUsable = load64(data+48);
  r.entryCount = load32(data+80); r.headerCrc = load32(data+16); r.entriesCrc = load32(data+88);
  if(!r.entryCount || r.entryCount>128 || load32(data+84)!=128 || arrayLba<2 ||
     firstUsable>lastUsable || lastUsable>=r.lastLba) return r;
  unsigned arrayBytes = r.entryCount*128, arrayBlocks = (arrayBytes+4095)/4096;
  if(arrayLba>r.lastLba || arrayBlocks>r.lastLba-arrayLba || arrayLba+arrayBlocks>firstUsable) return r;
  for(unsigned i=0;i<4096;++i) workspace[i]=data[i];
  r.header = true; r.stage = 4;
  if (!read(1,1)) return r;
  data = p.data();
  for(unsigned i=0;i<4096;++i) if(workspace[i]!=data[i]) return r;
  r.repeat = true; r.stage = 5;
  if (!read(uint32_t(arrayLba),uint16_t(arrayBlocks))) return r;
  data = p.data();
  if(p.crc(data,arrayBytes,false)!=r.entriesCrc) return r;
  r.entries = true;
  unsigned found=0;
  for(unsigned i=0;i<r.entryCount;++i) {
    const uint8_t *e=data+i*128;
    bool used=false; for(unsigned j=0;j<16;++j) used |= e[j]!=0;
    if(!used) continue;
    uint64_t first=load64(e+32),last=load64(e+40);
    if(first>last || first<firstUsable || last>lastUsable) return r;
    const char name[]="userdata"; bool match=true;
    for(unsigned j=0;j<36;++j) {
      uint8_t ch=j<8 ? uint8_t(name[j]):0;
      if(e[56+2*j]!=ch || e[57+2*j]) match=false;
    }
    if(match) {++found;r.userdataFirst=first;r.userdataLast=last;}
  }
  // From this target's captured Android GPT, never from another device.
  if(found!=1 || r.userdataFirst!=2969600 || r.userdataLast!=62458874) return r;
  r.geometry=true; r.stage=6;
  return r;
}
} // namespace t970_read
