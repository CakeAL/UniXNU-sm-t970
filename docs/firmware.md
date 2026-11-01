# SM-T970 固件输入与主机构建

本页最初记录 CPU0／initrd 固件的主机准备；后续已有多轮实机测试，以下早期范围按历史读取。
当前只读 SMMU 诊断复用精确哈希 `515105d7…` 的已测试 FD，不 dispatch 后加入的 UfsDxe／SCM 原型，
详见 [只读核查](smmu-readonly.md)。
`board.example` 已移除，只表示具体设备配置已填写，不能据此判定可启动。

## 固定源码和设备依据

- Mu-Silicium：`4bd8ae83bf37de41777f19e0777db70f59383a6d`。
- Mu_Basecore：`42d6d889f7c1f27e3226b44074b8a0ffe21cd988`。
- Mu、OEM 与嵌套子模块的提交见 `package/firmware/inputs.json`；准备工具逐一核对。
- `evidence/device-inputs/boot-firmware.json` 来自本机 T970ZCU2CVK1 的 XBL：
  校验 FV／FFS 头，解压 gzip 引导卷，记录 121 个 FFS 文件和 45 个平台区域。
- FD 为 `0x9fc00000 + 0x300000`；栈为 `0x9ff90000 + 0x40000`。
  `MemoryMapLib` 保留原厂数值，去掉会与 FV／FD／栈重叠的 Android `SEC LOG` scratch
  映射；Mu 的 `ValidateMemoryMap` 会拒绝此重叠。此调整不等于运行时所有权已验证。
- CPU 类型使用 SM8250-AB。面板的 2800×1752 来自实机；SimpleFb 的 stride／格式假设
  仍需要与启动时实际 framebuffer 对照，当前不能认定 GOP 可用。

DTS 从实测高内存段 `0x180000000 + 0x100000000` 中选择子区间
`0x200000000 + 0x80000000`（2 GiB），排除相机动态池允许使用的前 2 GiB。
检查工具对照 30 个静态保留区、13 个原厂动态池分配窗口及 45 个 XBL 区域检查不相交；原厂动态池仅供禁用外设的
来源审计，不在新固件中创建 Android CMA。真实 `GetMemoryMap` 与加载器分配另行验证。

## 取得并准备固件工作树

从设备仓库执行，首次使用时准备独立工作树：

```sh
git clone https://github.com/Project-Silicium/Mu-Silicium.git .cache/uefi-source/Mu-Silicium
git -C .cache/uefi-source/Mu-Silicium checkout --detach 4bd8ae83bf37de41777f19e0777db70f59383a6d
git -C .cache/uefi-source/Mu-Silicium submodule update --init --depth 1 -- Common/Mu Common/Mu_OEM_Sample Mu_Basecore
git -C .cache/uefi-source/Mu-Silicium/Mu_Basecore submodule update --init --depth 1 -- BaseTools/Source/C/BrotliCompress/brotli MdePkg/Library/BaseFdtLib/libfdt MdePkg/Library/MipiSysTLib/mipisyst MdeModulePkg/Library/BrotliCustomDecompressLib/brotli SecurityPkg/DeviceSecurity/SpdmLib/libspdm
```

若 Git 连接需要本机代理，可为对应 Git 命令加 `-c http.proxy=http://127.0.0.1:10808`。

已有 Magisk root、连接这一台 USB 设备时，读取原厂资产；输出路径必须是新的，保留原有证据：

```sh
python3.14 scripts/collect-boot-firmware.py --output out/new-capture/boot-firmware.json --extract-dir .cache/new-xbl-extracted
python3.14 scripts/prepare-uefi.py --uefi .cache/uefi-source/Mu-Silicium --extract-dir .cache/new-xbl-extracted
```

准备工具核对已提交清单的 84 份 PE32／DEPEX／RAW 资产哈希，将 44 个厂商模块包装及配置
放入该专用工作树。二进制保留在忽略目录。不会覆盖与上次准备清单不符的用户修改。
当前固件的 FDF 不 dispatch 厂商 UFS／USB DMA 驱动；XNU 也没有选择这些外设组件。

## 构建与打包

将 Homebrew LLVM、lld 放入 PATH，然后执行：

```sh
PATH=/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH python3.14 scripts/build-uefi-candidate.py --uefi .cache/uefi-source/Mu-Silicium --extract-dir .cache/new-xbl-extracted
```

此开发入口复用 UniXNU 的固件构建实现，仅生成 FD 和主机报告，不创建或写入设备镜像。
同一组输入也可走主仓库的常规 `build firmware`，并通过 `--edk2` 和
`--local-module refer:edk2=<Mu_Basecore绝对路径>` 指定已经固定的 Basecore。

打包时，`--dtb` 必须使用实机/原厂固件 FDT，不能用 `dts/sm-t970.dts` 生成的 XNU 硬件树。
实测 Android 镜像为 header v2、4096 页、无压缩 kernel、独立 DTB，偏移如下：

| 输入 | 相对 base=0 的地址 |
| --- | --- |
| kernel | `0x8000` |
| ramdisk | `0x2000000` |
| tags | `0x1e00000` |
| DTB | `0x1f00000` |

主仓库 `194aae294c1107e791f4f74b2be371a391ac6bc4` 已增加该布局的支持、upstream BootShim 的完整 image_size 校正及字节校验。
固件检查镜像可以使用 `--ramdisk none`；它没有 XNU payload，不代表 iPadOS 引导镜像。
Samsung 原厂环境未证明支持 `fastboot boot`，本阶段不执行重启或分区写入。

## 两个设备树输入

第 5 步要求两个用途明确的树输入，二者不能互换：

| 输入 | 来源 | 用途 | 核对 |
| --- | --- | --- | --- |
| 板级 DTS `dts/sm-t970.dts` | 本仓库 | `unixnu payload` 生成 `kernel.macho.adt` | `check-platform.py`／`check-hardware-description.py` 编译并解码 ADT |
| 固件 FDT | 设备 `/sys/firmware/fdt`（只读） | `unixnu bootimg --dtb` | `capture-firmware-dtb.py` 记录尺寸、SHA256 与脱敏摘要 |

实测固件 FDT 为 837154 字节（SHA256 `86c14aa305a6cf5db46665f4095d28aadcb1ea5ce9d213cd711641a07504ed1d`），
4533 个节点、43 个 reserved-memory 条目，`/chosen` 带 `bootargs`、`kaslr-seed` 和 initrd 范围。
它包含设备身份与启动状态，因此整包只留在忽略目录；提交的报告只保存哈希、结构、
内存区间和不含身份值的属性名。

两次独立采集得到同一份字节，可作为来源可复现的依据。板级 DTS 只有 memory、
静态保留区和禁用的外设节点，没有 `/chosen`；检查器会拒绝“两者相同”或“板级 DTS 带 `/chosen`”。

```sh
python3.14 scripts/capture-firmware-dtb.py --output out/firmware-inputs/firmware.dtb \
    --compare out/firmware-inputs/previous.dtb
python3.14 scripts/check-hardware-description.py --unixnu ../UniXNU
```

检查内容：固件 FDT 的完整交接结构；板级 DTS 编译出的 ADT 中 `/chosen`（DRAM 区间）、
`/cpus/cpu0`（亲和性、19.2 MHz）和 `/arm-io/intc`（寄存器、步长）；固件 DSC/FDF 中的
UniXNU、UniXNUDxe、RamDiskDxe、DarwinBoot、AdvancedLogDxe，以及基础配置中的
DiskIo／FAT／Unicode collation；若已构建，还会扫描卷内 GUID。

## 固件日志导出器

第 5 步要求首次启动时能从菜单导出固件日志。本板已按
[固件日志导出器步骤](https://unixnu.com/zh/porting/log-capture#firmware-setup)接入：

| 项目 | 值 |
| --- | --- |
| DSC `[Components]` / FDF | `UniXNUPkg/Driver/AdvancedLogDxe/AdvancedLogDxe.inf`（FFS GUID `8D4E7F50-3A2C-4C9A-9E1B-50C4C8472D41`） |
| 日志访问 | `AdvancedLoggerAccessLib`（`Common/Mu/AdvLoggerPkg`） |
| 二维码 | `QrEncoderLib`（`Common/Mu/MsGraphicsPkg`） |
| 硬件端口 | `AdvancedLoggerHdwPortLib` → `SerialPortLib`；DEBUG 下为 `FrameBufferSerialPortLib` |
| 设备名 | `gUniXNUPkgTokenSpaceGuid.PcdUniXNUDeviceModel = "gts7xlwifi"` |
| 菜单 | `board.toml [payload] tools = true` → **Tools → Advanced Logger** |

日志缓冲由 DXE Core 阶段的 `AdvancedLoggerLib` 通过
`AllocateReservedPages(PcdAdvancedLoggerPages)` 分配（默认 1024 页，即 4 MiB），随后安装
`gAdvancedLoggerProtocolGuid`；导出器的 Depex 依赖该协议，因此协议不存在时驱动不会加载。
SEC 阶段使用 PeilessArm 实例并让 `PcdAdvancedLoggerBase` 保持 0：本阶段不凭空固定一段
RAM 作为日志缓冲。调试输出仍经硬件端口写到屏幕，原有 DEBUG 屏幕诊断保留。

已验证（主机）：DEBUG 固件编译通过；`FVMAIN.Fv` 共 92 个 FFS 文件，导出器以
`8D4E7F50-3A2C-4C9A-9E1B-50C4C8472D41` 出现在卷内，并被 `FVMAIN.inf` 列出。

尚未验证：屏幕上的 Tools 菜单、二维码传输和日志内容。含菜单的 payload 镜像需要 XNU
内核与 Apple 负载输入，本阶段未构建，`tools` 的菜单项只经过生成代码路径核对。

## 固件清单范围

### SEC 的 FDT/initrd 交接补丁

上游固定提交的 SEC 不保存入口 x0；`UniXNURamDiskDxe` 需要从
`DAEE82E6-8090-4E72-BFB9-78C13CD4E359` HOB 中读取这个 FDT 地址。
`package/firmware/patches/0001-sec-entry-arg-hob.patch` 在汇编入口保存 x0，
并在 HOB 建立后发布该值。`inputs.json` 固定补丁和四个目标文件修改前后的 SHA256。

`prepare-uefi.py` 先校验补丁及文件状态，再应用；已经应用则验证而不重复打补丁。
状态不完整或存在未知源码改动时拒绝覆盖。无需依赖交接时 Mu 工作目录中的手工修改。

```sh
python3.14 -m unittest discover -s tests -v
```

`proprietary-files.txt` 共 130 条：43 个文件系统资产、3 个 builtin 固件和 84 个候选 UEFI 输入。
`builtin-firmware.json` 通过同一 boot kernel 中一致的 AArch64 相对重定位确认触控、笔、键盘
固件的数据位置及长度，记录 SHA256；未把其他设备的二进制当作本机输入。
无线 board-data 多个变体仅登记来源，当前未启用无线组件，也未假定实际选择了其中某份。

## 后续实机检查

检查固件入口、屏幕与实际 GOP、RAM disk FDT 交接、UEFI 可分配内存图、加载器分配、
恢复路径和内核日志。各项有实机证据后再提高 `porting.toml` 的验证等级。
未实现的外设继续保留 `planned`，不能用主机编译结果标记为设备验证通过。
