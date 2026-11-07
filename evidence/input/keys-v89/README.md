# T970 SPMI 侧键观察器 v89

继承实机成功的 v88 3840 MiB 请求，替换内核并加 `t970-keys=1`。
先只读 PON／GPIO 状态并记录按下和松开计数，不注入 HID。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --output out/data-bringup/keys-v89-build
python3.14 evidence/input/keys-v89/prepare.py
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/keys-v89/boot-partition.img
```

内核构建／prelink／原有 21H461 HID 绑定检查通过。BOOT：
`7b32d372d46233e314520f30d2523d1b74c72b75dfb2d900e0a4a21f9fed7013`。
Data、ADT、信任缓存及固件均保持；完整哈希见 `preparation.json`。
Heimdall 上传成功并请求重启，未做分区读回。

## 修正后的协议

对照原厂内核 `97e4a5b9…`，修正 dsh 的未接入头文件：

- `core+4` 是 `PMIC_ARB_INT_EN`，不是 APID 数量。按 DT 的 core 长度
  `0x1100` 与 APID 表偏移 `0x900`，扫描 512 项。
- PM8150 PON `RT_STS` 的按键位为 bit 0（电源）和 bit 1（音量减），不是 7／6。
- GPIO PPID `0x4c3` 仍取 `RT_STS` bit 0，低有效。
- 拒绝没有 EE0 所有权的映射；只有 observer 命令窗口可写，不映射 RW 通道。
- 输出缓冲区有界；主机 ASan／UBSan 测试覆盖小缓冲区、旧代状态位、外 EE、
  无效 APID、超时、错误完成、去抖、启动时按住和按下／松开。

`Keys:` 行包含版本、APID、mask、各键 press/release，以及 stage、samples、errors。
stage 5 为轮询中；2 为映射失败、3 为版本不支持、4 为找不到本 EE 外设、6 为连续
3 次读取失败后停止、7 为线程创建失败。原始状态每 16 ms 采样，两次一致才接受边沿。

实机步骤：进桌面后短按电源、音量加、音量减各两次，再三指按住取报告。
预期三个 `2/2`、最终 mask 0、errors 0。物理按键、HID 锁屏／音量、唤醒分别验证。

## 实机结果

进桌面，`v=50010000 pon=13 gpio=052 mask=2 power=2/2 up=0/0 down=2/2 stage=5 samples=13804 errors=0`。电源、音量减原始边沿通过；音量加未通过。
原厂 `pmic_gpio_pad.gpio_idx` 是从1开始的硬件编号，`pad->base=start+i*0x100`，所以 GPIO3 位于0xc200，正确 PPID 是0x4c2；v89误读了GPIO4的0x4c3。下一版只修正此地址再测试。HID未启用。
