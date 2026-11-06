# T970 语言页取证 v77

v76 已实测通过手指上滑越过 Hello。机主在点击语言后看到画面停住。v77 在 v76 BOOT 上加入 `t970-setup-probe=1` 和 360 秒终止报告。显示归档中仅替换 `DisplayRegistration.o` 与 `UiWaitSnapshot.o`。归档逐成员比较确认 v76 的 HID、GOP 和原版绑定对象相同。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe \
  --output out/data-bringup/setup-language-v77-build
python3.14 evidence/display/hello-black-v64/prepare.py --setup-probe
```

- `Setup down` 是最后一次 FTS 按下进入 HID 之前的时刻与累计接受、拒绝、复制数。将它与报告顶部的累计数比较。此行也记录最后一次和最大 CPU 像素复制时间，单位为微秒。时间覆盖像素复制和写屏屏障。
- `Setup reject` 是最近一次拒绝及其时刻，`geo` 是最近一次可读取尺寸的拒绝时刻。`Setup r0/r1` 与 `surf` 属于后者。零时刻表示尚未捕获对应事件。
- `stacks=11` 是紧凑的 Setup 栈模式。最多采样 Setup 三条、SpringBoard 一条、BackBoard 两条、lsd 两条，每条至多四级用户栈。快照与显示计数在同一报告中，采样各字段之间有时间差。

宿主 ASan/UBSan 核对了按下计数快照、打包矩形、拒绝时刻与复制耗时，以及 Setup 进程筛选、用户栈读取上限和原模式 10。仓库测试运行 54 项，44 项通过、10 项跳过。内核预链接、原版 HID 绑定复核和 BOOT FAT 回读通过。完整 DT/ADT 检查仍受主仓库审阅版本约束。

BOOT `d44b077ee9ce3602351dd472f1b873df15074a0320e03161bc1f58c41393e9fb` 已上传，Heimdall 请求重启。实机报告已收到，整屏照片及读数见 [device-result.json](device-result.json)。

最后一次 FTS 按下时累计接受 15 帧、复制 15 帧。报告时已经接受并复制 18 帧，全部退役，拒绝为 0。最后一帧在按下后 10.868 秒完成。最近一次像素复制为 265.972 毫秒，最大 292.623 毫秒。这个耗时只覆盖像素复制和写屏屏障。360 秒报告中没有 `Setup` 进程行。

LaunchServices 记录了一次锁等待，地址等于已知锁加本次 slide，等待者为 SpringBoard `0x12a`，记录的持有者为 `0x72f`。SpringBoard S1 的保存栈在同步 Mach 回复调用。持有线程未采到，记录无法证明报告时仍持锁。BackBoard 两条栈和 lsd 第一条在运行循环收消息。Data 约 124.5 MiB 可用，UFS 累计 577196 次读、0 次失败、平均 139 微秒。单次报告无法把卡住归因给容量或内存。 [符号化](symbols.json)
