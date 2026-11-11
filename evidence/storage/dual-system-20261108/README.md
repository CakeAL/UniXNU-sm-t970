# SM-T970 双系统分区（2026-11-08）

实机为 SM-T970 / gts7xlwifi，TWRP 3.7.1_12-1_MinsOS，内核 4.19.325-Paradigm-g159176c6f4a2。开始前读回 BOOT、DTBO、RECOVERY、vbmeta、misc、metadata 与 UFS LUN0 的主备 GPT。备份留在忽略目录 `out/dual-system/pre-minsos-20261108`。

机主明确授权清掉原有 iPadOS `userdata` 并使用指定的本地 MinsOS ZIP。本地 ZIP 为 `e33d427f…`，发布摘要为 `f1e9c73c…`。ZIP 各条目 CRC 检查通过。TWRP Format Data 重建 F2FS 后，经 ADB Sideload 安装 MinsOS 1.2.3。安装器使用其默认 KernelSU 版本。BOOT、DTBO 前缀及完整 RECOVERY 的读回分别匹配 ZIP 内的 `5e206cde…`、`51ff626a…`、`b5c722e7…`。

两份原厂 GPT 校验有效，36 个已占用条目中有 11 个无关条目共用一个 GUID。分割工具仅在显式开启 `--preserve-duplicate-guids` 时接受该布局，并要求 `userdata` 与 `unixnu` 的 GUID 各自唯一。两份 F2FS 超级块最初只在 `version[]` 末尾的四字节 fsck 时间戳上不同。允许无超级块校验和的副本在这四字节上不同，保留其余比较。

从 TWRP 关闭 MTP 并卸载 `/sdcard` 绑定挂载后，运行 `partition.py apply --preserve-duplicate-guids --size-gib 96`。F2FS 从 59,489,271 块缩至 34,322,935 块。依次写入并读回备用 GPT 与主 GPT。重新进入 TWRP 后，`partition.py verify` 验证两份 GPT、内核分区范围和挂载中的 F2FS 大小。

| GPT 项 | 块设备 | 首 LBA | 尾 LBA | 容量 |
| --- | --- | ---: | ---: | ---: |
| 36 `userdata` | `sda36` | 2969600 | 37292799 | 130.933 GiB |
| 37 `unixnu` | `sda37` | 37292800 | 62458623 | 96.000 GiB |

iPadOS 以 `t970-ufs-unixnu=1` 选择 `unixnu`。签名载体的磁盘绝对位置由实际 GPT 起始 LBA 和分区内偏移计算，并检查整个载体位于选定分区内。ASan/UBSan 主机测试使用本机划分前后 GPT，验证了按名称选择、旧 `userdata` 路径，以及 `unixnu` 缺失时直接拒绝。iPadOS 仍使用 RAM Data，持久化未验证。

在 TWRP 中复核主备 GPT、`unixnu` 的名称解析、块设备、边界和挂载状态后，向 `sda37` 写入 9,382,658,048 字节根镜像。使用既有签名的正确载体，分别写入相对 LBA 5,505,024 与 5,516,624。刷写后三份内容均完整读回并与源摘要匹配，分别为 `fd43ee70…`、`8fefc15f…`、`869a186a…`。回执留在 `out/dual-system/root-install-retry1/receipt.json`。

主机使用框架 `2c834e313d25482c78d38d703eff1f8d190f2597` 加本轮分区工具修改和独立输出目录 `out/t970-dual-system`。内核预链接输出为 `d7cdae12…`。引导候选使用 v137 的固件、ADT、信任缓存和 RAM Data，移除本轮无关的 GPU 和 UFS 测试参数。Recovery 镜像内嵌刷 MinsOS 前的原厂 DTBO，SHA-256 为 `5c9355fa81ac394b1d001593b5d59d1e961293afeff0f7da1eb6776476958056`。

完成写入后从 TWRP 请求正常启动。电脑观测到 MinsOS 的 Android USB 产品标识，机主确认进入 One UI 欢迎页或桌面。ADB shell 和重启服务返回 `error: closed`，下一步通过按键返回 TWRP。

机主返回 TWRP 后，主备 GPT 仍与分割后的字节完全一致，且 `unixnu` 首块的根镜像标识存在。引导镜像经 ADB 写入 `RECOVERY`，完整读回 86,888,448 字节并确认摘要 `5c9355fa…`。写前和写后分别核对 MinsOS BOOT 与 DTBO 的整分区摘要，结果一致。随后执行 `adb reboot recovery` 以测试 iPadOS。

机主确认从该 Recovery 镜像进入 iPadOS 欢迎页或桌面。随后按键重启再次进入 iPadOS，正常回切待核验。Android 的 `reboot recovery` 路径可以写入 `misc` 的 `boot-recovery` 请求，实际请求状态待检查。GPU、触控和持久 Data 仍待单独验证。

## 复现位置

- 分区工具提交为 `404572cfc431f0b259cd190a99ad5b2c881a074a`。实机预览、执行和复核保存在 `out/dual-system`，原始主备 GPT 与设备标识留在忽略目录。
- 主机使用已有的 `sm-t970_data_defconfig` 构建输出，复制到框架的 `out/t970-dual-system`。执行 `python3.14 ./unixnu build kernel -D ../UniXNU-sm-t970 --out out/t970-dual-system`，以固定参考内核提供真实 PMGR，使用同提交的干净 CoreCrypto checkout。完整命令输出留在设备仓库的 `out/dual-system/build/kernel-isolated.log`。
- 从设备仓库运行 `python3.14 out/dual-system/boot-candidate/pack-recovery.py out/dual-system/boot-candidate` 打包 Android v2 镜像并读回 FAT。运行同目录的 `install-recovery.sh`，传入已确认的 ADB serial，按摘要和分区几何复核后写入 `RECOVERY`。原始 TWRP 保存在 `out/dual-system/pre-minsos-20261108/recovery.img`。
- 主机测试为设备仓库 76 项运行、10 项跳过，分割工具 13 项通过，F2FS C 自检通过。硬件 DTS/ADT 和固件输入检查通过。`check-platform.py` 在历史框架修订检查处停止。
