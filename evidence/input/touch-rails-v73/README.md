# T970 触控供电资源只读探针 v73

v72 实测去掉 GPIO 下拉后 SDA/SCL 仍低，未发 I²C 请求。原厂设备树给出 L13A 3.3 V（AVDD）、L14A 1.8 V（DVDD）、command DB 保留区 `0x80860000+0x20000` 和 APPS RSC DRV2 `0x18220000`，TCS 偏移 `0xd00`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers \
  --output out/data-bringup/touch-rails-v73-build
python3.14 evidence/display/hello-black-v64/prepare.py --touch-rails
```

启动参数 `t970-touch-bus-report=4` 在 75 秒终止报告中检查 command DB magic、VRM 节点、对齐、范围和唯一性。只接受 `ldoa13`、`ldoa14` 的完整零填充键。读取 RSC 标识与 DRV 配置，几何匹配时才读 TCS0/1 的状态、控制、命令使能及等待位。参考 [板型内核 cmd-db.c](https://github.com/mukahraman/kernel_samsung_sm8250/blob/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/soc/qcom/cmd-db.c) 和 [rpmh-rsc.c](https://github.com/mukahraman/kernel_samsung_sm8250/blob/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/soc/qcom/rpmh-rsc.c)。宿主模拟通过正确键、重复键、地址重复、VRM 范围、长度越界及 magic 错误测试。

探针只读 MMIO，没有提交 TCS 请求。找到地址与空闲槽只表明后续可以按硬件证据准备供电探针；电源实际电压和触控身份仍须实测。

## 实机结果

`db=1 l13=40a00 l14=42100 rsc=20000/800c8104 irq=1/0`。TCS0 和 TCS1 均为 `st/ctl/en/wait=1/0/0/0`。TCS1 空闲且 IRQ 未使能，作为 v74 的唯一候选槽。照片与镜像哈希见 `device-result.json`。
