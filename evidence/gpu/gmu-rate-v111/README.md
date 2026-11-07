# v111 GMU 200 MHz 时钟路径

在 [v110 已验证的 MX/CX 投票](../arc-vote-v110/device-result.json)之后，保持 CX、时钟
和 RSC/PDC。确认 CM3 处于 reset、FW_INIT=0、GPLL0 运行于 600 MHz，GMU RCGR
仍使用 XO 且没有待处理 UPDATE。采用 [lmi mode 26](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-clock.c#L14-L82)
的顺序，启用 GCC GPU DIV_GATE，选择 GPLL0 / 2 再除以 1.5 的路径。

切换和恢复 XO 都需在 500 µs 轮询内读到 UPDATE 清零。先确认 XO 回读，再恢复 DIV_GATE。
若 UPDATE 或恢复状态不明确，保留已启用的依赖到重启。 `GPU rate ok/ok hz=600000000
cfg=1/100602/1 … rsc=ff/ff xo=7/7 cxr=1` 表示 200 MHz 路径的配置和恢复得到验证。
`hz` 由 GPLL0 寄存器推算，报告没有直接测量 GMU 频率。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-gmu-rate-v111-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-rate
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```
