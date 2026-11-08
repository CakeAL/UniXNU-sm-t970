# v130 HFI FW_VER 应答

[v129 实测](../gmuboot-inst-v129/device-result.json)确认 SID5 路由、GMU
启动和 HFI 队列就绪。模式 26 复用同一路径，随后只发一条
`FW_VER`。当前 UniXNU 的 AdrenoHfi 接口使用现代三队列布局与
一致性内存。这个探针沿用已实测的 A650 四队列布局和
[同固件 lmi 命令](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-hfi-io.c)。

探针检查版本字、队列布局、空游标和中断状态，按内容、写游标、门铃的
顺序发布。最多轮询 1,000 次，每次间隔 100 µs。完整应答必须匹配包
类型与长度、命令回显、返回码 0、版本 `0x20010008`。消费后回读
中断清零。GMU 和 DMA 映射保留至重启，超时后也保留。

预期报告为 `GPU fwver ok cmd=4/4 msg=0/4 irq=1/0`，其后记录四个
原始应答字。`cmd` 和 `msg` 是消费应答前的读写游标快照。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-hfi-version-v130-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-hfi-version
python3.14 -m unittest discover -s tests
```
