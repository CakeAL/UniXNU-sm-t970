# v123 GMU 固件装载和回读

[v122 实测](../sid5-v122/device-result.json)确认 GMU kernel 流可以发布至 CB0 并撤销。
v123 用 `A650GmuRegions` 和 `AdrenoFirmwarePlanGmu` 解析原厂已固定的
41,548 字节固件。输入可从 [linux-firmware 20260221](https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware/+/refs/tags/20260221/qcom/a650_gmu.bin)
取得，SHA-256 与 [T970 原厂清单](../../../proprietary-files.txt)相同。
构建验证大小与 SHA-256，将二进制保存在本地忽略目录。

探针在 CM3 保持复位时，将 22,888 字节装入已拥有的 GMU RAM，再将 18,404 字节
装入 ITCM/DTCM。逐字回读并观察 DTCM 版本，随后恢复 TCM 与 retention 原值。
之后清理 RAM 缓存，安装、走查并撤销禁用的 CB0 上下文。此轮验收固件装载；
GMU 启动将使用已验证的 T970 RSC 路由和对应 HFI 队列布局。

成功时 `GPU fw` 应显示
`ok/ok/ok tcm/ram=18404/22888 bad/rb=0/0 ver=20010008 cfg=3f/3f`
及 `bus=3/3 rsc=ff/ff xo=7 cxr=1`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-gmufw-v123-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-firmware
python3.14 -m unittest discover -s tests
```
