# v105 CX 电源域上电与恢复

从 [v104 实测 BOOT](../power-v104/device-result.json) 继承固件、ADT、Data 种子和
trust cache，替换内核及 `t970-gpu-p=2`。三指报告触发一次 CX 实验。

使用 [lmi 的 CX 独立探针](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-probe.c#L585-L627)
和 [Linux GDSC 状态判定](https://github.com/torvalds/linux/blob/v6.6/drivers/clk/qcom/gdsc.c#L54-L85)。
CFG AHB 必须已启用且在运行，CX/GX 必须仍处于 collapse 初态，CX 由软件控制，
GX 的上电完成位必须为 0。只清 GPUCC CX GDSCR（`0x3d9106c`）的 bit0，
按锁定的 SoC 头文件等待最多 2 ms，再恢复 bit0，另等最多 2 ms 读回掉电状态。

报告 `GPU cx pre=… on=… end=… ack=… restore=…` 中各对依次为 CX GDSCR 和 CX
硬件状态。 `ack=1 restore=1` 表示电源域已响应并恢复；若 `ack=0 restore=1`，
用读数区分写入被拒和上电等待超时。 `refuse` 会打印 CX/GX 初态以定位触发条件。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-cx-v105-build
python3.14 evidence/gpu/power-v104/prepare.py --cx-pulse
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```
