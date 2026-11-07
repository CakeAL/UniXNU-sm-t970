# 本轮内存与外设接入

目标是使用设备全部 8 GB 中实际可交给 XNU 的内存，实现 Wi-Fi、亮度、音量／锁屏键
和电池服务；GPU 暂缓。各项以镜像哈希、设备结果和 `porting.toml` 记录验收。

T733 参考项目的提交与实机范围已核查，见
[2026-11-07 功能核查](t733-feature-audit-20261107.md)。后续还对齐 USB CDC/ECM/LLDB、
持久 Data、正常关机、MSC 更新、CPU 调频和温度管理；其 README 中的旧状态不能作为
当前实现清单，参考项目的实测也不能替代 T970 自身验收。

| 项目 | 已确认输入／实现 | 当前实机范围 | 下一步 |
| --- | --- | --- | --- |
| 内存 | Loader 的连续 owned window；v87 托管范围覆盖补丁已撤下 | v88 桌面，3713.86 MiB 管理页，8 核 | 导出实际 EFI 内存图和分配区间，设计多区间管理，压力验证 |
| 侧键 | PM8150 PON + PM8150L SPMI GPIO，v89/v90 观察器已链接 | v91 三键HID、97报告/0错误；锁屏及再次点亮正常；音量键响应 | 音频路由可用后验证音量值与实际声音；继续电池／内存，分别验证音量和锁屏／唤醒 |
| 电池 | MAX77705，QUP0 I²C，GPIO28/29；FG 0x36、charger 0x69、PMIC 0x66 | v94 实机读数有效；v95 服务已确认：48 样本/0 错误，状态栏显示电池与 `Not Charging`；v96 配置快照确认 `chgEn=0`；v97 确认 CHG_EN 可写、CHG_DTLS=1；v98 修复生效：`charge=kicked`、CHG_DTLS=1 持续充电；gauge 电流符号待核对 | 转亮度（DSI 交接与 S6TUUM3 命令），充电中断后补 |
| 亮度 | S6TUUM3 AMSA24VU01，DSI command mode，范围 1–355 | GOP 图像已验证，亮度未验证 | 读取 DSI 交接状态；按面板 normal gamma mode 2 命令与映射表实现调节 |
| Wi-Fi | QCA6390 PCI 17cb:1101，subsystem 17cb:0108，PCIe0 | Android 设备 ID；XNU 尚未训练链路 | SM8250 PCIe0 供电、PHY、复位、BAR、MSI／DMA；然后接 ath11k/MHI/QMI 与 21H461 网络 ABI |

## 电池

原厂 `drivers/mfd/max77705.c` 建立 FG 子客户端 `0x6c >> 1 = 0x36`。
DT 的父节点 `max77705@66` 不是 gauge 的地址。charger 在 `0xd2 >> 1 = 0x69`。
SE0 地址 `0x980000+0x4000`，引脚为 NORTH tile 的 GPIO28/29，不能套触控 SE5 的
GPIO12/13 或另一 SoC 的 DSP battery-manager 协议。

gauge 的 16 位寄存器按低字节在前读取：STATUS `0x00`（bit 3 表示缺电池）、
REPSOC `0x06`（1/256 %）、TEMP `0x08`、VCELL `0x09`（78.125 µV/LSB）、
CURRENT `0x0a`、FULLCAP `0x10`、REMCAP `0x05`。
DT 的 `fuelgauge,fg_resistor=5` 是厂商软件缩放参数，电流换算按该驱动的
`signed_raw * 15625 * 5 / 100` µA；不要把它直接解释成 5 mΩ 后套通用公式。
厂商还有容量校准、温度补偿和电流补偿；原始 gauge 百分比不保证等于 Android UI。

`package/T970Power/Max77705Measurements.h` 实现只读字解码，v94 在终端报告路径接入
有界 GPIO I²C 读。v94 实机报告确认七项有效：`soc100=6049`、`uV=3925312`、
`uA=0`、`mC=28199`、`cap=5442/8787`，全部可由原始字重算；GPIO 恢复读回 1。
charger 读到 `int_ok=0xcf`、`details_00=0xe0`、`details_01=0x3b`：CHGIN 有效
说明外部电源在位，但 `details_01 & 0xf = 0xB` 是原厂代码中的充电看门狗过期，
所以充电未进行。本轮不改任何 PMIC／gauge／charger 配置。

v95 `BOOT01e85687` 在 `t970-battery=1` 下注册 `T970Battery`，worker 等
`IOBSD` 后每 5 秒沿同一有界 GPIO I²C 路径读取，并发布
`IOPMPowerSource`：百分比、电压、电流、温度、REMCAP/FULLCAP、外部电源与
充电状态；不完整样本保留上一字段并设置错误条件。三指报告的 Gauge/Bat
改用 worker 最后提交的样本，并多一行 `Battery svc=1 samples=...`；服务未
启动时才回退到 v94 的现场读取。仍不写任何充电配置，看门狗过期和
charger 中断留给后续。

13:32:48 实机照片确认服务被系统消费：状态栏显示电池图标和 `Not Charging`，
`Battery svc=1 samples=48 errors=0 published=1 age_ms=1870`，读数 60.93%、
3919375 µV、-188281 µA（放电）、28.2 °C、5480/8787 mAh。charger 仍是
`4f/e0/3b`：CHGIN 有效但 CHG_DTLS=0xB（看门狗过期），所以插着 USB 也不充电。
下一步先只读 CNFG_00/02/04/06/09，确认 WDTEN、CHG_EN、电流和浮充电压，
再决定是否清除看门狗、恢复充电。

v96 `BOOT3ce997f2` 已加入这五个配置字的只读采样，报告新增
`Charger cfg=.. wdtEn= chgEn= ichg= iin= cv=` 行；仍不写 charger 寄存器。
实机值待回报，之后按原厂顺序处理看门狗和充电重启。

v97 `BOOT96ff33b6` 在 `t970-charge=1` 下把 CHG_EN 从 0 置 1、按原厂方式写
WDTCLR 喂狗，并在温度 0–45 °C、电压 3.0–4.35 V、电池在位和 CHGPROT 解锁的
守卫下执行；每次写入回读校验，守卫失败或喂狗失败会撤销 CHG_EN。充电电流、
输入限流和 4.35 V 浮充值仍是引导阶段的原厂配置，本轮不改。报告在
`Battery svc` 行末给出 `charge=` 结果；实机充电状态待回报。

v97 实测 `charge=kick-failed` 暴露出 WDTCLR 写 1 后自清：回读只有 0xec，
v97 拿 0xed 比对，误判失败并每周期撤销 `CHG_EN`，充电反复开关。v98
`BOOT749b7419` 只校验 CNFG_06 的保留位 bit7:2，写 NACK 时保留充电（看门狗
到期会自停），保留位变化才撤销 `CHG_EN`。稳定充电与电流符号待回报。

14:04:20 实机确认 `charge=kicked`、`CNFG_09=0xbb`、`CHG_DTLS=1`，charger
持续报告充电；但 gauge 电流仍为负（-215625 µA），与 SOC/电压上升并存，
电流符号暂不用于剩余时间。按机主要求，下一阶段转亮度。

v93 实测 SE0 `fw=0x303`（I²C 协议 3）、`status=0`、GPIO28/29 配置 `7/7`。
临时解除 slave AHB HWCG 后可读引擎，随后恢复。详见
[v93 结果](../evidence/power/battery-clock-v93/README.md)和
[v94 测量镜像](../evidence/power/battery-gauge-v94/README.md)。

先仅查询测量与 charger 状态，保留现有充电配置；充电控制、USB-PD、快充和温控
需要各自建立所有权及实测，不能以“电量已显示”替代。

## 亮度

本机活跃面板是 S6TUUM3。原厂 `ss_brightness_gamma_mode2_normal` 的 DBV 是
11 位，在线命令参数按低字节、再高 3 位写入；另有平滑开关、HBM、ACL、gamma／
温度／OTP 校准状态，不能只线性映射 UI 1–355 或套其他面板的 DCS 端序。
先限定 normal brightness，核对完整命令及映射表，再检查最小／中间／最大亮度和
设置滑块、渐变、错误恢复。亮度不依赖 GPU 移植。

## Wi-Fi

原厂记录见 `evidence/adb-2026-11-01/network.txt`。现有组件目录的 Ath12kWifi
针对 WCN7850 等 ath12k 硬件，QCA6390 属于 ath11k，不能只改 PCI ID 选中它。
可借用其平台回调／网络 ABI 设计，但无线核心及固件协议需要匹配 QCA6390。
已有设备固件清单保存 amss20.bin、m3.bin、regdb.bin 和多个 bdwlan 变体，尚未确认
实际 board-data 选择。先验证链路、MSI 和 DMA，再验证固件启动、扫描、WPA2、DHCP、
双向流量及重连，分别记录。

原厂驱动源码的路径、固定提交和 SHA256 见
`evidence/peripherals/source-audit/sources.json`；二进制和生成镜像仍在忽略目录。
