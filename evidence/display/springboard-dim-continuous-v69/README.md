# 防调暗持续启动 v69

v68 实验版实测未转黑。v69 从该镜像仅移除 `t970-runtime-report=360`，让 Setup 继续运行。

```sh
python3.14 evidence/display/springboard-dim-v68/prepare.py --continuous \
  --output out/data-bringup/springboard-dim-continuous-v69
```

最终 BOOT FAT 回读确认内核、ADT、信任缓存及防调暗 Data 种子摘要与 v68 实验版一致。固件、Android v2 头、固件 DTB 和尾部逐字节相同。设备已接收 BOOT 上传并请求重启。机主确认 Hello 可以保持显示，手指上滑和电源键无响应，未到主屏幕。见 `device-result.json`。


SM-T733 的 [触控接入](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/3bb0d6f7840f088db6a0ec88ecb841e12042422f/package/T733Touch.cpp) 为 Focaltech／GENI SPI。[同为 21H461 的 HID 派发](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/3bb0d6f7840f088db6a0ec88ecb841e12042422f/package/T733TouchHid.cpp) 可用于 ABI 对照。T970 的手指触控是 STM FTS／GENI I²C，电源键由 PM8150 PON 单独上报。先在测得的 SE5 读到芯片 ID 和 FIFO 触点，再绑定 HID。触控和电源键单独验证。
