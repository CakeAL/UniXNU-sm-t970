# T970 连续触控 HID v76

v75 从三星 FTS 的 FIFO 读到了 27 次完整滑动。v76 在 v69 连续启动的基础上启用 `t970-touch-hid=1`。显示服务发布后，独立内核线程加载原版 HID 组件，再复用已实测的供电、身份读取和扫描序列。物理触点进入原版 `IOHIDDevice` 和 `IOHIDEventDriver`。指尖报告与边缘手势派发参考了同一 21H461 的 T733 实现。 [v75 实测](../touch-events-v75/README.md) · [T733 HID](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/3bb0d6f7840f088db6a0ec88ecb841e12042422f/package/T733TouchHid.cpp)

此版只在诊断内核编入触控且带启动参数时启用。硬件仍使用已实测的 GPIO 开漏 I²C。默认坐标变换为 `5`，即交换 X/Y，再反转交换后的 Y。横向 GOP 和原厂触控范围提供了方向依据。`t970-touch-transform` 的位 0、1、2 依次控制交换轴、翻转输出 X、翻转输出 Y。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --touch-hid \
  --output out/data-bringup/touch-hid-v76-build
python3.14 evidence/display/hello-black-v64/prepare.py --touch-hid
```

宿主触点测试覆盖坐标上下界、无按下的移动／抬起、无效 ID、双触点及 ID 重用。内核构建核对原版 HID 指令哈希、构造函数、207 槽虚表与私有符号绑定，并在重新链接后重复核对。

最终 BOOT FAT 回读通过。Heimdall 仅上传 BOOT，确认完成并请求重启。镜像哈希为 `03f21401d48aea2066f8d8188478c456f32d7f5750043d0fbce09a4e2d9db88b`。

机主确认上滑越过 Hello，进入下一页。交互与画面更新很慢，点击语言后画面停住。上滑推进了 Setup，确认 HID 路径工作。语言切换、坐标完整校准及实际帧率待测。 [机主实测](device-result.json)

下一轮在语言点击后同页采样 Setup、BackBoard、LaunchServices 等待与显示提交。若拒绝数增加，记录拒绝码、源与目标矩形和 IOSurface 尺寸。Sirius 的相近故障是在触控后更换画布时被显示校验拒绝。 [Sirius 实机显示记录](https://unixnu.com/devices/sirius-dddqmmx#display)
