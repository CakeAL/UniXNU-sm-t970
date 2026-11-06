# T970 SpringBoard 提前退出取证 v80

v78 在点击语言后收到 SpringBoard PID 27 的 SIGKILL。符号化确认栈从 `postsig_locked` 进入 `exit_with_reason`。配置中的 `panic_on_error_exit` 提前打印并终止了该次启动。v80 使用 v77 的普通写屏基线，并加入进程生命周期和退出原因两个诊断参数。 [v78 实测](../setup-copy-diff-v78/README.md)

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe \
  --output out/data-bringup/setup-exit-v80-build
python3.14 evidence/display/hello-black-v64/prepare.py --setup-exit
```

- `T970 UI exit` 拆分原始 wait status、信号编号和进程退出码。
- `reason` 输出退出原因命名空间、代码及标志。 `jetsam` 是调用时的 jetsam 标志，`caller` 是执行退出路径的当前进程。
- `signal metadata` 仅从内核保留的信号原因数据读发送者名称与 PID。若该数据缺失则显示 `-/-1`。 `desc` 保留有界的可打印描述。
- 若未触发提前终止，仍在 360 秒采集帧计数、Setup 生命周期和 LaunchServices 持锁线程。

宿主 ASan/UBSan 验证了参数开关、发送者数据长度、退出码和信号拆分、jetsam 与描述。内核预链接、原版 HID 绑定核对和最终 BOOT FAT 回读通过。BOOT 哈希为 `708d44b95fa26fe16ec055650b66af7e9bfad5f88c6dff30fca361718c8653ad`。Heimdall 已确认上传并请求重启。实机确认 SpringBoard PID 27 收到 SIGKILL，原因域 10、代码 `0x5BC1EA44`、标志 5，`jetsam=0`。描述开头是 `RBSTerminateContext`，可见的说明止于 `SBRe`。因此 v78 的差分复制开关并非复现此终止所必需。Sirius 实测同一原因码之后 SpringBoard 和 Setup 均重新启动。T970 的退出诊断在重启前就触发了 panic。 [本机读数](device-result.json) · [Sirius 实测](https://unixnu.com/devices/sirius-huajifruit#input)

28 秒后的照片显示 `wait_while_equals32` 超时。按本次内核符号化，堆栈落在 `task_restartable_ranges_synchronize` 等线程确认的路径。它与前一条 panic 的因果关系尚未验证。下一版仅对实测的 SpringBoard 原因允许重启，并持续运行以判断超时是否重现。

对 21H461 原版 arm64 共享缓存检索载入原因码的两条指令，在 `0x1d0012718` 找到 `mov w2, #0xea44` 和 `movk w2, #0x5bc1, lsl #16`。UUID 匹配的本地符号把该地址定位到 `-[SBRestartManager _doRestartForTransition:] + 344`。 [原版代码符号化](relaunch-code-symbols.json)
