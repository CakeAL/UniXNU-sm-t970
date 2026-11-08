# v135 CB1 AArch64 格式切换

模式 31 重验 [v134 的 CP/CB1 空闲条件](../cp-read-v134/device-result.json)，
并在已有的 GMU SID5 路由和 GX 保持运行时，将 CB1 的 `CBA2R.VA64`
从 0 写为 1，回读 CBAR、SCTLR 与 FSR，然后恢复 VA64 原值。
探针比对原始的 15 个 CB1 寄存器字。回读显示路由或电源状态变化时，
探针停止后续写入。CB1 的翻译、TTBR 和流匹配由后续探针设置。

预期 `GPU cb1fmt ok va=0/1/0`，`fsr=400` 为 AArch64 格式，
`diff=0` 表示恢复后的 15 个字与原值相同。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-cb1-format-v135-build
python3.14 evidence/gpu/power-v104/prepare.py --gpu-cb1-format
python3.14 -m unittest discover -s tests
```
