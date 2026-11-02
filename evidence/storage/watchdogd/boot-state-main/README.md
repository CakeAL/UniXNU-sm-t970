# main、Data、临时启动策略状态验证

机主报告正常2387e904超过4分钟只见紫条，不能据此定位。保留正常源内核39d7cfe1与
正常panic副本7ad48eae，在核验空白entry padding中加入92字节的只读观察器，
仅替换sysctl_initproc_spawned原尾分支，先调用原sysctl_handle_int，再读取原main字段。
main非1时完整恢复原返回值、FP/LR/SP；1时Darwin变参栈上放置main、原错误、Data错误、
watchdog策略错误与阶段，然后有意panic。不会写这些状态，不定时复位。

BOOT28268af5，ADT/trustcache/Data seed/配置与正常2387e904逐字节保持；
header、固件、firmware DTB和零尾部保持。实际27组Unicorn状态/返回值组合及未知输入拒绝通过，
验证原参数、返回、FP/LR/SP、只写栈、不写状态和五个栈参数。

19:10:24原图明确显示main=1 e=0 D=0 W=0 S=4。
这证明准确的可写APFS Data挂载成功，root-owned策略及迁移标记的创建、写入、元数据、
fsync和close完成，并继续执行到真正launchd main。不证明launchd随后接受策略、
watchdogd确已跳过或其他服务/桌面正常。free计数不包含全部可回收内存。

随后正常2387e904 BOOT-only恢复，上传exit0且正常结束/请求重启，
见../policy-normal-resume。当前不再保留这个终止探针，后续服务观测待回报。
