# SpringBoard 防调暗对照 v68

v67 在 Hello 后明确将 GOP 填黑，XNU 仍运行到 240 秒。Sirius 的 [BootWatchdogPolicy.c](https://github.com/dddqmmx/UniXNU-sirius/blob/b0e8023540f212625bd86a32a8bb512b410b59ed/package/BootWatchdogPolicy.c#L95) 提供三个 SpringBoard 偏好键。原版 21H461 的匹配 UUID 符号确认 `SBIdleTimerDefaults` 注册 `SBDisableAutoDim` 和 `SBDontDimOrLockOnAC`，且其 `disableAutoDim` 方法也引用前者。`SBPowerDefaults` 注册 `SBDisableIdleSleep`。见 `key-sites.json`。

```sh
python3.14 evidence/display/springboard-dim-v68/prepare.py \
  --output out/data-bringup/springboard-dim-v68
```

两份 BOOT 共用 v67 的内核、ADT、信任缓存和固件，改为一次性 RAM Data，报告设在 360 秒以留出新 Data 的启动时间。对照版使用原始 512 MiB Data 种子。实验版在它的副本上只合并这三个布尔值到 `mobile/Library/Preferences/com.apple.springboard.plist`，保留 APFS 卷 UUID、UID 501、权限 0600 和 Setup 流程。与 v67 的直接对比混入持久 Data 与新 Data 的差异，因此必要时应运行同组对照版。

两份镜像从最终 BOOT 内的 FAT 回读核对。实验版已上传并请求重启，对照版暂留主机。机主确认本轮未转黑。360 秒终止诊断时有 253 次成功复制及退役，`blank/dark=0/0`，最近一次复制时刻为 379.990 秒。未运行同组 RAM Data 对照，因此暂不能把改善单独归因于三个偏好键。见 `device-result.json`。后续使用 [v69 持续启动](../springboard-dim-continuous-v69/README.md)。
