# 一次采集三进程与工作队列（2026-11-04）

用户要求减少逐页刷机，新增mode5：一次遍历BB/SB/MobileGestaltHelper，每进程最多8线程、
每线程最多16级FP链。报告缓存8KiB，每次内核栈仅存一个进程的8行。
保留原模式1-4的线程选择/采样深度。

同一轮同时记录：
- 进程pid、total/visited/busy、共享缓存slide；
- 线程tid、状态、PC/LR/x16、等待事件和调度/基础优先级；
- 每线程有限FP链与读栈错误；同进程相同PC/LR/x16及完整采样链用stack=same引用，保留独立状态/等待事件；
- 原版fill_procworkqueue的返回值、总线程/运行/阻塞数量与限制标志；该API使用try-lock；
- 原有显示client/swap/transfer/copies/retire/vsync及KeyStore状态继续保留。

wq=rc:total/run/blocked/flags；非零rc下零值不代表真的空队列。
proc_workqueueinfo的4个uint32字段与本轮XNU bsd/sys/proc_info.h布局逐项核对，size断言16，
独立Mach-private编译单元避免混用BSD私有头。线程字段在sched try-lock下复制。
去重只表示所采寄存器/有限返回地址相同，不说明等待对象相同；事件和tid仍逐行输出。
末尾UI batch end processes=N clipped=0表示文本未截断；N不是全部目标均出现的保证，应逐个检查标题。

target90，报告方mode5最多40个100ms调度期限，其他模式仍20；等待不是硬实时上限，
VM读取超时不取消worker，完成前隐藏全部部分数据。单次总量最多24线程/384个16字节FP读取，
每个进程采样时间不同，live寄存器/栈不是原子冻结快照。屏幕自动换行仍可能挤掉早期行，需实机核对。

实际helper ASan/UBSan覆盖三进程合并选择、8线程上限、去重、workqueue成功/错误、引用释放及原错误边界；
当前Mach-private ABI编译通过。源内核/archive旧版保存在ignored pre-ui-batch-v1。
主机检查和镜像摘要见JSON；旧review框架版本差异仍使平台总检查拒绝，未放宽。
不修改MobileGestalt/蓝牙/诊断数据返回值，不将未知provider或回调当作已实现。

最终BOOT SHA256：`10dbedd8b39204d25780458e49d922370d75fdcf7a7fe66be8594398e7a8c84d`。mode5/90秒已独立核对；上传结果见upload.json。
