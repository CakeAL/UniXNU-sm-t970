# T970 触控总线只读探针 v70

从已显示 Hello 的 v69 重打包，新增 `t970-touch-bus-report=1` 与 75 秒终止报告。保留 2 GiB 窗口、防调暗 RAM Data 种子、原有信任缓存、固件和 DTB。v69 原镜像保留。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py \
  --cached-headers --output out/data-bringup/touch-bus-v70-build
python3.14 evidence/display/hello-black-v64/prepare.py --touch-bus
```

报告中的 `Touch RO` 行记录 GCC 投票寄存器和 SE5、wrapper 0 master AHB、wrapper 0 slave AHB 的分支状态。它同时读取 TLMM 北区 GPIO12/13/15 配置和逻辑电平。`lv` 的 bit2/1/0 对应 GPIO12/13/15。三个时钟分支都未报关闭时，才读 SE5 固件版本、FIFO 禁用位与状态寄存器。映射使用只读、禁缓存选项。探针不写寄存器，不驱动 GPIO，不发 I²C 请求。GPIO 电平不等于电源轨测量。

## 板级与协议证据

- 原厂设备树记录 SE5 `0x994000`、GPIO12/13、触控 IRQ GPIO15、地址 `0x49`、AVDD L13A 3.3 V、DVDD L14A 1.8 V，以及 `fts1ba90a_gts7xl.bin`。这些是配置值，实际供电仍待测。
- GCC 和 TLMM 寄存器地址分别来自 [Kona GCC](https://github.com/mukahraman/kernel_samsung_sm8250/blob/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/clk/qcom/gcc-kona.c) 与 [Kona pinctrl](https://github.com/mukahraman/kernel_samsung_sm8250/blob/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/pinctrl/qcom/pinctrl-kona.c)。GENI 只读寄存器的定义与 [Linux GENI SE](https://github.com/torvalds/linux/blob/abea5c349368a683e40fdc2e745099aaaacc89d7/include/linux/soc/qcom/geni-se.h) 对照。
- [三星 fts1ba90a 协议参考](https://github.com/mukahraman/kernel_samsung_sm8250/tree/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/input/touchscreen/stm/fts1ba90a) 的身份读取使用 `0x22` 加 5 字节读，预期身份字节为 `39 36`，事件槽 16 字节。该参考尚未通过 T970 的 XNU 实机总线验证。

主机编译、归档校验、预链接和最终 BOOT FAT 回读通过；两项显示回归测试通过。BOOT 上传已完成，Heimdall 已请求重启。尚待实机照片。

## 实机结果

`vote=041007c0 clk=80004220/0/80000002 gpio=1/1/1 lv=0 SE=off`。SE5 未投票，wrapper 主 AHB 已运行，从 AHB 报关闭且 HWCG 位已置位。GPIO12/13 仍是 GPIO 复用且读到低电平。SE 寄存器因此未读取，报告中的 `fw=0` 等是占位。照片和哈希见 `device-result.json`。
