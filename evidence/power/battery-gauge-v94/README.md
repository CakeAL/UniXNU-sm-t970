# MAX77705 只读测量 v94

BOOT `6d5c4c60b69a1e160fe02a2e25ad553837d01e6268c013f6ba724dcad47206c6`。
继承 v93 的内存、HID 和 seed/trust；只替换内核及 `t970-battery-ro=2` → `3`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/battery-gauge-v94-build
python3.14 evidence/power/battery-gauge-v94/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/battery-gauge-v94/boot-partition.img
```

## 边界与输出

先沿 v93 方法读取 SE0，要求 I²C 协议 3、M/S 均空闲且 AHB 控制已恢复。
只在 GPIO28/29 配置均等于实测 `7` 时临时切到 GPIO 开漏模式，保留上拉，
通过已验证的触控软件 I²C 实现寄存器读，最后恢复复用、输出锁存和 OE。

先读 PMIC `0x66` 的 ID/revision，要求原厂识别表中的组合；然后读 gauge
`0x36` 的 STATUS、REPSOC、VCELL、CURRENT、TEMP、REMCAP、FULLCAP。
七项均有效后读 charger `0x69` 的 `0xb2..0xb4` 状态，避开 read-to-clear INT。
不修改 PMIC、gauge 或 charger 配置，不发布系统电池服务。

报告新增 `Gauge` 原始字及 `Bat` 换算值、valid、charger 原始状态和 `restore`。
`soc100` 为百分比的百分之一，`uV/uA/mC` 为微伏、微安、毫摄氏度，cap 为 mAh。
valid 不完整时零初始化字段不是有效测量；`chg=0` 表示状态读取无效。

## 验证与当前状态

编译、prelink 及原始 21H461 HID 绑定通过。64 项测试中 54 项通过、10 项跳过；
新增真实代码的 ASan/UBSan 检查覆盖 I²C 地址、重复 START、ACK/NACK、仲裁、
SCL 超时、时钟恢复、GPIO 恢复及测量单位。见 `host-validation.json`。

2026-11-07 13:02:52 已 BOOT-only 刷入成功并请求重启。尚待桌面和 Gauge/Bat
实机读数；不能由传输成功认定电池可用。`source/`、`preparation.json` 和
`upload.json` 保留本轮确切源码、镜像身份和传输记录。

未刷的早期编译目录保留：一次 C++ 无标准库 initializer_list 编译失败已改为
普通循环；一次协议门限误写为 2（UART）已纠正为 3（I²C）后重建本镜像。
错误门限会拒绝本机 I²C 引擎，旧构建未打包部署。
