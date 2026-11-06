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
