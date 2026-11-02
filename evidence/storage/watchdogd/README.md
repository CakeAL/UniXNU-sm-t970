# 系统服务阶段：watchdogd SIGTRAP

BOOT6b83f4e6在修复PMGR空实现后，机主先报告超过2分钟无新画面的紫条，随后18:42照片出现
watchdogd[102] exited / namespace2 / subcode5。当前XNU的reason.h与signal.h解码为SIGTRAP。
这是实际服务启动证据；不是“紫条证明正常”，也不是launchd退出。

本版Data挂载路径在init exec前强制验证准确设备、APFS与非只读标志，任一失败即panic。
因此可从watchdogd服务已执行推断Data成功越过该挂载检查；没有单独Data读写或持久化测试。
没有EACCES抓取、UFS integrity=0、累计读取1245978块，并不排除其他未观测的问题。
PID1旧路径追踪的/etc/group不能当作watchdogd故障路径或文件损坏证据。

离线运行原watchdogd（固定ded4c688摘要）显示：缺IOWatchdog服务、打开服务失败可触发BRK；
虚拟机缺服务和连接成功是不同分支。报告保留OS API替身与未捕获实机PC的限制，
不能把推测的缺服务分支当作本板已经证实的精确故障点。

[T733 board](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/3bb0d6f7840f088db6a0ec88ecb841e12042422f/board.toml)
选择sheng-disable-watchdogd=1，其
[启动补丁](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/3bb0d6f7840f088db6a0ec88ecb841e12042422f/patches/t733-xnu/zzz-boot-progress.patch)
在Data挂载后调用可选sheng_boot_watchdog_policy。本板没有这个helper；只加参数不会生效。

disabled.plist是下一步的候选原launchd配置，只含com.apple.watchdogd=true，尚未应用。
现有框架check-launchd-watchdog-policy.py执行固定原launchd8cec9a3c的loader、UID检查及job gate，
三例通过：root配置跳过watchdogd、非root拒绝、其他job不跳过（文件系统/libxpc依赖显式替代）。
正式应用必须在RAM Data中创建root-owned文件和迁移标记，保留其他已有设置，
不得直接覆盖未核验的disabled.plist、吞掉panic或声称硬件watchdog已实现。
