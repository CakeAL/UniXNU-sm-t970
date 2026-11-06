# T970 跳过设置助手 v84

传输页在 v82、v83 都没有推进，Setup 的 4 个线程全部在等待。框架文档给出的标准做法不是逐个修设置页，而是**在 Data 种子里把设置标记为已完成**，让设备直接进 SpringBoard。 [skip-setup 指南](https://unixnu.com/guide/skip-setup) · [v83 报告](../setup-fb-cache-v83/README.md)

v84 只替换 BOOT 里的 Data 种子，内核、ADT、信任缓存、启动参数和固件都与 v83 相同：

```sh
python3.14 evidence/display/setup-skip-v84/prepare.py
```

- 调用框架的 `scripts/seed-data-skip-setup.py`（来源标注为 `github.com/dipa-studio/ios-sweet` 的 `tools/sweet-root-tweaks.py`）。
- 写入 `com.apple.purplebuddy` 的 `SetupDone`、`SetupFinishedAllSteps`、`SetupVersion=11`、`daemonizeNeedsToRun=false`，关闭全部 mini-buddy 步骤，写 `com.apple.migration` 的 `LastSystemVersion=21H461` 与 `DMUserDataDisposition`，并加 `BKNoWatchdogs`、`FBLaunchWatchdogExceptions`、`MCForceShowCloudConfigurationUI=false`。
- `--no-auto-dim` 同时关闭自动调暗与空闲睡眠，避免无按键板在 SpringBoard 启动约 30 秒后熄屏。
- 另外创建 `containers/Bundle`、`Data/System`、`Shared/SystemGroup`、`Temp`。

BOOT 哈希为 `215edec49f9ebf641b2b312f954416eb35e0d4347473b4bf97dd5581857b68cb`，Data 种子 `9a0005a5c520412006589e068264b611c3484af123547d13103387a9fb7c0afa`。内核、配置、ADT、信任缓存和固件字节均未变，BOOT 头部与分区尾部回读一致；Heimdall 确认上传并请求重启。

实机待确认：是否直接进入 SpringBoard 主屏。若进了主屏，可以再按住三指取一次运行时报告；若仍是设置助手或黑屏，报告会给出卡点。

## 实机结果

机主确认进入桌面，状态栏显示 `4:08 PM Wed Dec 31`，SpringBoard PID 27。 [桌面照片](screen-home-screen.jpg) · [机主读数](device-result.json) · [符号化](symbols.json)

- `Setup life exec=0/0/0`：本次启动 Setup.app 根本没有运行，种子里的 purplebuddy 标记生效。
- 显示：13 个客户端、277 次 swap、276 次拷贝与退休、0 拒绝；拷贝 `42531/49297` us，与 v83 一致，缓存设置继续生效。
- 278 个进程、983 个线程；accountsd 6 线程、backboardd 23 线程、SpringBoard 17 线程。
- 桌面 408 秒里 276 帧（约 0.68 帧/秒），静态主屏足够；应用启动动画会明显吃紧。
- LaunchServices 仍有 1 个等待者（SpringBoard 首线程 `0x129`），持有者 `0x7f4` 未采到。

至此显示领域从 `planned` 升到 `implemented`：用户态呈现已在实机证实，亮度控制和持续动画仍未验证。

机主随后报告：**应用可以打开并正常显示，但启动需要一些时间**（未测量）。这证实「SpringBoard → 应用 → 显示」链路已经通了，剩下的瓶颈是性能，不是兼容性。
