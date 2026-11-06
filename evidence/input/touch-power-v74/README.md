# T970 触控供电与身份探针 v74

v73 实机读到 `ldoa13=0x40a00`、`ldoa14=0x42100`，APPS RSC DRV2 ID/config 为 `0x00020000/0x800c8104`。两 ACTIVE TCS 空闲且未挂起 IRQ。v74 启用 `t970-touch-bus-report=5`，只在这些值与两个槽的空闲状态复现时借用 TCS1。原厂设备树约束 AVDD 3.3 V、DVDD 1.8 V；[Samsung fts1ba90a](https://github.com/mukahraman/kernel_samsung_sm8250/blob/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/input/touchscreen/stm/fts1ba90a/fts_ts.c#L2275) 先开 AVDD，等待约 1 ms 再开 DVDD。VRM 电压单位、偏移、HPM 数据及 TCS 完成位对照 [rpmh-regulator.c](https://github.com/mukahraman/kernel_samsung_sm8250/blob/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/regulator/rpmh-regulator.c) 和 [rpmh-rsc.c](https://github.com/mukahraman/kernel_samsung_sm8250/blob/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/soc/qcom/rpmh-rsc.c)。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers \
  --output out/data-bringup/touch-power-v74-build
python3.14 evidence/display/hello-black-v64/prepare.py --touch-power
```

每路分开提交 voltage/mode/enable 三条命令并等待响应。完成后还原 TCS1 寄存器和 IRQ 位；若超时，只屏蔽本槽 IRQ，保留在途命令，后续步骤停止。成功的供电投票保留到重启。只有两路都确认后才重跑 v72 的 GPIO 身份探针，仍要求 SDA/SCL 先达到高电平。TCS ACK 不是物理电压测量。宿主模拟通过命令参数、忙时拒绝、正常及无 ACK 恢复、超时隔离。

## 实机结果

两路各三条命令均为 `ack:10101/10101/10101`。随后 `idle=3 stage=done err=none n=5 id=5354393603 stop=1 restore=1`，确认在 `0x49` 通信，匹配 `fts1ba90a` 的 `39 36`。未测试触点或 HID。

[Tab S6 同芯片 Linux 驱动](https://github.com/Bentlybro/gts6l-mainline-linux/blob/41fa9b85bfb55f9ee671a1dcb8161a5d90a2d542/kernel/drivers/fts1ba90a.c) 提供扫描配置及 16 字节 FIFO 事件参考。用 [Mi 10 XNU 接入](https://github.com/reAAAq/UniXNU-umi/tree/3eb72578597d2ca16471b172d45eddc096a34a04/package/touch) 与 SM-T733 核对 HID 派发。Mi 10 的 FTM5 高半字节事件编码与本芯片的 SEC 格式不同。
