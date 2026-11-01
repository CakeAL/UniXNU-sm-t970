// SPDX-License-Identifier: BSD-2-Clause-Patent
#pragma once
#include "GccUfs.h"
#include "T970SmmuReport.h"

// Read callbacks only: no clocks, queues, SMMU contexts or storage are changed.
namespace t970_ufs {
struct Clocks {
  bool mapped = false;
  uint32_t gdsc = 0, axi = 0, ahb = 0, unipro = 0, ice = 0, aux = 0;
  uint32_t tx = 0, rx0 = 0, rx1 = 0, aggre = 0;
};
template <class Read>
static Clocks collectClocks(Read read)
{
  Clocks c;
  c.mapped = true;
  c.gdsc = read(GCC_UFS_PHY_GDSCR - 0x77000);
  c.axi = read(GCC_UFS_PHY_AXI_ENABLE - 0x77000);
  c.ahb = read(GCC_UFS_PHY_AHB_ENABLE - 0x77000);
  c.unipro = read(GCC_UFS_PHY_UNIPRO_CORE_ENABLE - 0x77000);
  c.ice = read(GCC_UFS_PHY_ICE_CORE_ENABLE - 0x77000);
  c.aux = read(GCC_UFS_PHY_PHY_AUX_ENABLE - 0x77000);
  c.tx = read(GCC_UFS_PHY_TX_SYMBOL0_ENABLE - 0x77000);
  c.rx0 = read(GCC_UFS_PHY_RX_SYMBOL0_ENABLE - 0x77000);
  c.rx1 = read(GCC_UFS_PHY_RX_SYMBOL1_ENABLE - 0x77000);
  c.aggre = read(GCC_AGGRE_UFS_PHY_AXI_ENABLE - 0x77000);
  return c;
}
static bool canReadController(const Clocks &c)
{
  // Strictly skip even HW-gated idle branches. A skipped read is not evidence
  // that the controller is broken; no force-on vote is made by this observer.
  return c.mapped && c.gdsc != 0xffffffffU && (c.gdsc & 0x80000000U) &&
    (c.axi & 0x80000001U) == 1 && (c.ahb & 0x80000001U) == 1;
}
struct Controller {
  unsigned state = 0; // 0=gated, 1=read, 2=HCI map failure, 3=GCC map failure.
  uint32_t cap = 0, version = 0, is = 0, hcs = 0, hce = 0;
  uint32_t listLow = 0, listHigh = 0, rsr = 0, doorbell = 0, tmRsr = 0, tmDoorbell = 0;
};
template <class Read>
static Controller collectController(const Clocks &clocks, Read read)
{
  Controller h;
  if (!canReadController(clocks)) return h;
  h.cap = read(0x00); h.version = read(0x08); h.is = read(0x20);
  h.hcs = read(0x30); h.hce = read(0x34);
  h.listLow = read(0x50); h.listHigh = read(0x54);
  h.doorbell = read(0x58); h.rsr = read(0x60);
  h.tmDoorbell = read(0x78); h.tmRsr = read(0x80);
  h.state = 1;
  return h;
}

static bool format(char *text, size_t capacity, const t970_smmu::Report &r,
                   const Clocks &c, const Controller &h)
{
  if (!capacity) return false;
  text[0] = 0;
  size_t used = 0;
  auto append = [&](const char *fmt, auto... arguments) {
    int n = snprintf(text + used, capacity - used, fmt, arguments...);
    if (n < 0 || static_cast<size_t>(n) >= capacity - used) return false;
    used += static_cast<size_t>(n);
    return true;
  };
  if (!append("%s", "T970 UFS handoff RO (no writes)\n") ||
      !append("GCC gdsc=%08x axi@10=%08x ahb@18=%08x uni@5c=%08x ice@64=%08x aggre@cc=%08x\n",
              c.gdsc, c.axi, c.ahb, c.unipro, c.ice, c.aggre) ||
      !append("GCC aux@9c=%08x tx@1c=%08x rx0@20=%08x rx1@b8=%08x gccMap=%u HCstate=%u\n",
              c.aux, c.tx, c.rx0, c.rx1, unsigned(c.mapped), h.state) ||
      !append("HCI cap=%08x ver=%08x hce=%08x hcs=%08x IS=%08x\n",
              h.cap, h.version, h.hce, h.hcs, h.is) ||
      !append("QUE list=%08x%08x rsr=%08x db=%08x tmRsr=%08x tmDb=%08x\n",
              h.listHigh, h.listLow, h.rsr, h.doorbell, h.tmRsr, h.tmDoorbell) ||
      !append("SMMU cr0=%08x id0=%08x id1=%08x id2=%08x gf=%08x\n",
              r.scr0, r.id0, r.id1, r.id2, r.gfsr) ||
      !append("groups=%u scanned=%u valid=%u CB=%u off=%llx geom=%u IDok=%u SMS=%u EXID=%u shift=%u\n",
              r.groups, r.scanned, r.valid, r.banks, static_cast<unsigned long long>(r.contextOffset),
              unsigned(r.geometryValid), unsigned(r.identityValid), unsigned(r.streamMatching),
              unsigned(r.extendedIds), r.pageShift) ||
      !append("%s", "slot(hex):SMR/S2CR (all scanned slots, six columns)\n")) return false;
  if (r.scanned > 128) return false;
  for (unsigned i = 0; i < r.scanned; ++i) {
    if (!append("%02x:%08x/%08x%c", i, r.streams[i].smr, r.streams[i].s2cr,
                (i + 1) % 6 == 0 || i + 1 == r.scanned ? '\n' : ' ')) return false;
  }
  return append("END slots=%u\n", r.scanned);
}
} // namespace t970_ufs
