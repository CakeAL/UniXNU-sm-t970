##
#  Copyright (c) 2011 - 2022, ARM Limited. All rights reserved.
#  Copyright (c) 2014, Linaro Limited. All rights reserved.
#  Copyright (c) 2015 - 2020, Intel Corporation. All rights reserved.
#  Copyright (c) 2018, Bingxing Wang. All rights reserved.
#  Copyright (c) Microsoft Corporation.
#
#  SPDX-License-Identifier: BSD-2-Clause-Patent
##

################################################################################
#
# Defines Section - statements that will be processed to create a Makefile.
#
################################################################################
[Defines]
  PLATFORM_NAME                  = gts7xlwifi
  PLATFORM_GUID                  = F0157C78-DB4A-5C55-A9B7-98B6651579D5
  PLATFORM_VERSION               = 0.1
  DSC_SPECIFICATION              = 0x00010005
  OUTPUT_DIRECTORY               = Build/gts7xlwifiPkg
  SUPPORTED_ARCHITECTURES        = AARCH64
  BUILD_TARGETS                  = RELEASE|DEBUG
  SKUID_IDENTIFIER               = DEFAULT
  FLASH_DEFINITION               = gts7xlwifiPkg/gts7xlwifi.fdf
  USE_CUSTOM_DISPLAY_DRIVER      = 0
  ENABLE_SECUREBOOT              = 0

  #
  # 0 = SM8250
  # 1 = SM8250-AB
  # 2 = SM8250-AC
  #
  SOC_TYPE                       = 1

!include KonaPkg/KonaPkg.dsc.inc

[PcdsFixedAtBuild]
  #
  # DDR Memory
  #
  gArmTokenSpaceGuid.PcdSystemMemoryBase|0x80000000

  #
  # UEFI Stack
  #
  gArmPlatformTokenSpaceGuid.PcdCPUCoresStackBase|0x9FF90000
  gArmPlatformTokenSpaceGuid.PcdCPUCorePrimaryStackSize|0x40000

  #
  # SMBIOS
  #
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemManufacturer|"Samsung"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemRetailModel|"gts7xlwifi"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemModel|"Galaxy Tab S7+ Wi-Fi"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemRetailSku|"SM-T970"
  gSiliciumPkgTokenSpaceGuid.PcdSmbiosSystemBoardModel|"Galaxy Tab S7+ Wi-Fi"

  #
  # Simple Frame Buffer
  #
  gSiliciumPkgTokenSpaceGuid.PcdFrameBufferWidth|2800
  gSiliciumPkgTokenSpaceGuid.PcdFrameBufferHeight|1752
  gSiliciumPkgTokenSpaceGuid.PcdFrameBufferColorDepth|32

  #
  # Platform PEI
  #
  gQcomPkgTokenSpaceGuid.PcdPlatformType|"LA"

[LibraryClasses]
  UniXNULib|UniXNUPkg/Library/UniXNULib/UniXNULib.inf
  #
  # Memory Libraries
  #
  MemoryMapLib|gts7xlwifiPkg/Library/MemoryMapLib/MemoryMapLib.inf

  #
  # QCOM Libraries
  #
  ConfigurationMapLib|gts7xlwifiPkg/Library/ConfigurationMapLib/ConfigurationMapLib.inf

[Components]
  #
  # ACPI Tables
  #
  #gts7xlwifi/AcpiTables.inf

  # Vendor modules retain their T970 GUIDs, PE32 bodies and DEPEX.
  gts7xlwifiPkg/Drivers/AdcDxe/AdcDxe.inf
  gts7xlwifiPkg/Drivers/ButtonsDxe/ButtonsDxe.inf
  gts7xlwifiPkg/Drivers/CPRDxe/CPRDxe.inf
  gts7xlwifiPkg/Drivers/Ccic/Ccic.inf
  gts7xlwifiPkg/Drivers/Chg/Chg.inf
  gts7xlwifiPkg/Drivers/ChipInfo/ChipInfo.inf
  gts7xlwifiPkg/Drivers/CipherDxe/CipherDxe.inf
  gts7xlwifiPkg/Drivers/ClockDxe/ClockDxe.inf
  gts7xlwifiPkg/Drivers/CmdDbDxe/CmdDbDxe.inf
  gts7xlwifiPkg/Drivers/DALSys/DALSys.inf
  gts7xlwifiPkg/Drivers/DALTLMM/DALTLMM.inf
  gts7xlwifiPkg/Drivers/DDRInfoDxe/DDRInfoDxe.inf
  gts7xlwifiPkg/Drivers/DisplayDxe/DisplayDxe.inf
  gts7xlwifiPkg/Drivers/EnvDxe/EnvDxe.inf
  gts7xlwifiPkg/Drivers/FeatureEnablerDxe/FeatureEnablerDxe.inf
  gts7xlwifiPkg/Drivers/GpiDxe/GpiDxe.inf
  gts7xlwifiPkg/Drivers/HALIOMMU/HALIOMMU.inf
  gts7xlwifiPkg/Drivers/HWIODxeDriver/HWIODxeDriver.inf
  gts7xlwifiPkg/Drivers/HashDxe/HashDxe.inf
  gts7xlwifiPkg/Drivers/I2C/I2C.inf
  gts7xlwifiPkg/Drivers/LimitsDxe/LimitsDxe.inf
  gts7xlwifiPkg/Drivers/MacDxe/MacDxe.inf
  gts7xlwifiPkg/Drivers/Muic/Muic.inf
  gts7xlwifiPkg/Drivers/NpaDxe/NpaDxe.inf
  # PIL needs partition access; no UFS driver yet. Excluded for bring-up.
  #  gts7xlwifiPkg/Drivers/PILDxe/PILDxe.inf
  # PIL needs partition access; no UFS driver yet. Excluded for bring-up.
  #  gts7xlwifiPkg/Drivers/PILProxyDxe/PILProxyDxe.inf
  gts7xlwifiPkg/Drivers/PdcDxe/PdcDxe.inf
  gts7xlwifiPkg/Drivers/PlatformInfoDxeDriver/PlatformInfoDxeDriver.inf
  gts7xlwifiPkg/Drivers/PmicDxe/PmicDxe.inf
  gts7xlwifiPkg/Drivers/PwrUtilsDxe/PwrUtilsDxe.inf
  gts7xlwifiPkg/Drivers/Redriver/Redriver.inf
  gts7xlwifiPkg/Drivers/RngDxe/RngDxe.inf
  gts7xlwifiPkg/Drivers/RpmhDxe/RpmhDxe.inf
  gts7xlwifiPkg/Drivers/SPMI/SPMI.inf
  gts7xlwifiPkg/Drivers/SPSSDxe/SPSSDxe.inf
  gts7xlwifiPkg/Drivers/ScmDxe/ScmDxe.inf
  gts7xlwifiPkg/Drivers/ShmBridgeDxe/ShmBridgeDxe.inf
  gts7xlwifiPkg/Drivers/SmemDxe/SmemDxe.inf
  gts7xlwifiPkg/Drivers/SubPmic/SubPmic.inf
  gts7xlwifiPkg/Drivers/TsensDxe/TsensDxe.inf
  # TzDxe asserts in QseeComDxe (EFI_DEVICE_ERROR) before the menu; excluded for bring-up.
  #  gts7xlwifiPkg/Drivers/TzDxe/TzDxe.inf
  gts7xlwifiPkg/Drivers/ULogDxe/ULogDxe.inf
  gts7xlwifiPkg/Drivers/UsbPwrCtrlDxe/UsbPwrCtrlDxe.inf
  gts7xlwifiPkg/Drivers/VcsDxe/VcsDxe.inf

  # Required initrd, FAT/DiskIo and loader integration.
  UniXNUPkg/Application/UniXNU/UniXNU.inf
  UniXNUPkg/Driver/UniXNUDxe/UniXNUDxe.inf
  UniXNUPkg/Driver/UniXNURamDiskDxe/UniXNURamDiskDxe.inf
  DarwinBootPkg/Driver/DarwinBoot.inf

#
# Advanced Logger and the UniXNU firmware log exporter
# (https://unixnu.com/zh/porting/log-capture#firmware-setup).
#
# The SEC instance only initialises the hardware port: PcdAdvancedLoggerBase
# stays 0, so no fixed RAM address is invented. The DXE Core instance reserves
# PcdAdvancedLoggerPages (4 MiB by default) from the DXE heap and installs
# gAdvancedLoggerProtocolGuid, which is the exporter's Depex. Debug output is
# still written to SerialPortLib (FrameBufferSerialPortLib in DEBUG), so the
# panel diagnostics that already existed remain.
#
[PcdsFixedAtBuild]
  gUniXNUPkgTokenSpaceGuid.PcdUniXNUDeviceModel|"gts7xlwifi"

[LibraryClasses]
  AdvancedLoggerAccessLib|AdvLoggerPkg/Library/AdvancedLoggerAccessLib/AdvancedLoggerAccessLib.inf
  AdvancedLoggerHdwPortLib|AdvLoggerPkg/Library/AdvancedLoggerHdwPortLib/AdvancedLoggerHdwPortLib.inf
  QrEncoderLib|MsGraphicsPkg/Library/QrEncoderLib/QrEncoderLib.inf

[LibraryClasses.common.SEC]
  AdvancedLoggerLib|AdvLoggerPkg/Library/AdvancedLoggerLib/PeilessArm/AdvancedLoggerLib.inf

[LibraryClasses.common.DXE_CORE]
  AdvancedLoggerLib|AdvLoggerPkg/Library/AdvancedLoggerLib/DxeCore/AdvancedLoggerLib.inf

[LibraryClasses.common.DXE_DRIVER]
  AdvancedLoggerLib|AdvLoggerPkg/Library/AdvancedLoggerLib/Dxe/AdvancedLoggerLib.inf

[LibraryClasses.common.DXE_RUNTIME_DRIVER]
  AdvancedLoggerLib|AdvLoggerPkg/Library/AdvancedLoggerLib/Runtime/AdvancedLoggerLib.inf

[LibraryClasses.common.UEFI_DRIVER]
  AdvancedLoggerLib|AdvLoggerPkg/Library/AdvancedLoggerLib/Dxe/AdvancedLoggerLib.inf

[LibraryClasses.common.UEFI_APPLICATION]
  AdvancedLoggerLib|AdvLoggerPkg/Library/AdvancedLoggerLib/Dxe/AdvancedLoggerLib.inf

!if $(TARGET) == DEBUG
[LibraryClasses]
  AssertLib|AdvLoggerPkg/Library/AssertLib/AssertLib.inf
  DebugLib|AdvLoggerPkg/Library/BaseDebugLibAdvancedLogger/BaseDebugLibAdvancedLogger.inf
!endif

[Components]
  # Tools -> Advanced Logger, exported as OneSend QR frames.
  UniXNUPkg/Driver/AdvancedLogDxe/AdvancedLogDxe.inf
