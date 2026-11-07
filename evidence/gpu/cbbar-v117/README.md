# v117 CB0 Stage 1 属性回读

v116 已在实机完成 GMU/HFI 页表软件走查。v117 使用模式 14，在 CM3 保持复位、
六个 SMR 为零、S2CR 稳定、CB0 翻译关闭且无故障的条件下，切换 VA64，
将 CBAR 暂时设为 Stage 1 / Stage 2 bypass 的 `0x1f300`，回读后恢复原值。
测试值来自 [lmi 的 A650 路由实现](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-route.c)，
该实现撤销时允许 CBAR 保持 Stage 1。此处区分写入被过滤、原值恢复以及
Stage 1 持续可见三种结果。最后复核 CB0 快照、全部 S2CR 和全局故障状态。
写入目标限于 CBAR 和 CBA2R。遇到活动流、故障、状态异常或恢复未证实时保留上游依赖。
成功时 `GPU cbar` 报告应包括 `bar=1f300/0 rb=1 va=1/0 f=0 diff=0 bus=3/3 rsc=ff/ff xo=7 cxr=1`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --output out/data-bringup/gpu-cbbar-v117-build
python3.14 evidence/gpu/power-v104/prepare.py --cb-bar
python3.14 -m unittest discover -s tests
```
