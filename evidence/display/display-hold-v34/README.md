# 终止诊断页保留和首帧时间

v33 机主看到 150 秒诊断页可见不足 0.5 秒，随后变回 Apple logo。当前绘屏 shim 在常规 panic 的 SMP 协调之前接管入口，其他核可能继续使用同一个 framebuffer。

v34 的 `t970-display-hold=1` 在显示启动时将一个板级 IOCommandGate 接到 Legacy 显示实例的 work loop。原版显示队列及同步 CPU 复制沿用同一 gate。终止报告在收集线程后尝试取得 gate。取得后标记诊断拥有 scanout，后续的 GOP CPU 复制及黑帧填充在现有准备回调返回失败。在 gate 内的旧帧操作已结束，诊断线程退出 gate 后才进入 panic 绘屏。最多重试 20 个 100ms 调度期限，失败时仍显示 best-effort 报告。

新行 `FB hold=… publish/first-copy ms=…/…` 中，hold 0 表示取得 gate 并阻止后续板级写入，1 表示重试后仍忙，-1 表示 gate 未安装，-2 表示其他 gate 错误。两个时间以 XNU absolute clock 为基准，分别记录显示注册回调和首个实际 CPU 表面复制完成。它们的差值可以估算服务发布到出帧的时间。0 代表尚未采到。时间和既有计数采样点略有不同。首个 CPU 表面不一定已经含 logo，也不包含黑帧填充。该 hold 只覆盖此 BOOT 使用的 GOP 写入路径，适用于主动终止诊断。

构建命令如下。构建脚本保留原内核和归档，将既有 late archive 中的板级对象替换为本轮编译产物，逐成员比对其余内容。打包以 v33 为基线，复现原 panic-screen 内核，然后对新内核应用同一补丁。最终 FAT 回读独立核对内核、唯一新增参数、ADT、trust cache、Data 种子和外层镜像边界。

```sh
python3.14 evidence/display/display-hold-v34/build-kernel.py
PATH="$PWD/.cache/bin:/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH" \
  python3.14 evidence/display/display-hold-v34/prepare.py
```

v34 保留 8 核、768 MiB 和 150 秒诊断。此次先检验能否稳定显示诊断页并取得首帧时间。组件已有源帧非黑像素边界扫描，后续可用它比较源 logo 几何与正面实拍。

板级对象、XNU 和 prelink 构建通过，最终内核中核对了报告、hold 和 timing 的符号。现有显示报告 ASan 测试及 Data 容量测试通过。平台总检查仍在 DT/ADT 前拒绝与历史审阅版本不同的 UniXNU HEAD。

BOOT `c9c49879eb2ad60d20c7e16bd843e72190918c660e2932fd89b09f86fa9bd05f` 已仅上传 BOOT，Heimdall 退出码 0 并请求重启。没有设备哈希读回，实机诊断页待采。见 `preparation.json`、`upload.json` 和 `flash.log`。

## 实机结果

机主拍到 150 秒报告，页面停留一秒多。hold=1 表示重试后仍未取得显示 work loop gate。显示发布和首次 CPU 复制分别在 XNU 时钟 18527、143217 ms，间隔 124690 ms。采到 6 次成功 swap、5 次实际复制和退役，软件 vsync timer start1/arm0/notify0。Data 仍可用约 305 MiB。

UUID 匹配的 symbols.json 显示 BB 已执行 BackBoard.axbundle 内的显示滤镜回调，采样时经 CAWindowServerDisplay setInvertsColors: 等 pthread mutex。SB 在控制中心查询模块关联应用时等待 LaunchServices 数据库上下文锁。此轮越过先前观测的 bundle 加载位置。尚未采到锁持有方、主屏幕或可交互界面。见 device-result.json。
