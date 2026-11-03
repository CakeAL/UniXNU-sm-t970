# 工作队列请求与回调状态（2026-11-04）

v18一次采到三进程，但屏幕未显示SB尾部/结束标记。MG工作队列7总/0运行/6阻塞且limitflags0，
尚不能确定有无待派发任务。当前只观察等待，不将其解释为已证实的调度器故障。

新增板级只读kernel补丁t970-ui-batch-detail.patch，按官方prepared-source流程加入series，
在workqueue源文件内以workq_lock_try复制11个字段，解锁后由独立报告worker格式化。
W行：rc、req待处理内核请求数、f内部标志、idle、sched、con受限scheduled、creator线程tid、
age距wq_thread_call_last_run的原始absolute ticks、int timer interval ticks、made创建/ done满足请求累计计数。
f的delay scheduled/pended位为0x10/0x20，immediate scheduled/pended位为0x40/0x80，来自本轮源码。
rc非0时其余零值无意义；last-run0或无pending时大age不表示故障。计数仍是独立尽力快照。
不取消线程调用、不redrive队列、不改返回值或线程上限。

原mode5报告改紧凑head+F地址行，重复栈same=引用；保留pid/线程/slide/wq/状态/等待事件/优先级与PC/LR。
x16仍参与采样和去重，但紧凑head不再重复打印。每条F行最多16个地址，减少前缀导致的换行。
批量panic分支保留runtime与显示/KeyStore/目标栈，去掉无关进程名单和逐核长行；旧模式输出不变。
保留90秒、独立worker和最多40个100ms调度期限；VM读取不保证硬实时，也不取消阻塞worker。
wait事件不一定唯一标识等待对象，特别是原版semaphore的公共SEMAPHORE_EVENT，不能跨进程据此认定依赖。

ASan/UBSan实际helper覆盖新快照null/try-lock失败/解锁/11项与canary，
原批量采样及runtime紧凑分支替身测试通过，当前Mach-private编译通过。
旧kernel/archive在ignored pre-ui-workqueue-v1；补丁应用/内核链接/打包记录见JSON及日志。
平台总检查旧review版本差异仍未解决。所有新增字段需实机资格验证。
下一轮同时看MG/BB/SB的W行及末尾UI batch end，不凭run0或一次age直接修改调度器。

## 构建恢复记录

首次完整编译发现uthread没有uu_thread字段，改用当前源码已有uthread_tid接口；
真实pthread_workqueue.o的原编译配方重编译通过，未只依赖主机替身。
随后两轮prepare被urllib TLS EOF中断。缺失公开头文件由已固定manifest的git blob SHA1逐个核对，
使用原download URL或本地EXPORT_HDRS恢复，并缓存完整已核对的头文件。
恢复启动器仅在官方prepare-xnu-source调用前放回相同字节，之后照常执行原脚本、应用全部patch并写正常stamp，
未改变共享构建脚本或关闭哈希校验。临时失败删除的workqueue对象用其原JSON配方重建，解除archive符号扫描缺文件问题。
完整临时日志保留ignored的ui-workqueue-kernel-v1..v5.log；本目录存失败原因摘要与公开头文件恢复清单。

最终BOOT SHA256：`6ef0db8c95530bb967d5eb1d116c2f16aab87b2af3cccebafd116fe5fd68eabe`。真实内核链接/预链接及独立打包检查通过，prepared patch摘要匹配；上传结果见upload.json。
