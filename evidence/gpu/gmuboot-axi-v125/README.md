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
