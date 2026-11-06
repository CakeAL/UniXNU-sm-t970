# T970 8 GiB：托管范围改从 ADT 取 v86

v85 只改了 ADT 的 `dram-size`，实机 `pages=` 仍是 `0x79dad`（约 1949 MiB）。原因在 `boot_args`：`memSize` 和 `memSizeActual` 都是 `uint32_t`（`pexpert/pexpert/arm/boot.h`），8 GiB 无法表示；`arm_init` 用 `args->memSize` 算 `gPhysSize`（`arm_init_sptm.c:1551`），ADT 的值只进了 `gDramSize`。

v86 加内核补丁 `t970-8g-managed-range.patch`，把托管大小、`real_phys_size` 和 `mem_actual` 的来源改为 64 位的 `gDramSize`（ADT `/chosen/dram-size`，已是 8 GiB），`boot_args` 与 Loader 不动。保留 v85 的 32 页引导页表补丁和 8 GiB ADT。

BOOT 哈希 `3f5065adcc3ddf6d558d8583815fdda1954d5b903d859d3f7cc0650af62a3780`，内核 `95d5d45e`，ADT 与 v85 相同（`be41464a`），种子、配置、信任缓存、固件和分区尾部均未变。Heimdall 确认上传并请求重启。

实机待确认：`pages=` 应升到约 1.9M 页（7.9 GiB）。
