# T970 8 GiB：托管范围改从 ADT 取 v87

v86 的补丁用了 `gDramSize ?: args->memSize`，但 `gDramSize` 要到 `arm_init` 调用
`arm_vm_init` **之后**才赋值（`arm_init_sptm.c:893`），`arm_vm_init` 里读到的还是 0，
所以 `pages=` 停在 `0x79dab`。

v87 在内核里改回“自己读 ADT”：`arm_vm_init` 开头用 `SecureDTLookupEntry(NULL,
"/chosen")` + `SecureDTGetProperty(chosen, "dram-size")` 取 64 位的 `dram_envelope`，
再用它算 `real_phys_size`、`gPhysSize`/`mem_size` 和 `mem_actual`；`boot_args`、
Loader、ADT 与 v85/v86 一致，不新增字段。

同时修掉 v86 构建失败的真实原因：补丁初版把属性长度声明成 `DTEntrySize`，而这一版
XNU 的 `SecureDTGetProperty` 用的是 `unsigned int *`（`pexpert/pexpert/device_tree.h:249`），
`arm_vm_init.c:1846` 报 `use of undeclared identifier 'length'`。现在按 `arm_init_sptm.c`
里既有写法声明 `unsigned int dt_entry_size` 与 `unsigned long const *dram_size`。

内核对上 21H461 的旧期望：`DT` 在 `PE_init_platform(FALSE, args)`（`arm_init.c:371`）
里已初始化，`arm_vm_init`（`:532`）在其后，读属性安全；读不到时退回 `args->memSize`，
即 v86 行为，不会更差。

## 构建与打包

- 内核：`evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe
  --gop-fork --output out/data-bringup/setup-8g-v87-build`，产物 `ea6ee2931140f3bbf8517c31321462d84bae0c1f1865e07059c4ca782566f9da`。
- 打包：`evidence/memory/8g-v87/prepare.py`，在 v86 BOOT 上只替换 `Payloads/kernel.macho`，
  入口探针补丁后内核 `2fab6d1d63e7253778cb86f15ae97799529ee6db82e836dad915b2f86afd648f`。
- BOOT `4351962f5393dc70c766f17942b23c577bf565262074063741a732befb3d5337`，基准 v86
  `3f5065ad`；ADT `be41464a`（仍是 8 GiB `dram-size`）、种子、配置、信任缓存、固件与
  分区尾部全部未变。
- Heimdall 确认上传 `BOOT` 并重启（`upload.json`）。

## 实机待确认

`pages=` 应从 `0x79dab` 升到约 `0x1E0000`–`0x1F0000`（7.5–7.8 GiB）。若仍不变，
说明 `dram-size` 在 `arm_vm_init` 时还读不到（DT 未初始化或属性名不同），下一次
改为打印 `dram_envelope` 与 DT 返回码，再定位。

## 实机结果：卡在品红条（失败）

刷入后停在第 2 阶段品红条（MMU 打开前），没有进入内核控制台，也没有运行时报告。
原因不是补丁语法，而是**改错了层**：内核把托管范围直接扩到物理 DRAM 的 8 GiB 信封，
而 DarwinBoot 实际只分配了约 2 GiB 的 owned window 并把 `boot_args.memSize` 设成它；
`arm_vm_init` 于是把窗口之外的保留区和空洞一并当作受管内存去建页表，启动早期就停了。

已回滚：`heimdall flash --BOOT out/data-bringup/setup-8g-v86/boot-partition.img`
（v86 `3f5065ad`），平板恢复正常。

## 下一步（v88 的正确层次）

1. `boot_args.memSize` / `memSizeActual` 在 arm64 头里是 **uint64**（`pexpert/pexpert/arm64/boot.h:58-58`），
   8 GiB 本来就能表达；之前按 `arm/boot.h` 的 uint32 判断是错的。
2. 托管大小 = DarwinBoot 的 owned window，窗口大小来自 ADT `/chosen/darwinboot-memory-size`
   （`darwinboot-memory-size`，`DarwinBoot.c:264`），当前被设成 2 GiB（v62）。
3. 板级 DTS 只声明了 2 GiB DRAM（`dts/sm-t970.dts:12`），而整机实测内存节点是三段：
   `0x80000000+0x3BB00000`、`0xC0000000+0xC0000000`、`0x180000000+0x100000000`。
4. 三段里只有最高 4 GiB `[0x180000000, 0x280000000)` 不被 stock 保留区占用；中间 3 GiB 段被
   `sec_debug_rdx_bootdev@0`（0x100000000 + 0xAD00000）切断，低段到 0xBBB00000 结束。
   所以单窗口最多约 4 GiB。要更多需要 XNU 多 bank 支持，属于后续工作。
5. v88 计划：撤掉本补丁，DTS 改成 stock 三段，ADT 把 `darwinboot-memory-size` 设到
   0xF0000000（3.75 GiB，留 256 MiB 余量），由 Loader 传正确的 `memSize`，内核不再改托管范围。
