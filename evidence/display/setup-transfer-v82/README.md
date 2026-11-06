# T970 传输页手动报告 v82

v81 已通过语言切换并到达「传输 App 与数据」。机主选择不传输任何内容后，右上角持续转圈，点击响应仍然很久。v81 依靠 360 秒定时报告，需要等 Setup 自行走到端点。v82 保留 v81 的启动参数，把报告改为机主主动触发，并让采样窗口覆盖账号服务。 [v81 实测](../setup-relaunch-v81/README.md)

- `t970-setup-report-touch=1`：触控驱动在读到恰好三个接触点并持续两秒后，立即请求一次运行时报告，不再等待定时器。
- 报告沿用 panic 屏，打印后不复位。 `native_t970_runtime_started` 只置位一次，因此每次启动只能触发一次。
- 采样窗口同时选中 Setup、SpringBoard、backboardd、lsd、accountsd 和 akd 六个进程，Setup 最多读取 6 个线程，其余 1 个。
- 报告仍包含帧计数、CPU 副本延迟、Setup 生命周期和 UI 等待栈。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe \
  --output out/data-bringup/setup-transfer-v82-build
python3.14 evidence/display/hello-black-v64/prepare.py --setup-transfer
```

宿主 ASan/UBSan 覆盖开关解析、accountsd/akd 选择、6 进程与 6 线程上限和结束行未裁剪。仓库测试 54 项，44 项通过、10 项跳过。内核编译、预链接、原版 HID 绑定复核及最终 BOOT FAT 回读通过。BOOT 哈希为 `81f47cd6a07f6ee1f12fbe8eed6e5af396fde87587ed37035663875a20f5d9f7`。Heimdall 确认 BOOT 上传并请求重启。实机结果待采集。

实机步骤：进入「传输 App 与数据」并选择「不传输任何内容」后，用三根手指同时按住屏幕约 2.5 秒，随后拍摄 panic 屏报告。

## 实机结果

机主在传输页按住三指后报告正常打印，转圈仍在。 [报告照片](screen-transfer-report.jpg) · [机主读数](device-result.json) · [符号化](symbols.json)

- Setup 进程只有 4 个线程，全部在等待：两个在 `CFRunLoop` 的 Mach 端口等待，一个在 `dispatch_mach_send_and_wait_for_reply` 同步等回复，一个空闲在 workqueue。 accountd 与 akd 各只采到首线程，均在 `CFRunLoop` 空转，没有在处理请求。
- `Setup life exec=2/394/0 exit=1/273/9 reason=10/5bc1ea44`：语言切换的重启同样杀掉了 Setup，随后以 PID 394 重新启动。这与 v80 的 SpringBoard 原因码一致。
- 显示侧共 548 次拷贝、548 次退休，0 次拒绝。最后一次拷贝 `326897` us，最大 `331681` us；首帧 134.4 s，末帧 471.6 s。改动区域只有 `366x176`，但每次仍复制整帧 19.6 MB，约 60 MB/s。

因此转圈不是账号服务卡住：accountd/akd 空闲，Setup 只有一条同步 XPC 回复在等。真正拖慢交互的是整帧拷贝的固定开销。 v78 的差分拷贝只写变化的 64 字节块、仍要读整帧，实测与普通拷贝同速（143–285 ms），说明瓶颈在源表面读取，而不是写屏。
