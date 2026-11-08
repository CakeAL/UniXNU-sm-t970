# v133 A650 GX 上电

模式 29 在 [v132 的带宽表与 CORE_FW_START](../hfi-core-v132/device-result.json)
重新通过后，发送 `START` 和最低活跃档 DCVS 请求。档位 1 对应
T970 原厂 305 MHz，带宽参数 `0xff` 保留当前值。
然后通过 GMU 发送 GX 的 OOB 请求，最多轮询 1,000 次，每次 100 µs。
[A650 实现参考](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-gx.c)。

验收行应包含 `GPU gx ok/ok/ok echo=50010a/60041e rc=0/0
oob=80000000/0`，且 `pwr` 后值的 `0xc0` 位和 `fence` 为零。
探针只清 OOB 应答中断，GX 请求、GMU、SID5、DMA 和上游时钟保持至重启。
该轮验收 GX 供电与时钟状态，ZAP 和 CP 由后续探针验证。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-hfi-gx-v133-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-hfi-gx
python3.14 -m unittest discover -s tests
```

[镜像清单](preparation.json)、[刷写回执](upload.json)和[实机报告](device-result.json)
对应 BOOT `f6537ceddde66d65b67fdc74d5efac5df468ac2a1459750da0cdc62180d5a793`。
实机确认 `echo=50010a/60041e rc=0/0 oob=80000000/0 pwr=c0/0 fence=0`，
`pf=0`。八核在线，Data 查询成功，GOP 拷贝和回收各 20 次。
[主机验证](host-validation.json)包括 GX 模型、栈帧、封包和独立 DTS/ADT。
完整平台检查停在历史框架版本校验。
