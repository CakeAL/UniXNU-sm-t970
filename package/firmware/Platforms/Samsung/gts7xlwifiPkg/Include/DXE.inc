# Derived from the pinned r8q reference; vendor assets are from this T970 XBL.
  INF MdeModulePkg/Core/Dxe/DxeMain.inf
  INF MdeModulePkg/Universal/PCD/Dxe/Pcd.inf
  INF ArmPkg/Drivers/CpuDxe/CpuDxe.inf
  INF MdeModulePkg/Core/RuntimeDxe/RuntimeDxe.inf
  INF MdeModulePkg/Universal/SecurityStubDxe/SecurityStubDxe.inf

  INF gts7xlwifiPkg/Drivers/ScmDxe/ScmDxe.inf
  # TzDxe asserts in QseeComDxe (EFI_DEVICE_ERROR) before the menu; excluded for bring-up.
  #  INF gts7xlwifiPkg/Drivers/TzDxe/TzDxe.inf

  INF MdeModulePkg/Universal/WatchdogTimerDxe/WatchdogTimer.inf
  INF MdeModulePkg/Universal/CapsuleRuntimeDxe/CapsuleRuntimeDxe.inf
  INF MdeModulePkg/Universal/ReportStatusCodeRouter/RuntimeDxe/ReportStatusCodeRouterRuntimeDxe.inf
  INF MdeModulePkg/Universal/StatusCodeHandler/RuntimeDxe/StatusCodeHandlerRuntimeDxe.inf
  INF MdeModulePkg/Universal/Variable/RuntimeDxe/VariableRuntimeDxe.inf
  INF EmbeddedPkg/EmbeddedMonotonicCounter/EmbeddedMonotonicCounter.inf
  INF EmbeddedPkg/SimpleTextInOutSerial/SimpleTextInOutSerial.inf
  INF MdeModulePkg/Universal/ResetSystemRuntimeDxe/ResetSystemRuntimeDxe.inf
  INF EmbeddedPkg/RealTimeClockRuntimeDxe/RealTimeClockRuntimeDxe.inf
  INF EmbeddedPkg/MetronomeDxe/MetronomeDxe.inf
  INF MdeModulePkg/Universal/PrintDxe/PrintDxe.inf
  INF MdeModulePkg/Universal/DevicePathDxe/DevicePathDxe.inf
  INF MdeModulePkg/Universal/Console/ConPlatformDxe/ConPlatformDxe.inf
  INF MdeModulePkg/Universal/Console/ConSplitterDxe/ConSplitterDxe.inf
  INF MdeModulePkg/Universal/Console/GraphicsConsoleDxe/GraphicsConsoleDxe.inf
  INF MdeModulePkg/Universal/HiiDatabaseDxe/HiiDatabaseDxe.inf

  INF gts7xlwifiPkg/Drivers/EnvDxe/EnvDxe.inf

  INF ArmPkg/Drivers/ArmGicDxe/ArmGicDxe.inf
  INF ArmPkg/Drivers/TimerDxe/TimerDxe.inf

  INF gts7xlwifiPkg/Drivers/ChipInfo/ChipInfo.inf
  INF gts7xlwifiPkg/Drivers/SmemDxe/SmemDxe.inf
  INF gts7xlwifiPkg/Drivers/ULogDxe/ULogDxe.inf
  INF gts7xlwifiPkg/Drivers/NpaDxe/NpaDxe.inf
  INF gts7xlwifiPkg/Drivers/CmdDbDxe/CmdDbDxe.inf
  INF gts7xlwifiPkg/Drivers/PwrUtilsDxe/PwrUtilsDxe.inf
  INF gts7xlwifiPkg/Drivers/RpmhDxe/RpmhDxe.inf
!if $(USE_CUSTOM_DISPLAY_DRIVER) == 1
  INF gts7xlwifiPkg/Drivers/CPRDxe/CPRDxe.inf
!endif
  INF gts7xlwifiPkg/Drivers/PdcDxe/PdcDxe.inf

  INF MdeModulePkg/Universal/Disk/DiskIoDxe/DiskIoDxe.inf
  INF MdeModulePkg/Universal/Disk/PartitionDxe/PartitionDxe.inf
  INF FatPkg/EnhancedFatDxe/Fat.inf
  INF MdeModulePkg/Universal/Disk/UnicodeCollation/EnglishDxe/EnglishDxe.inf

  INF gts7xlwifiPkg/Drivers/DALSys/DALSys.inf
  INF gts7xlwifiPkg/Drivers/ClockDxe/ClockDxe.inf
  INF gts7xlwifiPkg/Drivers/VcsDxe/VcsDxe.inf
  INF gts7xlwifiPkg/Drivers/HALIOMMU/HALIOMMU.inf
  INF gts7xlwifiPkg/Drivers/HWIODxeDriver/HWIODxeDriver.inf
  INF gts7xlwifiPkg/Drivers/GpiDxe/GpiDxe.inf
  INF gts7xlwifiPkg/Drivers/I2C/I2C.inf
  INF gts7xlwifiPkg/Drivers/SPMI/SPMI.inf
  INF gts7xlwifiPkg/Drivers/DALTLMM/DALTLMM.inf
  INF gts7xlwifiPkg/Drivers/FeatureEnablerDxe/FeatureEnablerDxe.inf

!if $(USE_CUSTOM_DISPLAY_DRIVER) == 1
  INF gts7xlwifiPkg/Drivers/DisplayDxe/DisplayDxe.inf
!else
  INF SiliciumPkg/Drivers/SimpleFbDxe/SimpleFbDxe.inf
!endif

  INF gts7xlwifiPkg/Drivers/PlatformInfoDxeDriver/PlatformInfoDxeDriver.inf
  INF gts7xlwifiPkg/Drivers/ButtonsDxe/ButtonsDxe.inf
  INF gts7xlwifiPkg/Drivers/PmicDxe/PmicDxe.inf
  INF gts7xlwifiPkg/Drivers/UsbPwrCtrlDxe/UsbPwrCtrlDxe.inf
  INF gts7xlwifiPkg/Drivers/AdcDxe/AdcDxe.inf
  INF gts7xlwifiPkg/Drivers/TsensDxe/TsensDxe.inf
  INF gts7xlwifiPkg/Drivers/LimitsDxe/LimitsDxe.inf
  INF gts7xlwifiPkg/Drivers/DDRInfoDxe/DDRInfoDxe.inf


  INF gts7xlwifiPkg/Drivers/HashDxe/HashDxe.inf
  INF gts7xlwifiPkg/Drivers/CipherDxe/CipherDxe.inf
  INF gts7xlwifiPkg/Drivers/MacDxe/MacDxe.inf
  INF gts7xlwifiPkg/Drivers/RngDxe/RngDxe.inf

  INF MdeModulePkg/Universal/BdsDxe/BdsDxe.inf

  INF gts7xlwifiPkg/Drivers/Ccic/Ccic.inf
  INF gts7xlwifiPkg/Drivers/Muic/Muic.inf
  INF gts7xlwifiPkg/Drivers/Chg/Chg.inf
  INF gts7xlwifiPkg/Drivers/SubPmic/SubPmic.inf
  INF gts7xlwifiPkg/Drivers/Redriver/Redriver.inf
  # PIL needs partition access; no UFS driver yet. Excluded for bring-up.
  #  INF gts7xlwifiPkg/Drivers/PILDxe/PILDxe.inf
  # PIL needs partition access; no UFS driver yet. Excluded for bring-up.
  #  INF gts7xlwifiPkg/Drivers/PILProxyDxe/PILProxyDxe.inf
  INF gts7xlwifiPkg/Drivers/SPSSDxe/SPSSDxe.inf
  INF gts7xlwifiPkg/Drivers/ShmBridgeDxe/ShmBridgeDxe.inf
