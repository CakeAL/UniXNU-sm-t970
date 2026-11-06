# T970 触控事件探针 v75

以已实测亮屏的 v69 为启动基线，复用 v74 的两路供电与 GPIO 开漏 I²C。运行时诊断目标为 75 秒。只有读到 v74 实测的五字节身份 `53 54 39 36 03` 才启用扫描。探针轮询最多 20 秒，读取并统计三星 FTS 的 16 字节 FIFO 记录，再尝试关闭扫描并恢复引脚状态。GPIO15 仅作 IRQ 电平采样。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers \
  --output out/data-bringup/touch-events-v75-build
python3.14 evidence/display/hello-black-v64/prepare.py --touch-events
```

宿主模拟覆盖扫描命令顺序、扫描回显、FIFO 计数上界、同一触点的按下／移动／抬起与读取失败。内核预链接和最终 BOOT FAT 回读通过。BOOT 哈希为 `668f075b6520ef91c1a41d75d0af3ee0acfdeab1a314a1eb358edfc9d2468675`。完整镜像和传输日志保存在 `out/data-bringup/touch-events-v75/`。

首次 Heimdall 在握手阶段退出，未开始上传。第二次对同一镜像仅上传 BOOT，Heimdall 确认完成并请求重启。机主未见 Apple 标志，仍做了滑动。诊断页显示显示服务已发布，GOP 首帧时间与复制计数均为 0。

两路供电收到完成应答，芯片再次返回 `53 54 39 36 03`。FIFO 正常完成，298 次轮询中 49 次读到 IRQ 低，收到一次扫描回显，扫描关闭成功。统计为 28 次按下、356 次移动、27 次抬起。27 次为同一触点 ID 完成的滑动。最后触点为 ID 0、原始坐标 (281, 1196)。这个镜像验证了芯片到 XNU 的原始触点路径。下一轮在连续启动中验证 HID 派发和 Hello 手势。

实测照片与各字段见 [device-result.json](device-result.json)。
