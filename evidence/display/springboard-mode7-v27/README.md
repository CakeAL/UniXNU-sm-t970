# 90 秒 SpringBoard / lsd 采样

针对 300 秒照片与 Poco F1 移植记录中高度相似的 LaunchServices 锁等待，新增显式 `t970-ui-stack=7`：只选择 SpringBoard 和 lsd，各最多前四线程，每线程最多八级 FP 栈；沿用隔离 worker、task/thread try-lock、VM map 引用和超时后隐藏未完成数据的机制。其他模式保留。活线程栈不是原子快照；无进程行不证明其从未启动；输出结束标记的数量和 `clipped` 值需结合两进程标题检查，屏幕本身仍可能截断。

BOOT `aeb13ffcb50b8f2d22819e2daf7de6a7b22b07a6815cb95aaac95652322ca5c8` 为 8 核、768 MiB 内存请求、90 秒**终止式**诊断；90 秒从内部报告线程启动起算，可能比机器重启晚。采样时机过早可能尚未进入先前等待链。机主已授权 BOOT 上传及重启，Heimdall 报告成功、退出码 0 并请求重启，见 `flash.log` 和 `upload.json`；没有设备读回。先前 v24 内核和两版候选均保留在忽略目录，未改变默认 DTS 或内存配置。

本机 helper 测试用 ASan/UBSan 验证模式选择、读取上限、非目标过滤和 map 引用释放，Mach-private ABI 编译、内核链接/预链接、FAT 回读及打包校验通过；`kernel-sampler-disassembly.txt` 的比较边界对应允许模式 1–7。`check-platform.py` 因 UniXNU HEAD 不等于历史审阅 pin，在 DT/ADT 检查前退出；不能标记为通过。

参考对照和证据边界见 [UI 启动对照](../../../docs/ui-reference-comparison.md)。`reference-check.json` 记录原始 21H461 MobileGestalt 映像中的相关字符串及 v24 ADT 对应属性缺席；它没有确定代码交叉引用或运行时调用，不证明相同根因。

## 实机结果

照片 `screen-target90.jpg` 显示 main1、CPU8、SB27、BB57、lsd97，open5、swap0；`UI batch end processes=2 clipped=0`，两组标题和报告尾部均可见。lsd 有7线程，此次采前4：线程1在安装日志恢复路径等待 dispatch 队列；线程2在恢复 inactive installs 时等待 dispatch group；线程3经 XPC 请求进入“等待数据库 seeding 完成”的函数并等待 dispatch group；线程4在工作队列入口。SpringBoard 首线程当时等 BackBoard 主屏幕信息，并非更晚时的 LaunchServices 调用链。符号与采样见 `symbols.json` 和 `device-result.json`。

这些实时栈并非原子快照；线程5–7和数据库 seeding 的具体阻塞点仍未知，照片不证明 Wi-Fi 地址查询是原因。90 秒未出现帧说明它比先前出现 Apple logo 的阶段更早，应避免把本次 `swap0` 当作回归。
