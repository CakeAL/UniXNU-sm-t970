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

## 实测

[刷写回执](upload.json)与[实机照片及读数](device-result.json)对应 BOOT
`789e99a1b42f03b312586e5641e5d11da3b666a36f7a04d2e58245c1add98353`。
置位和回读均通过，CB0 全部恢复，总线、RSC、XO 与 CX 随后释放。快照中八核
在线，RAM Data 查询成功，GOP 路径完成五次拷贝和回收，侧键采样零错误。
