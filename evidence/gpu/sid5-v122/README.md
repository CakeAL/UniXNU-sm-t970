# v122 GMU kernel 流发布和撤销

[v121 实测](../cbactivate-v121/device-result.json)确认 CB0 翻译启停及本地 TLB 同步。
v122 使用原厂 DT 的 GMU kernel `SID 5 / mask 0x400`，在 CM3 保持复位时将
`0x005` 和 `0x405` 的匹配发布至 CB0。此轮验证寄存器和撤销顺序，CM3 全程复位。

发布前要求 SCR0 的全局故障报告与未匹配流故障策略有效，六个 SMR 都为空，S2CR0
为 FAULT，已审计的 CB0 正在翻译。按 [lmi A650 实现](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-route.c)
的字段掩码保留 S2CR0 的其余位，先写并回读 S2CR0，再发布 SMR0。
撤销时先清 SMR0 并回读，再恢复原 FAULT 路由，然后关闭 CB0 并同步 TLB。
若清除 SMR0 未证实，仍尝试恢复 FAULT，且保留页表与依赖。

成功时 `GPU sid5` 应显示 `ok/ok/ok smr=84000005/0`、`tlb=3 held=0` 和
`bus=3/3 rsc=ff/ff xo=7 cxr=1 n=2`。若继承值与 v112 一致，`s2` 应为
`1c38eb00/1f3aeaff`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --output out/data-bringup/gpu-sid5-v122-build
python3.14 evidence/gpu/power-v104/prepare.py --sid5
python3.14 -m unittest discover -s tests
```
