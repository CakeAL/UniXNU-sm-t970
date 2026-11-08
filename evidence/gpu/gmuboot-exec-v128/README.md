# v128 GMU 临时 RAM 取指

[v127 实机报告](../gmuboot-pf-v127/device-result.json)成功出图，确认 SID5
在 `0x153e00` 和 `0x154600` 发出特权取指请求。两页属于同一段
`0x144000–0x156fff` GMU 临时 RAM。模式 24 在释放 CM3 前给该段
19 个 4 KiB 叶加入执行权限，与
[同固件 lmi 页表](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-ram.c#L148)
在此范围内的 `0xe03` 属性一致。地址、物理 backing 和该段的读写权限保持原值。

探针保留 v127 的故障重试策略。报告 `pf=` 是已捕获的故障数，前两条
`GPU pf` 显示完整 64 位 PTE。若出现 `ready/smmu-hold fw=100 hfi=1/20000001`，
下一轮再验收 `FW_VER` 应答。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-gmuboot-exec-v128-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-boot-scratch-exec
python3.14 -m unittest discover -s tests
```

[镜像清单](preparation.json)和[刷写回执](upload.json)对应 BOOT
`8ee0c6edbbdf3a6a6c419cef22be74c82b846b7caaacf01e9a704dca076e9c88`。
Heimdall 确认上传并请求重启。[实机报告](device-result.json)显示捕获了三次
故障，前两次落在 HFI 队列和电源日志的起始页，PTE 的 XN 位在写入重试前已清除。
此前路由保留的 `INSTCFG=3` 会把读请求标记为取指，因此日志的 IND 位
反映的是 SMMU 路由处理后的属性。
[主机验证](host-validation.json)记录了页表差异、探测链栈帧、封包和独立
DTS/ADT 检查。完整平台检查停在历史框架版本校验。
