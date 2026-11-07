# v124 GMU 首启

以 [v123 固件装载实测](../gmufw-v123/device-result.json)和
[v122 SID5 实测](../sid5-v122/device-result.json)为基线。沿用 T970 验证过的
RSC 路由和 200 MHz GMU 时钟，用 XNU 自有页表为 SID5 提供 GMU RAM、
电源日志和 20 KiB HFI 队列。CM3 释放参数来自
[lmi A650 首启](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-boot.c)，
四队列布局来自[同一固件的 HFI 实现](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-hfi.c)。

探针仅运行一次。先回读固件和寄存器并屏蔽 AO/GMU 中断，再释放 CM3。
分别等待 `FW_INIT & 0x1ff == 0x100` 和 HFI 状态 bit 0，每阶段最多轮询
1,000 次，间隔 100 µs。握手失败后拉回 CM3 复位并回读。装载成功后，
探针保持 SID5、页表及上游电源时钟直到重启。后续报告重用首次观测。

验收行应包含 `GPU boot ready/smmu-hold fw=100 hfi=1/20000001 rst=0`，
以及 `f=0/400` 和 `held=1`。 `f` 记录 SMMU 全局及 CB0 故障状态，
`0x400` 是 AArch64 Format 位。`at` 记录发生回读异常的 GMU 配置寄存器偏移。
本轮验收到 HFI 队列就绪。后续用 `FW_VER` 的应答验证收发队列。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-gmuboot-v124-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-boot
python3.14 -m unittest discover -s tests
```

[镜像清单](preparation.json)、[刷写回执](upload.json)和[实机报告](device-result.json)
对应 BOOT `a5af785e63a87473fff855937a37222173e7fa9b8c82abcc8cf5f54d92d82224`。
实机读到 `axi=80100000`，DDR AXI 的 CLK_OFF 置位，探针在 SMMU 设置前返回。
八核在线，Data 查询成功，GOP 完成 23 次拷贝和回收。
[主机验证](host-validation.json)含 ASan/UBSan 模型、镜像及独立 DTS/ADT 检查。
完整平台检查停在历史框架版本校验。
