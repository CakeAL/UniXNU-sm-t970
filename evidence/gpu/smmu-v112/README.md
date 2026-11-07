# v112 GPU SMMU 与 CB0 冷态

继承 [v111 的 200 MHz 路径](../gmu-rate-v111/device-result.json)。保持 CM3 reset、
已应答的 MX/CX、RSC/PDC 与 GMU 200 MHz，核对 GPUCC AHB、CXO、CX GMU 在运行后，
短时启用原厂 DT 列出的 GCC MEMNOC GFX 和 SNOC DVM GFX。两条总线时钟均通过时才
只读映射 `0x03da0000 + 0x10000`。原厂 DT 的 GMU kernel 路径是 SID5、mask `0x400`。
读序参照 [lmi SMMU 快照](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-probe.c#L142-L220)。

ID0/ID1 须匹配 lmi 的 6 个 SMR、5 个 4 KiB CB 和 `+0x8000` CB 基址。
SMR 全零、全局无故障且扩展 SID 未开启时，间隔 1 ms 采三次 CB0 寄存器。
随后恢复两条总线时钟的原 enable 位，再恢复 XO 和上游依赖。

- `GPU smmu` 的 `sm` 依次为有效 SMR 数、非零 SMR 数、S2CR0。 `bus` 是两条时钟原始运行值和就绪/恢复位图。
- `CB0` 的 `tt` 顺序为 TTBR0 low/high、TTBR1 low/high，`tcr` 为 TCR/TCR2，`chg` 为后两次采样中与首次不同的寄存器总数。

下一阶段用实测布局核对 SID5/CB0，并接入 `ArmSmmu4K` 的 4 KiB 页表和审计接口。
共享 A650 GMU 实现需要 icache、dummy、log、HFI 四类映射，后续为其分配并持有物理页，
再验证 attach/detach 和 HFI。 [ArmSmmu4K 组件](https://unixnu.com/reference/components)

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-smmu-v112-build
python3.14 evidence/gpu/power-v104/prepare.py --smmu-read
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

2026-11-07 18:09（中国标准时间），Heimdall 成功上传 BOOT `f9df94f3…` 并请求重启。
启动后三指按住两秒，采集 `GPU smmu` 和下一行 `CB0`。 [主机验证](host-validation.json) · [上传回执](upload.json)
