# v115 CB0 格式恢复

[v114 实测](../cbguard-v114/device-result.json)在 VA64 置位后读到 FSR
`0x400`。[Arm SMMUv2 规范](https://documentation-service.arm.com/static/5f900d34f86e16515cdc08fb)
和 [lmi 路由检查](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-route.c#L81-L90)
均将这组读数解释为 AArch64 格式。

v115 将 FSR[10:9] 与故障位分开判断。进入探针时要求原始 FSR 为零。
置位阶段要求 VA64 为 1 且 FSR 为 `0x400`。恢复时比较原始 FSR 和
其余 CB0 字以及 S2CR0。出现实际故障、活动流或恢复差异时保留上游依赖。

成功时 `GPU cbfmt` 显示 `va64=0/1/0 rb=1 guard=0/0 diff=0 bus=3/3 rsc=ff/ff xo=7 cxr=1`。
`CB guard` 中的 `f=0/400` 是置位时的全局和 CB0 FSR。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-cbrestore-v115-build
python3.14 evidence/gpu/power-v104/prepare.py --cb-restore
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```
