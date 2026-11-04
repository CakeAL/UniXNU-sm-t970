# 首帧后两进程单屏诊断

v36 的 mode5 在第八条 BB 线程后触及屏幕下缘。v37 新增 mode9，仅采 backboardd 和 SpringBoard，各最多八条线程和每线程四级 FP。每条线程一行，保留十六进制 TID、状态、PC、LR 和帧读错误。紧凑模式省去逐核行、进程尾名单和工作队列统计，保留显示、Data、写屏状态及 UI batch end。现有模式的目标和输出保持原样。

原绘屏器在 2800×1752 下每列 18 像素，每行 42 像素。从第 227 像素开始约可显示 36 行。主机 sampler 测试在两进程都达到八条线程上限的情况下验证批次恰为 20 行、每行不超过 128 字符。实机先检查 UI batch end processes=2 clipped=0 以及 BB、SB 两个标题。

FB 行新增十六进制 writer，显示格式化时在途 CPU 传输的线程 ID。hold1 时可把非零 writer 与线程行的 id 比较。writer=0 也可能表示最后一次轮询与格式化之间已排空。采样早于 hold，TID 一致仅能关联同一线程，单次照片不能证明锁持有关系。线程不在前八条时可按已知 ID 安排下一轮定向采样。

先运行 python3.14 evidence/display/ui-compact-v37/build-kernel.py，再在 v35 的 mtools 与 LLVM 环境运行本目录 prepare.py。构建仅替换 late archive 中的两个板级对象，保留原件并逐成员比对。打包以 v35 为基线，最终 FAT 回读核对新内核、唯一变化的 t970-ui-stack=9、ADT、trust cache、Data seed 和镜像边界。沿用 150 秒终止诊断及写屏排空。

补充分析 v36 原始 backboardd 主程序。b1 和 b4 的已知调用各自推导出同一主程序 slide 0x7000。b4 对 dispatch_group_wait 传入无限期限，返回后才调用 _queue_applyDefinitions:。目前还未识别 group 的生产方或它和写屏的关系。见 v36-backboard-callers.json。

实际板级和 Mach-private 对象编译、XNU、prelink、最终 FAT 回读以及两项主机 helper 检查通过。平台检查在 DT/ADT 前因 UniXNU HEAD 与历史审阅版本不一致退出。BOOT ea3e7c1032bc4dec6efed15b665b929e4f7d95d1c1b8fb54b5e407874b9c2828 已仅上传 BOOT，Heimdall 退出码 0 并请求重启。设备哈希未读回，实机结果待采。

## 实机结果

完整显示 BB 八条、SB 五条和 UI batch end processes=2 clipped=0。hold0 writer0，两个帧已复制并退役。发布到首次复制间隔 123.810 秒。BB b1 在 AX 显示滤镜的 setGrayscale: 等 pthread mutex，b3 再次采在 SwapEnd。SB S1 重现 LaunchServices 上下文锁等待，S2 在同步 Mach 回复等待，四级调用栈未说明对端服务。hold0 说明采样结束时没有在途写屏，无法将上一轮 hold1 归给 SwapEnd。见 device-result.json。
