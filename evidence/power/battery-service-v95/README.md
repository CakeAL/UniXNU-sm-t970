# MAX77705 只读电池服务 v95

BOOT `01e85687885b0a07d3f34442d132d89107e0203b976e95381a93df5358512d3b`。
继承 v94 的内存、HID、seed/trust 和电池总线；只增加只读电池服务、
`t970-battery=1` 启动参数及报告末的 `Battery svc=` 行。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/battery-service-v95-build
python3.14 evidence/power/battery-service-v95/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/battery-service-v95/boot-partition.img
```

## 实现边界

`package/T970Power/BatteryService.cpp` 在 `bsd_init` 的 `t970-battery=1`
门限内注册 `T970Battery` 类；常驻 worker 等 `IOBSD` 出现后挂接一次，每 5 秒
沿原有有界 GPIO I²C 读取一次 PMIC/gauge/charger，再把样本发布为
`IOPMPowerSource`：

- 电量按 REPSOC 百分比（`CurrentCapacity`/`MaxCapacity=100`），并另存原始
  `T970StateOfChargePercentX100`、电压、电流、温度、REMCAP/FULLCAP。
- 外部电源和充电状态用 `0xb2..0xb4` 的 CHGIN/CHG_DTLS 解码；看门狗过期
  （`0xB`）单独发布为 `T970ChargerDetail`，不据此伪造充电状态。
- 读取不完整时保留上一字段并设置 `MAX77705ReadIncomplete`；完整样本清除
  该错误条件。发布在首个完整 gauge 样本后发生。
- 三指报告优先使用 worker 最后一次提交的样本并追加
  `Battery svc=1 samples= errors= published= age_ms=`；服务未启动或尚无样本时
  才回退到 v94 的现场读取。panic 路径本身不再发起 I²C 事务。
- 电池对象与 PMGR 桥共用同一个 force-load 归档
  （`libShengPlatformPower.a`），因此现有链接依赖也会在电池对象变化时重链接。

## 未验证与下一步

本轮仍未写 PMIC/gauge/charger 配置：v94 看到的充电看门狗过期状态未处理，
充电不会因此开始。未接 charger 中断，插拔状态最多延迟一个 5 秒周期。
系统电池图标/百分比是否随 `IOPMPowerSource` 更新仍待机主观察；本目录
`upload.json` 只记录 BOOT 传输成功，`host-validation.json` 只记录主机检查。

实机步骤：正常重启进入桌面后三指按住取报告，确认 `Battery svc=1
samples>0 errors=0 published=1` 与 Gauge/Bat 两行；再插拔 USB，观察
`external`/充电图标是否在一个周期内变化。
