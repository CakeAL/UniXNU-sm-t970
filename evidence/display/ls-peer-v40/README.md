# x0 列证伪：ulock 等待者打印的是操作码，不是锁地址

v40 在紧凑行加 `a0=`（采样瞬间 x0），本意是让停在 ulock 的线程直接报出锁地址，并与 `LS waits` 行的 `addr` 自校验。

## 实机结果

自校验按预设失败：SpringBoard S1 停在 `__ulock_wait2`，`a0=1000002`，而 LS 锁地址是 `0x1fdda4878`；lsd 两条停在 `__ulock_wait` 的行是 `a0=1000001`。两个值对所有等待者一致，说明 x0 装的是 ulock 操作码，地址在 x1。采样器本来就保存了 x1（`arg1`），只是没打印，v41 加 `a1=` 列即可。

同一轮仍有独立收获：

- 第三次复现同一处 LaunchServices 锁：`addr=1fdda4878` = `0x1f4884878 + 0x9520000`（本页三个任务行都打印 `slide=9520000`），`waiter=125` 是 SpringBoard S1，`owner=576` 是 S2。
- lsd（p100，本次 6 线程全采）的安装进度子系统整体堵住：l1 在 `-[_LSInstallProgressService performJournalRecovery]` 里同步派发等队列所有权；l3 在 `restoreInactiveInstalls` 里等 dispatch group；l4 等的是 `___LAUNCH_SERVICES_CLIENTS_ARE_WAITING_FOR_THE_DATABASE_TO_FINISH_SEEDING__` 这个组；l5 自己也在 `_dispatch_mach_send_and_wait_for_reply` 等同步回复。v39 里那条 `-[LSDBExecutionContext syncRead:]` 争锁线程本轮没有出现——lsd 的线程数在两次启动间从 13 变成 6，该争用是启动相关的。
- 显示：这一轮 `hold=0 writer=0`，但 b3（id=2ab）仍停在 IOMFB `kern_SwapEnd` 的 IOKit 调用里；`vsync 1/0/0/0/0`、`notify=0` 再次出现。连续三次采样都看到 SwapEnd 调用者，而 hold 在 0/1 之间翻转，说明 hold 与"谁卡在 SwapEnd"不是同一件事。

## 局限

本轮 lsd 六条全采，但线程总数较 v39 少了一半，不能把两次的线程集合当同一状态。行内仍看不出每条 ulock 等待的目标锁，需 v41 的 x1 列。状态值只是有界采样，不是冻结快照。

## 下一步

v41 打印 `a0=`（操作码）与 `a1=`（地址）。判读：若 lsd 的 a1 等于 `0x1f4884878 + slide`，则 SpringBoard 与 lsd 争的是同一把共享缓存锁，是跨进程死锁；若不是，则 lsd 是 seeding 内部自锁，转向 l4 的组等待与 I/O。
