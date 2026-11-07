# v108 RSC/PDC 冷态快照

继承 [v107 实测镜像](../gmu-v107/device-result.json)。CX 与三条 XO 时钟保持期间，
确认 CM3 reset=1、FW_INIT=0、AO 计数推进及 GMU 的 RPMH_CTRL、RSCC 请求和应答均为零。
随后只读映射 T970 的 GPU RSCC（`0x03de0000 + 0x10000`），核对 DRV0 配置、
序列状态、中断和各 TCS 的状态。只有配置为 `0x4000000a` 才按十槽布局读 TCS，
十个槽均空闲且无 RSC 请求时再读路由和 SRAM。PDC 配置资源为 `0x0b290000 + 0x10000`。
采样完成后按 v107 的顺序恢复 XO 时钟和 CX。依据 [lmi DRV0 检查](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-rsc-init.c#L57-L83)。

报告用两行 RSC 读数替换旧的 ARC 档位和 GMU 摘要。各字段顺序如下。

- `GPU rsc` 的 `cfg/st/busy` 是 DRV0 配置、状态及序列忙位。 `g` 是三个 GMU 守卫值的按位或。
  `irq` 是 enable/status，`idle=3ff` 表示十个槽均满足空闲条件。
- `RSC hidden` 是三组地址/数据。 `route` 依次为 PDC slave ID、override、start、match low、match high。
  `seq` 是五个 RSC SRAM 字，`pdc` 是 start/enable。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-rsc-v108-build
python3.14 evidence/gpu/power-v104/prepare.py --rsc-read
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

2026-11-07 16:01（中国标准时间），Heimdall 成功上传 BOOT `25f846a6…` 并请求重启。
详见 [打包记录](preparation.json)、[主机验证](host-validation.json)和 [上传回执](upload.json)。
启动后三指按住两秒，采集 `GPU rsc` 和下一行 `RSC hidden`。
