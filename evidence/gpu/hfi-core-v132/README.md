# v132 A650 HFI 带宽表与 CORE_FW_START

模式 28 在 [v131 的 FW_VER 和 PERF_TBL](../hfi-perf-v131/device-result.json)
重新通过后，从 T970 的 live cmd-db 查找四个 BCM。按
[A650 legacy ABI](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-hfi-core.c)
构建 160 字 `BW_TBL`。DDR 仅含 off 档，CNOC 保留协议的 off/on 两行。
只有带宽表应答回显、返回码与中断清除均通过才发送 `CORE_FW_START`。
完成或失败后均保留 GMU、DMA 和上游依赖至重启。

验收行应包含 `GPU bw ok cmd=224/224 msg=8/12 irq=1/0` 和
`GPU core ok cmd=228/228 msg=12/16 irq=1/0`，应答回显分别是
`30a003` 和 `40020e`，返回码均为 0。前置命令失败时报告其游标
和应答。GX、ZAP 和 CP 留到后续探针。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-hfi-core-v132-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-hfi-core
python3.14 -m unittest discover -s tests
```

[镜像清单](preparation.json)、[刷写回执](upload.json)及[实机报告](device-result.json)
对应 BOOT `3fdb8e6dc324e9b2d724c73cc1010ca1821e7bffe8d88cba72f82371fd372015`。
实测带宽表回显 `210303/30a003/0`、核心启动回显 `31030e/40020e/0`，
两次中断均清零，`pf=0`。八核在线，Data 查询成功，GOP 拷贝和回收各 38 次。
[主机验证](host-validation.json)记录队列、栈帧、封包和独立 DTS/ADT 检查。
完整平台检查停在历史框架版本校验。
