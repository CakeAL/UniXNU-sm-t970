# 工作队列准入与两次采样（2026-11-04）

接续v19照片01:42:52（BOOT6ef0db8c），三进程req分别4/6/4，idle2/1/2、creator0。
0x14是death+delayed scheduled，0x10只有delayed scheduled。原始ticks未自行假定频率。
BB的age大于interval，但一次快照不能区分回调延迟与正常重新排队；MG/SB则尚小于interval。
源码workq_schedule_creator允许在请求未通过admission时保留creator=NULL，因此不直接redrive。

新增t970-ui-stack=6：同一隔离worker按进程各采两次，间隔500ms调度期限，3进程最多6次快照。
不读用户VM、不锁task/线程、不暂停进程。原有mode1..5保留。
每次只用workq_lock_try读取队列，失败显示rc且零值无意义，解锁后才睡眠/换算/格式化。
reporter最多40个100ms调度期限；这不是严格墙钟上限，未完成buffer仍隐藏。

W0/W1显示待处理/标志/空闲/已调度/受限/creator、距最近thread_call的age_ms和interval_ms、累计made/done。
时长通过当前内核absolutetime_to_nanoseconds换算，不假定CNTFRQ。
Q0/Q1读取constrained/overcommit/special队列头(qos/flags/count)，受限请求的cached并发额度/active/busy，
全局受限线程上限、manager请求是否存在、cooperative最佳qos/已调度总数/限制开关。
C字段无请求时均0；有请求时cap/active/busy仅是准入输入，不声称完整复制准入结果。
cooperative总数和限制位也不是完整allowance结论。读取现有只读aggregate helper，不调用会重排队的selector/allowance。
不能把req数解读成dispatch block总数，不能把两次不变解读成永久死锁。

本次在既有BSD文件内扩充helper为28项；实际Mach-private采样编译、内核编译/预链接、
ASan/UBSan helper null/busy/unlock/queue fields/bounds及采样无用户读取/三次等待检查通过。
实际kern_exec批量mode5/6及旧报告分支测试通过，独立payload检查核对mode6/90秒、详细symbol和显示参数；
最终FAT往返验证只在已核对八核镜像上把owned请求由512改768MiB。默认DTS/内存未改。
首个kernel启动在安装新archive前被来源哈希检查拒绝；安装正确late archive后v2完整通过。
公开头恢复仍用v19的Git-blob核验缓存，官方prepare签名与本次patch一致。
平台总检查对旧review修订的拒绝仍未解决，不标为全平台通过。

BOOT SHA256见preparation.json；命令/内核日志/checks/host报告一并保存。实机结果待回报。
参考：[官方XNU补丁流程](https://unixnu.com/xnu/source-and-patches)、[适配记录](https://unixnu.com/porting/records)。
