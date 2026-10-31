# SM-T970 固件输入与主机构建

本阶段完成 CPU0／initrd 引导所需的仓库输入，未在平板上执行新固件。
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

DTS 选择实测高内存段 `0x180000000 + 0x100000000`。检查工具对照 30 个静态保留区、
原厂动态池的分配窗口及上述 45 个 XBL 区域检查不相交；原厂动态池仅供禁用外设的
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

主仓库 `7ebc585543fd1a89e1d47d17442899ab61978f9a` 已增加该布局的支持及字节校验。
固件检查镜像可以使用 `--ramdisk none`；它没有 XNU payload，不代表 iPadOS 引导镜像。
Samsung 原厂环境未证明支持 `fastboot boot`，本阶段不执行重启或分区写入。

## 固件清单范围

`proprietary-files.txt` 共 130 条：43 个文件系统资产、3 个 builtin 固件和 84 个候选 UEFI 输入。
`builtin-firmware.json` 通过同一 boot kernel 中一致的 AArch64 相对重定位确认触控、笔、键盘
固件的数据位置及长度，记录 SHA256；未把其他设备的二进制当作本机输入。
无线 board-data 多个变体仅登记来源，当前未启用无线组件，也未假定实际选择了其中某份。

## 后续实机检查

检查固件入口、屏幕与实际 GOP、RAM disk FDT 交接、UEFI 可分配内存图、加载器分配、
恢复路径和内核日志。各项有实机证据后再提高 `porting.toml` 的验证等级。
未实现的外设继续保留 `planned`，不能用主机编译结果标记为设备验证通过。
