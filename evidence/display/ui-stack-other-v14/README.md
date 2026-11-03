# BB其他线程调用栈诊断（2026-11-04）

v13的实机BB首线程等待IOHIDSessionOpen异步初始化任务完成；尚不能推断缺少触控驱动。
原版IOKit indirect symbol表确认0x190003e84为dispatch_async、0x190003e90为dispatch_semaphore_wait，
block入口0x1900045d8，完成通知在0x190004980。原二进制只读审阅，未修改Apple指令。

新增t970-ui-stack=2选择BB队列第2至第4线程读取最多8级FP链；不再重复首线程和SB栈。
模式1保留原首线程采样，默认仍不读用户VM。格式FP行新增队列索引，便于与保存寄存器对应。
沿用task map引用、解锁恢复IRQ后读取、隔离worker、20个100ms调度期限及完成发布规则。
工作线程VM读取可能持续阻塞，超时不会取消它；保存寄存器和FP链均不是冻结快照。
线程总数/队列顺序瞬时变化，不把队列序号当作稳定线程身份。

实际helper ASan/UBSan验证两个模式的线程选择、引用释放及原有错误/超时边界；
当前Mach-private ABI编译通过，late archive依赖解析通过。
环境、构建与打包沿用v13，旧内核/archive保存在ignored的pre-ui-stack-other-v1。
平台总检查仍拒绝当前框架与旧review revision差异，未绕过。

构建：先执行scripts/build-ui-wait-snapshot.py（输出ui-stack-other-object-v1），
再执行scripts/link-display-archive.py（输出display-archive-ui-stack-other-v1），
保存旧内核和归档后替换构建树内late archive，使用v13相同参数执行unixnu build kernel，
最后运行本目录build-image.py；JSON记录完整打包命令及摘要。

硬件预期：stacks2；显示b2/b3（及存在时b4）FP行的n/e/地址，
据调用链区分初始化任务的阻塞位置或尚未调度。主机检查不等于实机执行成功。

相似项目案例：umi@3eb7257的package/boot-progress/BootWatchdogPolicy.c明确记录
实机栈中identityservicesd/contextstored/locationd同步XPC等待环，以隔离job令Mach查询失败而非挂起。
这是服务等待的相似案例，未找到它与本板IOHIDSessionOpen相同栈/同因的证据，不照搬禁用列表。
来源：https://github.com/reAAAq/UniXNU-umi/blob/3eb72578597d2ca16471b172d45eddc096a34a04/package/boot-progress/BootWatchdogPolicy.c

最终BOOT SHA256：`dbb7921a359415ac646c7b70e109c1e9d19b3b10f0d462e813fadfd53f1301ae`。

BOOT上传成功exit0并请求重启；无设备读回摘要，BB其他线程栈与桌面结果待机主照片。
