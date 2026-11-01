// SPDX-License-Identifier: BSD-2-Clause-Patent
// SM8250/kona diagnostic offsets, checked against the Samsung SM8250 kernel
// ad129ac77e9d871770d61f7bd219a836d7f35b74 drivers/clk/qcom/gcc-kona.c.
// The captured T970 DT selects kona GCC. See handoff-readonly/clock-source.json.
// These constants authorize observation only, not clock or reset writes.
#ifndef NATIVE_UFS_GCC_UFS_H
#define NATIVE_UFS_GCC_UFS_H

// Physical windows from the captured T970 DT.
#define GCC_BASE                      0x00100000ULL
#define UFS_HC_BASE                   0x01d84000ULL
#define UFS_HC_SIZE                   0x3000ULL

#define GCC_UFS_PHY_GDSCR             0x77004
#define GCC_UFS_PHY_AXI_ENABLE        0x77010
#define GCC_UFS_PHY_AHB_ENABLE        0x77018
#define GCC_UFS_PHY_TX_SYMBOL0_ENABLE 0x7701c
#define GCC_UFS_PHY_RX_SYMBOL0_ENABLE 0x77020
#define GCC_UFS_PHY_UNIPRO_CORE_ENABLE 0x7705c
#define GCC_UFS_PHY_ICE_CORE_ENABLE   0x77064
#define GCC_UFS_PHY_PHY_AUX_ENABLE    0x7709c
#define GCC_UFS_PHY_RX_SYMBOL1_ENABLE 0x770b8
#define GCC_AGGRE_UFS_PHY_AXI_ENABLE  0x770cc

#define GCC_UFS_BRANCH_ENABLE_BIT     0x1U

// A HW-gated idle branch may report CLK_OFF; the read-only handoff diagnostic
// conservatively skips HCI in that case. No separate SM8550 memory-PHY GDSC is
// mapped on this board. RPMh/TCSR/QMP-PHY programming remains unqualified.
#endif
