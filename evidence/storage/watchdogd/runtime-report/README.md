# 有界服务采样（BOOTeeeba83b，实机结果待回报）

主机已确认main1/Data0/policy0/stage4，但没有持续控制台或图形输出。
新增设备补丁t970-runtime-report.patch，仅在显式t970-runtime-report=30..300时启动一次
诊断内核线程。普通board参数不启用；本次配置120。没有CPU忙等或自动复位。
线程在Data/策略安装后创建，使用clock_interval_to_deadline/assert_wait_deadline/thread_block
休眠让出CPU，随后通过proc_iterate(PROC_ALLPROCLIST|PROC_NOWAITTRANS)采样非僵尸进程。
原proc_iterate实现管理进程引用，callback返回PROC_RETURNED或PROC_RETURNED_DONE，不占用引用。

输出有意panic：runtime target=120 main=... n=... wd=... sb=... bb=... rb=... D=... W=... S=... blocks=...
其中wd/sb/bb/rb是watchdogd/SpringBoard/backboardd/runningboardd的PID，0为本次没有观察到。
callback最多512个，n=512可能被截断；展示前18个名称/PID、固定512字节缓冲。
这是尽力而为的非原子快照：进程可能并发退出/exec，存在不代表工作正常，缺失不代表从未运行。
main通过只读accessor读取原initproc_spawned，不改原PID1-only sysctl setter或退出结果。
Data/策略状态和UFS累计verified-block计数只读，原OS与系统服务不改。

目标等待从诊断线程进入时开始，不是电源键或loader启动时；调度或前序I/O可增加整机等待时间。
实际设备计时/线程唤醒和采样尚未验证，没有报告不能单独解释成用户态卡死。
此版与普通BOOT2387e904、main检查28268af5分开保存，先前源内核39d7cfe1保持。

源内核ab84b0ca、打包内核239c66ab、完整BOOTeeeba83b。
实际helper的ASan/UBSan检查覆盖进程/PID匹配、512回调上限、固定缓冲、调度等待分支、
显式参数/上下界/单次创建守卫和线程创建失败；这些是OS API替身，不是实机证明。
现有watchdog策略helper15个API失败点回归检查通过，提取器现按函数边界排除后续新helper。
独立包装核验真实PMGR、RamBlock和采样符号、全部FAT/ADT/种子/trustcache/FD/DTB/header/零尾部，
要求实际bootarg120，未声明采样参数的检查负例已拒绝。

仅上传BOOT，exit0正常结束/请求重启，未做分区读回。结果以随后device-result为准。
