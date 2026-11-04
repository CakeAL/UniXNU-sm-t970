# 300 秒运行状态对照（待实机测试）

从机主此前观察到 Apple logo 的 `bb4d847476d455c0a49d28ffea03492e8e0f2b5fd0f2480ed2eb34dc5604912e` 构造。入口参数仅将 `t970-runtime-report=125` 替换为 `t970-runtime-report=300`；CPU 数、内核、ADT、trust cache、Data 种子、固件和 DTB 均保持，最终 BOOT 中重新提取 FAT 核验通过。`preparation.json` 记录哈希及具体参数。执行 `python3.14 evidence/display/display-late-v26/prepare.py` 生成忽略目录下的 BOOT 镜像。

该镜像是**终止式诊断**：运行状态采样启动约 300 秒后主动 panic 并显示计数及 backboardd/SpringBoard 栈，不是正常运行版。对照 125 秒的 swap、copy、retire 和线程位置，可提供后期是否推进的线索；不同启动之间计数差异不能单独证明持续刷新，实时采样栈也不是一致性快照。机主持续版观察是重启后超过三分钟 Apple logo 无变化，不能判断后台状态。机主已明确授权仅写 BOOT 并重启，Heimdall 上传成功、退出码 0 并请求重启，见 `upload.json` 和 `flash.log`；未设备读回。

## 实机结果

机主照片 `screen-target300.jpg` 显示 target300、main1、122 进程、CPU8/secondary7、SB27/BB57；显示 open7、swap7/0、transfer7、copy7、retire7、vsync0。125 秒镜像的 copy 为2，但这是独立启动，不能将数值差解释成同次运行中的增量或持续刷新证据。UUID 匹配的 `symbols.json` 显示 SB 首线程等 unfair lock，上层 LaunchServices/Control Center 栈与 125 秒照片相同；BB 首线程处于 CFRunLoop 的 Mach 消息接收。两个采样不能证明同一锁永久死锁，也未识别持锁线程。结果与照片哈希见 `device-result.json`。机主要求后续缩短等待时间。

本轮平台检查在读取 DT/ADT 前因 UniXNU HEAD 和审阅 pin 不一致而停止，详见 `evidence/display/display-continuous-v25/README.md`。该对照直接复用先前打包 ADT 并核对其哈希，不能把这项检查写成 DT/ADT 通过。
