# 受守卫的充电恢复 v97

BOOT `96ff33b674e62c4ca18eeb3efed8955d718e22c70c7a4d9d20f5116063a5f979`。在 v96 配置快照基础上，`t970-charge=1` 时允许电池服务
在每次采样里做两件受守卫、可回读校验的写：

1. 若 `CHG_EN=0`：写 `CNFG_09 |= 0x80`（保留 1500 mA 输入限流），回读必须等于目标值。
2. 写 `CNFG_06` 的 `WDTCLR=1` 喂看门狗（保留 CHGPROT/LX_SLOPE），回读校验。

守卫（在读取当前样本后重新检查）：电池在位、`0 ≤ 温度 ≤ 45 °C`、
`3.0 V ≤ 电压 ≤ 4.35 V`、`CHGPROT=3`（配置未锁）。守卫失败时若充电已使能，
会撤销 `CHG_EN`；喂狗写失败也会撤销 `CHG_EN`，避免无看门狗充电。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/charge-restart-v97-build
python3.14 evidence/power/charge-restart-v97/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/charge-restart-v97/boot-partition.img
```

## 报告与预期

`Battery svc=` 行末尾新增 `charge=`：

- `enabled`：本轮把 CHG_EN 从 0 置 1 且喂狗成功；
- `kicked`：CHG_EN 已是 1，本轮只喂狗；
- `guard` / `guard-disabled`：守卫失败，未使能或已撤销；
- `enable-failed` / `kick-failed` / `disable-failed`：写入或回读失败。

看门狗保持使能、每 5 秒喂一次（沿用原厂做法）。充电电流 1500 mA、
输入限流 1500 mA、浮充 4.35 V 仍是引导阶段写入的原厂值，本轮不改。
若 `charge=enabled` 而下一次采样的 `Bat` 仍显示 `CHG_DTLS=0xB`（状态栏仍
`Not Charging`），说明过期状态被锁存，下一步按原厂顺序做 mode 0x4→延时→0x5
重启充电。

## 待观察

三指报告的 `Battery svc` 行（`charge=` 值）、`Charger cfg` 行和 `Bat` 行；
状态栏是否从 `Not Charging` 变为充电。若温度/电压守卫拒绝，会看到
`charge=guard` 且寄存器不变。

## 实机结果

13:56:01 照片及 `device-result.json` 确认：

- `Charger cfg=15/5e/13/ec/bb`：`CHG_EN` 已被写成 1，说明使能写成功；
  `Bat` 的 `chg=1:5f/e0/31` 里 CHG_OK 置位、CHG_DTLS=1，charger 确实进入充电。
- 但 `Battery svc` 行是 `charge=kick-failed`，`CNFG_06` 仍读回 `0xec`。
  原因是 WDTCLR 位**写 1 后自清**，回读的 bit1:0 永远是 0；v97 拿整字节
  `0xed` 比对，误判为失败，然后每周期把 `CHG_EN` 写回 0，充电被反复开关。
- 电流仍是 -264843 µA（放电），与这种 5 秒一次的短暂使能一致。

修复方向（v98）：喂狗只校验被保留的 bit7:2，不要求 WDTCLR 位回读为 1；
喂狗失败也不撤销 CHG_EN（未喂的看门狗到期会自行停充）。enabled/kicked 的
判别保持不变。
