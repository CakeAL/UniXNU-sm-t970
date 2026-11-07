# v125 DDR AXI 与 GMU 首启

[v124 实测](../gmuboot-v124/device-result.json)在首启范围读到
`GCC_DDRSS_GPU_AXI=0x80100000`。v125 在 MEMNOC 和 SNOC DVM 时钟
之后设置 DDR AXI 的 ENABLE 位，要求回读 ENABLE=1 和 CLK_OFF=0，
随后沿用 SID5、固件及 HFI 首启探针。请求方式与
[固定 SM8250 电源序列](https://github.com/FFT-infra/UniXNU-sm8250-common/blob/166235ec2480ff0992627b7aafa15c65ce6b4efa/kits/Sm8250Platform/A650GmuPower.c#L397)
一致。

`axi=前/中/后` 记录 CBCR 三次观测。若仍关着，探针撤回本次增加的
时钟请求。若装载后保留依赖，末项为默认值 0。首启验收行应包含
`GPU boot ready/smmu-hold fw=100 hfi=1/20000001 rst=0` 和 `held=1`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-gmuboot-axi-v125-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-boot-axi
python3.14 -m unittest discover -s tests
```

[镜像清单](preparation.json)和[刷写回执](upload.json)对应 BOOT
`1cb79accad1624cd468373e8fe3421beb1ce08e8a5f076ed2b908bf40b4e38b6`。
Heimdall 确认上传并请求重启。
[主机验证](host-validation.json)包括时钟与 GMU 首启模型、封包和独立 DTS/ADT 检查。
完整平台检查停在历史框架版本校验。

## 实测

[实机报告](device-result.json)对应同一 BOOT。DDR AXI 从 `80100000`
变为 `00100001`，CLK_OFF 清零，SMMU 三条总线时钟拿到后进入 SID5、
固件和 CM3 首启。发布后读到：

`GPU boot fw/smmu-hold fw=0 hfi=0/0 rst=1 at=0 f=0/40000408 irq=0/0 held=1 axi=80100000/100001/0`

CM3 已释放，11 个配置寄存器全部读回一致（`at=0`），AO 和 GMU 致命位
均为 0。`fw=0` 表示 `FW_INIT` 没有出现 `0x100`，失败发生在首启阶段。
CB0 FSR 从空闲的 `0x400` 变为 `0x40000408`：按
[Linux arm-smmu 的 SMMU-500 定义](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/iommu/arm/arm-smmu/arm-smmu.h)，
`0x400` 是 AArch64 Format，位 3 是 permission fault（PF），位 30 是
stream stalled（SS）。GFSR 为 0，说明没有未匹配流的全局故障。
因此第一个 GMU 总线访问已被成功翻译，但被页表权限拒绝；流处于
stall 状态并一直等待，CM3 因而没有写 `FW_INIT`。该行没有记录 FAR，
具体地址和读写/取指方向留到下一轮。

八核在线，Data 查询成功，GOP 完成 85 次拷贝和回收。
