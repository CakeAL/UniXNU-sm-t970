# v119 CB0 TTBR 64 位访问

[v118 实测](../cbrelease-v118/device-result.json)确认 CBAR 保持 Stage 1 时，可以在原有
上下文和流状态均核对通过后释放依赖。v119 在 CBAR 为 `0x1f300`、VA64 为 1、
SCTLR.M 为 0、CM3 仍复位且六个流槽为空时，使用固定版本的 ArmSmmu4K MMIO
适配器访问 TTBR0 和 TTBR1。

每个 TTBR 先比较原生 64 位读取与两次 32 位读取。宽读一致后暂时翻转 ASID 的 bit 48，
保留页表基地址，再用两种宽度验证并写回原值。ASID 字段定义和访问顺序可参见
[Linux ARM SMMU 驱动](https://github.com/torvalds/linux/blob/v6.6/drivers/iommu/arm/arm-smmu/arm-smmu.c#L518-L535)。
如果 64 位读取或写入的结果与拆分读取不一致，报告 `width`。
如果写入后的守卫或恢复失败，保留上游依赖。恢复 VA64 后沿用 v118 的两次检查。
成功时 `GPU ttbr` 应显示 `ok/inert/ok rd/wr/rb=3/3/3`、
`bus=3/3 rsc=ff/ff xo=7 cxr=1 n=2`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --output out/data-bringup/gpu-ttbrwidth-v119-build
python3.14 evidence/gpu/power-v104/prepare.py --ttbr-width
python3.14 -m unittest discover -s tests
```

## 构建和刷写

[主机验证](host-validation.json)包含 64 位加载和存储反汇编、守卫模型、预链接、
FAT 回读、Mach-O 符号范围及独立 DTS/ADT 检查。完整平台检查停在历史框架版本校验。

[镜像清单](preparation.json)与[刷写回执](upload.json)对应 BOOT
`9e07061db0cdff73c64b48ed88101726021451f515d5bcc22d184038cb655c6a`。
Heimdall 确认上传成功并请求重启。

[实机报告](device-result.json)显示 `rd/wr/rb=3/3/3`。两个 TTBR 的原生 64 位
读取、ASID 置换与恢复均通过，两个快照匹配，所有依赖恢复。八核在线，
Data 查询成功，GOP 完成 39 次拷贝和回收。
