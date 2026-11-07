# T970 独立消费控制 HID v91（已刷，系统行为待确认）

在 v90 三键原始状态全部确认后，已启用 `t970-keys-hid=1`。
v90三键原始状态已全部确认。v91完成内核构建、prelink、21H461 HID ABI核对和镜像打包，
已上传并重启；锁屏／音量的系统行为待机主反馈。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/keys-hid-v91-build
python3.14 evidence/input/keys-hid-v91/prepare.py
```

BOOT `65026b210ef6765aef37e08ddf49e2160a0060a98b04a9da8e3fa194f7dbcac4`。
完整构建和镜像哈希见 `preparation.json`。旧 v89/v90 源码快照的 SHA256 与已编译输入核对一致，
分别位于 `../keys-v89/source` 与 `../keys-v90/source`，避免把后续 HID 代码误当成旧镜像实现。

## 接入

- 复用已核对的 T970TouchHid 原始 IOHIDDevice ABI，创建独立 keyboard／consumer 服务。
  触控保持 Digitizer/Touch Screen 主用途，不改变触控描述符。
- 键盘／Consumer report 2 描述符来自 BSD-2-Clause-Patent 的
  [ShengHidInput@5f3a37ce](https://github.com/UniXNU/ShengHidInput/blob/5f3a37cec0c3fc4234b10726b25489a55f0d77ef/NativeHidInput.cpp)。
  Power、Volume Increment、Volume Decrement 分别使用 report 2 的 bit1/2/3；Home 位保持0。
- 所有事件经独立服务的 work loop 序列化；等待事件驱动出现，失败时保留未完成状态并重试。
  启动时按住的键先松开再接受按下；传输错误时尝试清空按住状态。
- 观察器仍要求 `t970-keys=1`；只有额外的 `t970-keys-hid=1` 才允许发送事件。
  `Keys:` 增加 `hid=启用/成功报告数/最近返回码`。

## 实机验收

1. 原始三键计数和空闲mask通过后才使用本镜像。
2. 先测音量加／减，确认系统音量 UI 和按下／松开报告；检查无卡键和重复事件。
3. 再短按电源，分别记录锁屏与再次点亮；硬件休眠／恢复不是同一验收项。
4. 重复和同时按键后仍能触控、三指取报告，记录各键计数、hid返回码和管理页数。

系统屏幕电源切换和实际亮度控制还没有适配；若锁屏后黑屏，保留这条观察并回到 Download，
不要把黑屏直接当作内核崩溃或已实现休眠。

## 实机结果

2026-11-07 12:30:44：`mask=0 power=4/4 up=14/14 down=30/30 stage=5 samples=18626 errors=0 hid=1/97/0`。97次成功HID报告与96个边沿加一次初始松开报告一致。机主确认短按电源可以锁屏、再次点亮；音量键有响应，但系统音量调节不可用，未观察到音量值变化。缺少音频后端是合理的待核实原因，不能把它写成已证实故障原因。硬件休眠／恢复和实际音量变化仍未验证。照片及哈希见 `device-result.json`。
