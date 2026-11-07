# v110 GPU DRV0 MX/CX 最低档位投票

以 [v109 实测的 RSC/PDC 初始化](../rsc-init-v109/device-result.json)为前置条件。
启用 GMU RPMH 接口 `0xf11` 并独占 GPU DRV0 的空闲 TCS1，顺序使用本机 command DB
核对过的 MX（`0x30010`）和 CX（`0x30000`）。两者发送的是 selector 2，
对应 MX code 128 和 CX code 64。CX 请求须等 MX 应答。采用
[lmi mode 25 的 DRV0/TCS1 协议](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-rpmh.c#L40-L96)。

每次等待上限 200 ms。收到 TCS 完成中断、slot idle 和 `0x10100` 状态才算应答。
请求完成后恢复命令槽、IRQ、GMU RPMH 接口、RSC/PDC、XO 和 CX GDSC。已完成的 ARC rail
投票留到重启，寄存器回读只确认控制器应答。请求超时或槽归属不明时保留依赖到重启。

期望 `GPU vote ok/ok mx=ack/10100 cx=ack/10100 ... rsc=ff/ff xo=7/7 cxr=1`。
`irq/ctl/st` 记录清理或保留前的中断、控制和槽状态。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-arc-vote-v110-build
python3.14 evidence/gpu/power-v104/prepare.py --arc-vote
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```
