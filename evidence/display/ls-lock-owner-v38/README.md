# SpringBoard LaunchServices 锁持有者采样

v37 完整显示两进程报告。SpringBoard 的 S1 重复采在 LaunchServices 上下文锁，S2 等同步 Mach 回复。单凭两条调用栈不能确定 S2 是否持锁。

v38 以 21H461 的去 slide 锁地址 0x1f4884878 为基线，仅在 t970-ls-owner=1 时观察 SpringBoard 的匹配 unfair-lock 等待。筛选进程名、操作码、页偏移和原缓存允许的 slide 范围。在原 syscall 已经校验用户锁值、解析持有者并进入 THREAD_WAITING 后，复制等待者和持有者 TID。读写诊断记录使用不等待的 try-lock，竞争时可丢样本。正常 ulock 行为沿用原代码。

150 秒的单屏报告加一行 LS waits/addr/waiter/owner。count 是成功记录次数，后面是最近一次记录，不是终止瞬间持锁证明。先核对 addr 等于 0x1f4884878 加 SpringBoard 标题上的 cache slide，再按十六进制 waiter/owner 对照线程行。若命中 S2，则能把同一次解析中的持锁者与该线程的采样栈关联，仍需核对时序。零次数或地址不符都没有确认目标锁。

打包用 v37 的内核和 BOOT 作核验基线。重新构建 XNU 后，执行本目录 prepare.py。最终 FAT 回读检查保留 mode9、150 秒、写屏排空、ADT、trust cache、Data 种子和外层镜像，只加入新内核和诊断参数。
