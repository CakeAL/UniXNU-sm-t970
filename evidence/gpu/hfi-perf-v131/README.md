# v131 A650 HFI 性能表

模式 27 复用 [v130 实测通过的 FW_VER](../hfi-version-v130/device-result.json)。
收到同一应答并清除中断后，读取本机 cmd-db 的 `gfx.lvl`、`cx.lvl` 和
`mx.lvl`，按原厂 [T970 OPP 表](../../adb-2026-11-01/live-device-tree.dts)的
七个活跃档及 off 档生成性能表。GMU 表包括 off 与已验证的 200 MHz。
MX 选择器按主轨实际选中的 corner 计算。ACD 字段使用诊断哨兵。
[A650 四队列性能表参考](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-hfi-perf.c)。

`PERF_TBL` 含 59 个有效字，填充到 60 字后发布。只有命令回显
`0x203b04`、返回码为零且应答中断可清除才判定通过。探针保留 live
SID5、DMA backing 和电源到重启，本轮验收到性能表。

预期 `GPU perf ok cmd=64/64 msg=4/8 irq=1/0`，并回显 `203b04/0`。
ACK 首字保留固件原值。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-hfi-perf-v131-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-hfi-perf
python3.14 -m unittest discover -s tests
```

[镜像清单](preparation.json)和[刷写回执](upload.json)对应 BOOT
`08365a3ad111027ea7cadb0027200b7424f3769fd80d24537ed01c692344b20a`。
Heimdall 确认上传并请求重启。[实机报告](device-result.json)回读
`cmd=64/64 msg=4/8 irq=1/0 ack=110304/203b04/0`，HFI 性能表通过，
SMMU 故障计数为零。八核在线，Data 查询成功，GOP 完成 27 次拷贝和回收。
[主机验证](host-validation.json)记录了队列及性能表模型、栈帧、封包和
独立 DTS/ADT 检查。完整平台检查停在历史框架版本校验。
