# v134 上电后的 CP 与候选 CB1

模式 30 在 [v133 GX 上电](../hfi-gx-v133/device-result.json)重新通过后，
确认 SID5 仍有效，且 GX 电源、时钟、IRQ 和 AHB fence 状态允许读寄存器。
按 [lmi mode 34](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-cp-plan.c)
及 [A6xx 寄存器定义](https://raw.githubusercontent.com/torvalds/linux/v6.6/drivers/gpu/drm/msm/adreno/a6xx.xml.h)
记录 CP ring、SQE 和候选 CB1，读完后再次核对路由及关键状态。

`GPU cp idle` 表示 ring 游标、SQE 和 CP 错误寄存器为零，
候选 CB1 未启用且空闲，第二次读回匹配。`GPU cb1` 显示 CBA2R、
CBAR、SCTLR、FSR、TCR、TTBR0 及候选 S2CR1 原值。探针仍保留
已经开启的 GX、GMU 和 DMA。此次 CP 与 CB1 操作是只读的。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-cp-read-v134-build
python3.14 evidence/gpu/power-v104/prepare.py --gpu-cp-read
python3.14 -m unittest discover -s tests
```

[刷写回执](upload.json)、[镜像清单](preparation.json)及[实机报告](device-result.json)
对应 BOOT `54cc16fa928448adb68a0bda3ffc3731d5b5b9dd92adeace5a7cdb9067174167`。
实机读到 `GPU cp idle rbbm=1 irq=0 rb=0/0 ptr=0/0 sqe=0 err=0/0`，
CB1 的 VA64、CBAR、SCTLR.M 和 FSR 均为零。该截图采于启动早期，
Data 查询成功，GOP 拷贝计数为零。
[主机验证](host-validation.json)记录模型、栈帧、封包及独立 DTS/ADT。
完整平台检查停在历史框架版本校验。
