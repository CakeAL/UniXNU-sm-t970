# 首帧后同进程线程对照

v34、v35 的 150 秒照片均采到 BB 在 QuartzCore setInvertsColors: 的 pthread mutex 等待，以及 SB 在控制中心模块查询中的 LaunchServices 上下文锁等待。v36 复用 v35 内核，仅把 t970-ui-stack=1 改为 5。现有 mode5 对 BB、SB 和 MobileGestaltHelper 各采样最多 8 条线程及有限调用栈，显示线程 ID、等待事件和工作队列。目标仍是 150 秒，保留 scanout hold。实机先看各进程标题、线程行和末尾 clipped 标记。线程是 best-effort 采样，重复地址不等于已找到持锁方。

运行 python3.14 evidence/display/ui-peer-stacks-v36/prepare.py。最终 FAT 回读确认只有启动参数中的采样模式变化。内核、ADT、trust cache、Data seed 和 payload 外部内容相同。

BOOT a30af66e477130dc9b7d760d577ddd9c34fe87012f2163c28d78414f8c660aab 已仅上传 BOOT，Heimdall 退出码 0 并请求重启。设备哈希未读回，实机结果待采。

独立对照 v34/v35 的原始缓存指令，两个进程各自都落在相同的去 slide 返回地址。BB 在取得第一把 mutex 后，尝试获取另一个显示对象偏移 0x18 处的 mutex。SB 等待 LaunchServices 固定缓存地址 0x1f4884878 上的锁。静态指令给出锁的位置，持锁线程仍需要运行时取证。见 lock-sites.json。

## 实机结果

屏幕在 BackBoard 第八条线程处到达下缘，SpringBoard 和批次结束标记均未显示。已有四次成功复制和退役。hold1 表示重试期结束后仍有在途写入，具体线程 ID 未采。符号确认 b3 在 QuartzCore 自己的 display timer 路径调用 IOMFB SwapEnd，b4 等 dispatch group，b1 处于 CFRunLoop。b3 只是一个候选，当前不能把它与 hold1 绑定。下一版将两进程的报告压为每线程一行，同时记录写屏线程 ID。
