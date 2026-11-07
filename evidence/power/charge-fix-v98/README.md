# 修正看门狗喂狗回读 v98

BOOT `749b7419d42801fd27b22193343824a17ff6b3c96fea3347545a5ad0f7f25f1c`。在 v97 基础上只改 `applyChargerAction` 的喂狗校验：

- v97 把 `CNFG_06` 写成 `0xed`（`WDTCLR=1`）后要求整字节回读等于 `0xed`；
  但 WDTCLR 位写 1 后**自清**，回读永远是 `0xec`，于是每周期误判
  `kick-failed` 并把 `CHG_EN` 撤销，充电被 5 秒一次地反复开关。
- v98 只校验 `CNFG_06` 中保留的 bit7:2（CHGPROT/LX_SLOPE），不要求
  WDTCLR 位读回为 1；I2C 写失败或保留位变化才报告失败。
- 喂狗失败不再撤销 `CHG_EN`：未喂的看门狗到期会自行停充，这比在
  AP 无法喂狗时继续充电更安全。

`enabled` / `kicked` 的判别不变；充电电流 1500 mA、输入 1500 mA、4.35 V
浮充仍是引导阶段的原厂值，本轮不改配置、不改参数。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/charge-fix-v98-build
python3.14 evidence/power/charge-fix-v98/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/charge-fix-v98/boot-partition.img
```

## 预期与观察

- `Battery svc=... charge=kicked`（首个周期为 `enabled`）；
- `Charger cfg=` 应显示 `c09=bb`、`c06=ec`；
- `Bat` 的 `chg=1:` 应为 `1`/`2`（充电），电流符号若转正说明稳定充电；
- 状态栏应从 `Not Charging` 变为充电。

若 `charge=kicked` 但状态仍是 `0xB`，再按原厂顺序做 mode 0x4→延时→0x5
重启；若长期为负电流，需要单独核对 gauge 电流符号与充电电流实际值。

## 实机结果

14:04:20 照片及 `device-result.json` 确认修复生效：

- `Charger cfg=15/5e/13/ec/bb`、`CNFG_06` 回读 `0xec`，`Battery svc` 行
  `charge=kicked`：喂狗不再被自清位误判，CHG_EN 保持 1。
- `Bat` 的 `chg=1:5f/e0/31`：CHG_OK、CHGIN_OK 置位，CHG_DTLS=1，charger
  报告正在充电；47 个样本 0 错误。
- 但 gauge 电流仍是 -215625 µA，而 v96→v98 的 SOC/容量/电压是上升的
  （61.25%→62.62%，3.932→3.938 V）。电流符号与充电状态尚未对齐，暂不把
  `Amperage` 用于剩余时间估算；充电本身已由 charger 状态确认为使能。
- 本张照片没有状态栏（被 panic 文本覆盖）。
