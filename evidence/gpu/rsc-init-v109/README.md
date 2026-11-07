# v109 RSC 序列与 PDC 受控初始化

在 [v108 实测冷态](../rsc-v108/device-result.json) 上复用
[lmi mode 24](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-rsc-init.c#L36-L86)。
CX 与三条 XO 时钟保持期间，重新核对 CM3 reset、DRV0、十个空闲 TCS、hidden 命令、
路由、序列 SRAM 和 PDC 初值。条件满足后依次写 SDE 位、五个 A650 RSC SRAM 字和 PDC
start/enable。每步回读，随后逆序恢复。此轮写入限于这八个位置，TCS 命令、hidden
路由和 CM3 reset 保持原值。

`GPU init ok cfg=4000000a idle=3ff wr=ff restore=ff xo=7/7 cx=1/1` 表示八个值均回读并恢复。
`rollback` 表示某步写入未通过，已恢复并再次核对冷态。`busy-hold` 或 `restore-hold`
表示检测到活动或无法确认恢复，保留上游 XO 与 CX 到重启。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-rsc-init-v109-build
python3.14 evidence/gpu/power-v104/prepare.py --rsc-init
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

2026-11-07 16:13（中国标准时间），Heimdall 成功上传 BOOT `569ebe5f…` 并请求重启。
详见 [打包记录](preparation.json)、[主机验证](host-validation.json)和 [上传回执](upload.json)。
机主截图确认 `GPU init ok cfg=4000000a idle=3ff wr=ff restore=ff xo=7/7 cx=1/1`。
八处写入与恢复均通过，XO 与 CX 同样恢复。同屏八核在线，GOP 完成 29 次复制和退役。
[实测记录与截图哈希](device-result.json)
