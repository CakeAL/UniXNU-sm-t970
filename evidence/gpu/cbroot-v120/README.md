# v120 禁用的 CB0 接入真实页表

[v119 实测](../ttbrwidth-v119/device-result.json)确认两个 TTBR 支持原生 64 位读写。
v120 复用 v116 的 XNU 物理连续内存和五个 GMU RAM 窗口，用实测 SMMU ID
编码上下文，并把已走查的页表和零填充缓冲区清到 PoC。

在 CM3 复位、SCTLR.M 为 0、无流且无故障时，探针临时安装 TCR2、TCR、MAIR0/1、
TTBR0/1。读取两个宽度并从实机 TTBR0 的基地址重新走查 42 个叶页。
随后恢复六项寄存器，并沿用 v118 的两次完整回读。只有撤销得到确认后，
才释放 XNU 内存和上游依赖。恢复不确定时，页表保留到重启。
此模式只验证未启用的上下文，后续还需要 TLB 同步、激活与 SID5 路由验证。

成功时 `GPU root` 应显示 `ok/inert/ok cfg/rb=3f/3f leaf=42 held=0`，
以及 `bus=3/3 rsc=ff/ff xo=7 cxr=1 n=2`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --output out/data-bringup/gpu-cbroot-v120-build
python3.14 evidence/gpu/power-v104/prepare.py --cb-root
python3.14 -m unittest discover -s tests
```

## 构建和刷写

[主机验证](host-validation.json)包含真实建表和走查库、安装和回滚守卫模型、缓存指令、
预链接、FAT 回读、Mach-O 符号范围和独立 DTS/ADT 检查。完整平台检查停在历史框架版本校验。

[镜像清单](preparation.json)与[刷写回执](upload.json)对应 BOOT
`e6d8b426b79facd7ebe47b5a6e6100f377542befbf3fc718e9a91c8a3c6d21b6`。
Heimdall 确认上传成功并请求重启。

[实机报告](device-result.json)显示 `cfg/rb=3f/3f leaf=42 held=0`，两个快照匹配，
依赖均已恢复。八核在线，Data 查询成功，GOP 完成 18 次拷贝和回收。
