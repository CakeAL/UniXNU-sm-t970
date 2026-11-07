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

## 实机结果

13:32:48 机主照片 `screen-runtime.jpg` 及 `device-result.json` 确认：

- 桌面已进入。右上状态栏显示电池图标和 `Not Charging`，与
  `external=1 / charging=0` 一致，说明 `IOPMPowerSource` 已被系统消费。
- `Battery svc=1 samples=48 errors=0 published=1 age_ms=1870`：48 个 5 秒
  样本约等于 13:28:24 重启到拍照的 4 分钟，期间无读取错误；Gauge/Bat 来自
  worker 最后一次提交的样本（age 1.87 秒），不是 panic 路径的现场读取。
- 读数：60.93%、3919375 µV、-188281 µA（放电约 188 mA）、28.2 °C、
  5480/8787 mAh；所有换算值仍可由原始字重算。
- charger `chg=1:4f/e0/3b`：CHGIN_DTLS=3 有效、`CHG_OK` 位为 0、
  `CHG_DTLS=0xB` 是看门狗过期，所以插着 USB 仍显示未充电并在放电。

## 未验证与下一步

仍不写充电配置。下一步先只读 charger 的 CNFG_00/02/04/06/09，确认
WDTEN、CHG_EN、充电电流、输入限流和浮充电压，再决定是否清除看门狗并
恢复充电。未接 charger 中断，插拔状态最多延迟一个 5 秒周期；本次状态栏
只显示图标和 `Not Charging`，没有百分比文字。
