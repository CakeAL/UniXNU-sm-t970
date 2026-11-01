// SPDX-License-Identifier: BSD-2-Clause-Patent
// SM8250 UEFI UFS PHY bring-up for the T970 board package.
//
// The QMP UFS PHY tables come from the Linux phy-qcom-qmp-ufs driver
// (Sm8250UfsPhyTables.h); this file only sequences the GCC block, replays the
// tables and waits for the PCS to report ready.

#include <Uefi.h>
#include <Library/IoLib.h>
#include <Library/TimerLib.h>
#include <Library/DebugLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Protocol/GraphicsOutput.h>
#include <Library/DxeServicesTableLib.h>
#include <Library/ArmSmcLib.h>
#include <Library/PlatformUfsLib.h>

#include "Sm8250UfsPhyTables.h"

#define UFS_PHY_BASE       0x01D87000ULL
#define GCC_UFS_PHY_BCR    0x00077000
#define GCC_UFS_PHY_GDSCR  0x00077004
#define GCC_UFS_PHY_AXI    0x00077018
#define GCC_UFS_PHY_AHB    0x00077024
#define GCC_UFS_PHY_UNIPRO 0x00077068
#define GCC_UFS_PHY_ICE    0x00077074
#define UFS_PHY_SERDES_OFF 0x000
#define UFS_PHY_TX_OFF     0x400
#define UFS_PHY_RX_OFF     0x600
#define UFS_PHY_PCS_OFF    0xC00
#define UFS_PCS_READY      0x180
#define UFS_PCS_READY_BIT  BIT0
#define T970_UFS_STATUS    0x9FF80000ULL
#define T970_UFS_MAGIC     0x54393730U

STATIC
UINT64
ScmCall (
  IN UINT64  Service,
  IN UINT64  Command,
  IN UINT64  Arg0,
  IN UINT64  Arg1
  )
{
  ARM_SMC_ARGS  Args;

  ZeroMem (&Args, sizeof (Args));
  Args.Arg0 = 0x02000000ULL | (((Service & 0xff) << 8) | (Command & 0xff));
  Args.Arg1 = 2;
  Args.Arg2 = Arg0;
  Args.Arg3 = Arg1;
  ArmCallSmc (&Args);
  return Args.Arg0;
}

STATIC
VOID
Marker (
  IN UINT8  Red,
  IN UINT8  Green,
  IN UINT8  Blue,
  IN UINTN  X
  )
{
  EFI_GRAPHICS_OUTPUT_PROTOCOL  *Gop = NULL;
  EFI_GRAPHICS_OUTPUT_BLT_PIXEL  Pixel;

  if (EFI_ERROR (gBS->LocateProtocol (&gEfiGraphicsOutputProtocolGuid, NULL, (VOID **)&Gop)) || Gop == NULL) {
    return;
  }
  Pixel.Red = Red; Pixel.Green = Green; Pixel.Blue = Blue; Pixel.Reserved = 0;
  Gop->Blt (Gop, &Pixel, EfiBltVideoFill, 0, 0, X, 10, 50, 18, 0);
}

STATIC
VOID
Replay (
  IN UINTN                                  Base,
  IN UINTN                                  Offset,
  IN CONST struct t970_ufs_phy_reg         *Table,
  IN UINTN                                  Count
  )
{
  UINTN Index;

  for (Index = 0; Index < Count; Index++) {
    MmioWrite32 (Base + Offset + Table[Index].offset, Table[Index].value);
  }
}

STATIC
EFI_STATUS
WaitSet (
  IN UINTN   Base,
  IN UINTN   Offset,
  IN UINT32  Mask,
  IN UINTN   Loops
  )
{
  UINTN Index;

  for (Index = 0; Index < Loops; Index++) {
    if ((MmioRead32 (Base + Offset) & Mask) == Mask) {
      return EFI_SUCCESS;
    }
    MicroSecondDelay (10);
  }
  return EFI_TIMEOUT;
}

EFI_STATUS
EFIAPI
UfsBoardInit (
  IN struct UfsHost *Ufs
  )
{
  EFI_STATUS  Status;

  (VOID)Ufs;
  MmioWrite32 (T970_UFS_STATUS, T970_UFS_MAGIC);
  MmioWrite32 (T970_UFS_STATUS + 4, 1);
  Marker (255, 0, 255, 10);

  /* Release the UFS PHY block reset and wait for the GDSC to report on. */
  EFI_STATUS MapStatus;
  MapStatus = gDS->AddMemorySpace (EfiGcdMemoryTypeMemoryMappedIo, 0x00100000, 0x00080000, EFI_MEMORY_UC);
  Marker (MapStatus == EFI_SUCCESS ? 255 : 255, MapStatus == EFI_SUCCESS ? 255 : 128, MapStatus == EFI_SUCCESS ? 255 : 0, 70);
  MapStatus = gDS->SetMemorySpaceAttributes (0x00100000, 0x00080000, EFI_MEMORY_UC);
  Marker (MapStatus == EFI_SUCCESS ? 0 : 255, MapStatus == EFI_SUCCESS ? 255 : 0, MapStatus == EFI_SUCCESS ? 255 : 0, 130);
  gDS->AddMemorySpace (EfiGcdMemoryTypeMemoryMappedIo, UFS_PHY_BASE, 0x2000, EFI_MEMORY_UC);
  gDS->SetMemorySpaceAttributes (UFS_PHY_BASE, 0x2000, EFI_MEMORY_UC);
  /* UFS controller and ICE window used by UfsDxe after this point. */
  gDS->AddMemorySpace (EfiGcdMemoryTypeMemoryMappedIo, 0x01D84000, 0x0002C000, EFI_MEMORY_UC);
  gDS->SetMemorySpaceAttributes (0x01D84000, 0x0002C000, EFI_MEMORY_UC);
  Marker (0, 200, 200, 190);
  /* ABL already brought UFS up; skip the GCC writes that hang non-secure. */

  Replay (UFS_PHY_BASE, UFS_PHY_SERDES_OFF, t970_ufs_phy_serdes, ARRAY_SIZE (t970_ufs_phy_serdes));
  Marker (255, 255, 0, 250);
  Replay (UFS_PHY_BASE, UFS_PHY_TX_OFF, t970_ufs_phy_tx, ARRAY_SIZE (t970_ufs_phy_tx));
  Marker (255, 128, 0, 310);
  Replay (UFS_PHY_BASE, UFS_PHY_RX_OFF, t970_ufs_phy_rx, ARRAY_SIZE (t970_ufs_phy_rx));
  Marker (128, 0, 255, 370);
  Replay (UFS_PHY_BASE, UFS_PHY_PCS_OFF, t970_ufs_phy_pcs, ARRAY_SIZE (t970_ufs_phy_pcs));
  Marker (0, 128, 255, 430);
  Replay (UFS_PHY_BASE, UFS_PHY_TX_OFF, t970_ufs_phy_hs_g4_tx, ARRAY_SIZE (t970_ufs_phy_hs_g4_tx));
  Marker (0, 0, 255, 490);
  Replay (UFS_PHY_BASE, UFS_PHY_RX_OFF, t970_ufs_phy_hs_g4_rx, ARRAY_SIZE (t970_ufs_phy_hs_g4_rx));
  Marker (0, 200, 0, 550);
  Replay (UFS_PHY_BASE, UFS_PHY_PCS_OFF, t970_ufs_phy_hs_g4_pcs, ARRAY_SIZE (t970_ufs_phy_hs_g4_pcs));

  Status = WaitSet (UFS_PHY_BASE, UFS_PHY_PCS_OFF + UFS_PCS_READY, UFS_PCS_READY_BIT, 2000);
  if (EFI_ERROR (Status)) {
    DEBUG ((DEBUG_ERROR, "UfsBoardInit: PCS not ready\n"));
    MmioWrite32 (T970_UFS_STATUS + 4, 0x20);
    Marker (255, 128, 0, 610);
    return Status;
  }
  MmioWrite32 (T970_UFS_STATUS + 4, 0x30);
  Marker (16, 16, 16, 620);

  /* Ask the secure world to hand the UFS SMMU configuration back. */
  UINT64 ScmZero = ScmCall (0x0c, 0x02, 0, 0);
  UINT64 ScmOne  = ScmCall (0x0c, 0x02, 1, 0);
  Marker (ScmZero == 0 ? 0 : 255, ScmZero == 0 ? 255 : 0, ScmZero == 0 ? 0 : 0, 660);
  Marker (ScmOne == 0 ? 0 : 255, ScmOne == 0 ? 255 : 0, ScmOne == 0 ? 0 : 0, 700);
  MmioWrite32 (T970_UFS_STATUS + 8, (UINT32)ScmZero);
  MmioWrite32 (T970_UFS_STATUS + 12, (UINT32)ScmOne);

  Marker (0, 255, 0, 610);
  return EFI_SUCCESS;
}

UfsCalError
UfsCalInit (
  IN struct UfsCalParam *Param
  )
{
  (VOID)Param;
  return UFS_CAL_NO_ERROR;
}

UfsCalError
UfsCalPreLink (
  IN struct UfsCalParam *Param
  )
{
  (VOID)Param;
  return UFS_CAL_NO_ERROR;
}

UfsCalError
UfsCalPostLink (
  IN struct UfsCalParam *Param
  )
{
  (VOID)Param;
  return UFS_CAL_NO_ERROR;
}

UfsCalError
UfsCalPrePmc (
  IN struct UfsCalParam *Param
  )
{
  (VOID)Param;
  return UFS_CAL_NO_ERROR;
}

UfsCalError
UfsCalPostPmc (
  IN struct UfsCalParam *Param
  )
{
  (VOID)Param;
  return UFS_CAL_NO_ERROR;
}

UINT8
UfsCalGetTargetBoard (
  VOID
  )
{
  return HOST_EMBD;
}
