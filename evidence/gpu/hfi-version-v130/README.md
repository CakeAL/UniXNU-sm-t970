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

[镜像清单](preparation.json)和[刷写回执](upload.json)对应 BOOT
`da0349810f6e3f64181c273502a3c6b31db78b3d6e2740b1ff97f67c2a7180a7`。
Heimdall 确认上传并请求重启。[实机报告](device-result.json)确认
`cmd=4/4 msg=0/4 irq=1/0 ack=10401/100201/0/20010008`。固件读取了
命令并写回匹配应答，中断已清除，`pf=0`。八核在线，Data 查询成功，
GOP 完成 24 次拷贝和回收。
[主机验证](host-validation.json)记录了缓存与队列模型、栈帧、封包和独立
DTS/ADT 检查。完整平台检查停在历史框架版本校验。
