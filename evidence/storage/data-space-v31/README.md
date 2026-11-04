# 运行时 Data 空间诊断

参考其他 iPadOS 移植曾因 Data 卷 ENOSPC 阻止界面启动；本板尚无运行时空间数据，不能据此认定已满。对 512 MiB 原始种子做哈希核对后，以只读方式在主机附加、查询并卸载，初始 APFS 容器空闲 534294528 字节；该值不包括设备启动后的写入，见 `../data-space-survey/initial-seed.json`。

新增仅在 `t970-data-space=1` 和现有终止报告启用时运行的检查：隔离 worker 只读查找 `/private/var`，核对其为已认证的 RAM Data 设备、可写 APFS 后请求当前 `f_bsize/f_blocks/f_bfree/f_bavail`。`support` 标记哪些字段由文件系统提供；失败的 errno、设备不匹配、未支持字段或 pending 不能解释为零空闲。报告线程最多等待20个100ms调度期限，超时显示 pending，不读取未完成结果；这不是严格墙钟上限，也不会取消可能仍在运行的 worker。没有修改文件或扩大卷。

实际 helper 的 ASan/UBSan 测试覆盖成功、lookup/getattr 失败、设备不匹配、worker 启动失败和超时；真实 BSD 编译、完整内核/预链接、最终 FAT 回读及参数检查通过。最初构建因 BSD 头缺少 `thread_terminate_self` 声明失败，修复声明后构建时旧的缺失对象被 archive 检查拒绝；按原 BSD 配方补编该对象后完整构建成功，旧内核和归档保存在忽略目录 `out/data-bringup/pre-data-space-v1/`。

BOOT `e0a2d8586cbf2123c0943d6d7f52ea0b649e8eee50fffdb32d1448fe5fced8fb` 保持八核、768MiB 请求和125秒终止报告，同时显示 Data 空间及原有 UI/帧计数。机主授权 BOOT 上传及重启，Heimdall 报告上传成功并请求重启，未设备读回，见 `upload.json`、`flash.log`。Data 状态应与支持位及错误码一起解读。`check-platform.py` 因当前 UniXNU HEAD 和历史审阅版本不同，在 DT/ADT 检查前退出；不能标为通过。

## 实机结果

机主照片中的 v31 专有容量行显示 `rc=0 phase=1 support=1d0`。四个请求字段均受支持，块大小 4096 字节，总块数 131072（512 MiB），空闲和可用各 78135 块（320040960 字节，约 305.2 MiB）。这次报告时，可写 RAM Data APFS 有余量。较早瞬时错误、其他卷以及单次写入失败仍需各自的运行证据。报告是主动终止，125 秒是线程配置的采样期限。

同屏记录 main1、110 个进程、八核及七个副核。显示阶段 8，已映射并发布，open7，成功 swap、transfer、copy、retire 各 2，vsync0。125 秒的既有基线也报告 2 次成功退役。设备主屏幕仍待验证。

以 `scripts/symbolicate-ui-registers.py` 和 UUID 匹配的 21H461 原始 ARM64 缓存解析 slide `0x5a4000`。SpringBoard 首线程在 `sb_defaultContext`，上层为 `SBApplicationSupportServiceDelegate` 和启动前系统服务初始化。其 PC 去 slide 后为 `0x1cfc502bc`，原指令是 `ldr x8, [x8, #0xfd0]`。BackBoard 首条采样线程在 Objective-C `_map_images_nolock`，经 dyld 和 Foundation 加载 bundle，PC 处为 `ldr x28, [x23]`。两处均为一次采样的执行位置。BB 调用链的 `0x100455b44` 缺少主程序 slide，暂留为未解析。见 `device-result.json` 和 `symbols.json`。

下一次显示定位优先分辨软件 vsync 的事件阶段。已审阅的 GopFramebuffer `cf3b429` 仅在客户端队列非空时 arm 计时器，现有板级 `vsync` 计数只记录通知事件 1，创建（4）、arm（0）、空队列停发（2）以及刷新属性调用（5）未在终止报告区分。先补事件计数，再根据实机结果决定排查 timer 初始化、客户端注册或计时器执行。
