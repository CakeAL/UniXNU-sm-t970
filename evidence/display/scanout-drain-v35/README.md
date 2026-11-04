# 终止诊断直接等待 CPU 写屏

v34 实机拍到 hold1。即使显示 work loop 的 gate 长时间忙，终止报告也需要阻止之后的帧覆盖它。v35 在已有的板级 CPU 写屏准备和传输完成回调跟踪写入线程。报告先关闭新写入准入，再按既有 20 个 100ms 调度期限等待正在进行的传输。hold0 表示当时没有已经准入的写入，hold1 表示超时后仍有传输，-1 表示未启用跟踪。

复核固定 GopFramebuffer cf3b429 的两个写屏路径。黑帧填充在准备后写入，CPU surface 路径同一线程可能调用两次准备。写入后先执行 store barrier，再调用传输完成回调。准备后每个提前退出分支也调用传输回调。只有原准入线程的完成回调可以释放写入。板级 GPU offer 始终拒绝，此检查适用于当前的同步 CPU 路径。

报告的 src-lit 给出原版已有 IOSurface 扫描首次检测到的非黑像素包围框宽高，0x0 表示尚未采到。它可与正面拍摄画面比较，并需先确认两者对应同一图案。扫描结果可能先于复制完成。

运行 python3.14 evidence/display/scanout-drain-v35/build-kernel.py，再用 v34 相同工具环境运行本目录 prepare.py。打包只换入新内核，保留 v34 的启动参数和 150 秒报告。两个主机 helper 检查分别覆盖显示格式化和写入准入关闭、重入及不同线程完成。

完整构建、内核预链接、最终 FAT 回读、两项主机 helper 检查通过。BOOT 0c99c6d4e218ee18879d122a24e13fb05e0a82f91e92170567f4c73e4684e2cf 已仅上传 BOOT，Heimdall 退出码 0 并请求重启。设备哈希未读回，实机结果待采。

## 实机结果

150 秒照片为 hold0，显示发布 23919 ms、首次复制完成 144518 ms，间隔 120599 ms。open8、swap4、copy/retire 各3，timer start1/arm0/notify0。诊断页已可拍摄，停留时间未测。src-lit=366×176 是首次非黑源区域，尚无证据将其与屏幕上的 Apple logo 一一对应。

UUID 匹配的符号显示 BB 再次在 AX 显示滤镜到 QuartzCore setInvertsColors: 的 pthread mutex 等待，SB 再次在控制中心的 LaunchServices 数据库上下文锁。两次均有实际帧退役。下一轮可用已实测的 mode5 扩大线程采样，查同进程中同时活动的队列及等待链。
