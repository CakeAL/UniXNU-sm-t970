# SM-T970 侧键（电源/锁屏、音量）

目标：电源键锁屏/唤醒、音量加/减，按下与松开都产生 iOS 消费的 HID 事件。

## 硬件归属（实机 DT 与 ADB 输入设备）

| 键 | 归属 | 证据 |
| --- | --- | --- |
| 电源 | PM8150 PON（SPMI SID 0，寄存器 `0x800`），`kpdpwr` 中断 | `qpnp_pon` input 暴露 `KEY_POWER`（`evidence/adb-2026-11-01/input.txt`） |
| 音量减 | 同一 PON 的 `resin` | 同一 input 暴露 `KEY_VOLUMEDOWN` |
| 音量加 | PM8150L（SID 4）SPMI GPIO3（1起始编号，外设 0xc2），低有效 | `gpio_keys/vol_up { gpios = <&pm8150l_gpio 3 ACTIVE_LOW> }`；`gpio_keys` 暴露 `KEY_VOLUMEUP` |

SPMI 仲裁器（`spmi@c440000`，EE 0）窗口来自实机 DT：

```
core   0xc440000 0x1100     cnfg   0xc40a000 0x26000
chnls  0xc600000 0x2000000  obsrvr 0xe600000 0x100000
intr   0xe700000 0xa0000    periph_irq = <PDC 1>
```

外设 PPID = `sid << 8 | (byte_addr >> 8)`：PON `0x008`，PM8150L GPIO3 `0x4c2`。

## 其他移植的做法

- **sheng（SM8550）**：`package/ButtonProbe.cpp` 走 SPMI v7 仲裁器，找 PON 与 GPIO 的 APID，在仲裁器里使能双边中断，`armcpu_spi_attach` 挂 PDC 转发的中断，线程只读 `RT_STS`（该端口 PON 位 7/6，GPIO 位 0；T970 的原厂驱动用位 0/1）并把变化成 HID report 2 的 Power/Volume Increment/Volume Decrement 位（`sheng-buttons=1`）。
- **mondrian（SM8475）**：同一套只读 observer 命令（`(1<<27)|(reg<<4)|(count-1)`，状态位 0，数据在 `+0x18`），把按键发到 `/dev/pong-buttons` 给用户态。
- **alioth（SM8250，与本机同代）**：确认电源/音量减是 PM8150 PON `RT_STS` 位 0/1 语义（`kpdpwr`/`resin`），音量加是 PMIC GPIO6，并给出 PPID 公式。

## 计划

1. **只读探针**（下一步）：按 v5 仲裁器布局映射 `core/cnfg/obsrvr`，读版本与 APID 数，找 PON `0x008` 与 GPIO `0x4c2`，轮询 `RT_STS`，把当前掩码与各键按下/松开次数并进运行时报告。不改任何 PMIC 寄存器，风险只在观察通道读。
2. **HID 注入**：确认我们现有的 21H461 HID 绑定能否承载第二个 report（消费控制），否则参考 sheng 的 `NativeHidInput` 建独立 device。
3. **中断化**：探针稳定后再走 PDC 中断（sheng 的 `armcpu_spi_attach`），把 16 ms 轮询换掉。

## 风险

- 读错 APID 或窗口可能同步外部中止（其他端口有先例），所以第一步只读、只碰 PON 与已确认的 GPIO PPID。
- 电源键若被注入 HID，会真的锁屏；探针阶段只读，不会改变系统状态。
- 仲裁器版本必须核对：`core[0]` 落在 `0x5xxxxxxx` 才按 v5 偏移使用，v7 布局的 `+0x2000`/`+0x00` 偏移不同（sheng 的实现）。

## 接入状态（v89 已构建并上传）

已实现 `package/T970Input/KeyProbe.cpp`、`scripts/build-key-probe.py`、
`build-kernel.py --keys`，并从显示启动／三指报告接入。修正的 APID 范围、状态位、
EE0 所有权与有界输出测试见 [v89](../evidence/input/keys-v89/README.md)。

旧计划中的 `KeyProbe.c` 未实现；现在使用 IOKit C++ 的 MMIO 映射，并沿用已审查的
编译配方。暂不发布 HID，先验证三键计数，随后分别接入音量、锁屏和唤醒。
