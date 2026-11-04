# 三进程同页：SpringBoard 等 lsd，lsd 卡在数据库 seeding

v38 已证明 LaunchServices 上下文锁的持有者就是 SpringBoard 自己的 S2，而 S2 在等一条同步 Mach 回复。v39 新增 mode 10，把 lsd 与 backboardd、SpringBoard 放进同一页：每进程行格式与 mode 9 相同，线程上限 backboardd 8、SpringBoard 6、lsd 6，栈读 4 级。

## 实机结果

同一处锁在新 slide 下复现：`LS waits=1 addr=210f90878 waiter=125 owner=522`，`0x1f4884878 + 0x1c70c000 == 0x210f90878`，与三个进程各自打印的 slide 一致；waiter 是 SpringBoard S1，owner 是 S2。

lsd（p97，13 线程采 6）自己也是堵住的，且堵在数据库 seeding：

- l2/l3 在 `-[_LSInstallProgressService restoreInactiveInstalls]` 里调用 `-[LSDatabaseBlockingFetchClient getServerStoreBlockingWithCompletionHandler:]`，停在 `__dispatch_group_wait_slow`，调用方符号名为 `___LAUNCH_SERVICES_CLIENTS_ARE_WAITING_FOR_THE_DATABASE_TO_FINISH_SEEDING__`。
- l1 在 `-[_LSInstallProgressService performJournalRecovery]` 里做同步派发，停在 `___DISPATCH_WAIT_FOR_QUEUE__`/`__dispatch_kq_poll`。
- l6 替客户端执行一次数据库读：`-[_LSDService connection:handleInvocation:isReply:]` → `-[_LSDReadClient invokeServiceInvocation:isReply:]` → `-[LSDBExecutionContext syncRead:]` → 停在不公平锁。
- l4 状态 9（不可中断），停在 `-[_LSLazyPropertyList objectForKey:ofClass:]` ← `_LSStringsFileContent subscriptLoctableWithLocale:` ← `gatherLocalizedStringsForCFBundle:`，即读 bundle 本地化字符串时不可中断等待。

因此 S2 等不到回复不是服务缺失，而是 lsd 的 seeding 阶段自锁：seeding 未完成 → 读线程 l6 拿不到数据库锁 → 回复不发 → SpringBoard S1 拿不到 LS 上下文锁。

显示侧这一轮还出现 `FB hold=1` 与 `writer=314`，而 backboardd b3 的 `id` 正是 314，b3 停在 IOMFB `kern_SwapEnd` 的 IOKit 调用内。这是第一次把未排空的 scanout 保留与具体线程对上号。

## 局限

lsd 采的是 13 线程中的 6 条，backboardd 是 20 中的 8 条，行集不是冻结快照。行内不打印 ulock 地址，所以无法判断 l6 等的是共享缓存里的 LaunchServices 上下文锁，还是 lsd 内部另一把锁。单张照片也不能给 l4 的内存等待与 l2/l3 的 group 等待排序。

## 下一步

v40 在每行加 `a0=`（采样瞬间 x0，即系统调用第一个参数），让停在 `__ulock_wait2` 的线程直接把锁地址打出来：若 lsd l6 的 a0 也是 `0x1f4884878 + slide`，这就是跨进程共享同一把锁的真死锁；若不是，则 lsd 是 seeding 内部自锁，需要另找触发点。
