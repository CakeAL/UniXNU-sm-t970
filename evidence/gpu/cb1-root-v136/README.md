# v136 CB1 独立 GPU 页表与 SQE

模式 32 复用 [v135 实测](../cb1-format-v135/device-result.json)通过的
CB1 VA64，随后将 CBAR 切到 Stage 1。用 ArmSmmu4K 生成单独的 ASID 2
页表，覆盖 ring `0x01000000`、SQE `0x01008000` 和回读页
`0x01010000`。布局来自 [lmi A650 core memory](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-core-memory.c)。

构建固定 31,632 字节 SQE 的原厂 SHA-256，去掉首字后将 31,628 字节
复制到只读可执行的 GPU 页。ring 和回读页是可写、禁止执行。
探针写入并核对六个上下文字段，再用硬件 TTBR0 走查 17 个叶子。
CB1 翻译维持关闭，S2CR/SMR 不变。开始写 TTBR 后 backing 保留至重启。

预期 `GPU cb1root ok cfg=3f leaf=17 sqe=31628 ... held=1`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --sqe-firmware .cache/firmware/gpu-candidates/samsung-common-a650_sqe.fw --output out/data-bringup/gpu-cb1-root-v136-build
python3.14 evidence/gpu/power-v104/prepare.py --gpu-cb1-root
python3.14 -m unittest discover -s tests
```
