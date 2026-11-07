# MAX77705 charger 配置快照 v96

BOOT `3ce997f23f30650f4ffec97edd0e76ce0d9a4ab35d8382a4454a79fb89f98c35`。
v95 基础不变（同一 971 字节参数，仍为 `t970-battery=1 t970-battery-ro=3`），
只把 charger 的 CNFG_00/02/04/06/09 加入每次 5 秒采样，并在报告中新增
`Charger cfg=` 行。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/battery-config-v96-build
python3.14 evidence/power/battery-config-v96/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/battery-config-v96/boot-partition.img
```

## 为什么先只读

v94/v95 已知 charger 的 `CHG_DTLS=0xB` 是看门狗过期：外部电源有效、`CHG_OK=0`，
所以插着 USB 仍显示 `Not Charging` 并以约 188 mA 放电。原厂异常处理会先
关充电、重设浮充电压再重新开充电，并不只看一个状态位；在此之前还要知道
WDTEN、CHG_EN、充电电流、输入限流和浮充电压的现值。本轮只加读取：

- 每次采样多读 5 个寄存器（0xb7/0xb9/0xbb/0xbd/0xc0），总事务 9 → 14，
  仍是同一 GPIO28/29 有界 I²C 路径，不写任何寄存器。
- 解码：`WDTEN=CNFG_00 bit4`、`CHG_EN=CNFG_09 bit7`、
  `ICHG=(CNFG_02&0x3f)×50 mA`、`IIN=((CNFG_09&0x7f)+1)×25 mA`（代码 0 表示
  不限流）、`CV=CNFG_04&0x3f`。
- 报告新增一行，并把原始字节和换算值作为自定义属性发布；读取失败时该行
  标记 `partial`，不影响电量样本本身的完整性。

## 边界与待观察

只读，不改变充电状态；看门狗仍过期，charger 中断仍未接。若这一行显示的
`wdtEn=1/chgEn=1`，下一步才考虑按原厂顺序清除看门狗并重启充电，并加
回读校验；`chgEn=0` 时需要先确认允许的充电电流/电压配置。

实机步骤：正常重启进桌面后三指按住，发 `Charger cfg=` 行和
Gauge/Bat/`Battery svc` 行。若报告没有这一行，说明配置读取失败，请一并
发 `Bat` 行的 `stage/fault`。
