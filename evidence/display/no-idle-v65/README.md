# 禁止内核空闲睡眠对照 v65

v64 的照片确认 IOService 电源管理看门狗超时。以已显示 Hello 的持续版 v63 为基线，仅添加 `noidle=1`。在实际构建的 XNU 源中，`IOPMrootDomain::start` 读取该参数，`startIdleSleepTimer` 检查 `gNoIdleFlag` 后提前返回。内嵌 ADT 没有覆盖用的 `/defaults/no-idle`。该开关隔离自动空闲计时器，保留其他电源路径及其看门狗。板级默认保持原样。

```sh
python3.14 evidence/display/owned-window-2g-v62/prepare.py --prevent-idle-sleep \
  --output out/data-bringup/no-idle-v65
```

从最终 BOOT 回读确认内核、ADT、信任缓存和 Data 种子与 v63 一致。Android v2 头、固件 FD、固件 DTB 及尾部逐字节相同。BOOT 已上传并请求重启。验证 Hello 是否能持续显示至少 1 分钟，观察同一 panic 是否重现。

机主观察到 Hello 后约 10 秒转黑。照片无可见诊断文字，所以只确认空闲计时器开关没有维持可见界面，尚不能确认同一 panic 是否重现。见 `device-result.json`。
