# MobileGestalt服务端与90秒诊断（2026-11-04）

v15实机链已到RemoteHID → MobileBluetooth → MobileGestalt bluetooth能力同步查询。
原版服务com.apple.mobilegestalt.xpc的Program为/usr/libexec/MobileGestaltHelper。
只读检查原版plist/CFString/调用指令，不修改Apple二进制或服务策略。

新增t970-ui-stack=3，仅匹配进程名MobileGestalt/mobilegestalt前缀（兼容proc_name截断），
保存前4线程寄存器，读取前2线程最多16级FP链。原UI模式1/2保留。
继续使用try-lock、解锁恢复IRQ后读VM、map引用与独立worker完成发布；报告最多20个100ms调度期限，
不保证硬实时，不取消阻塞worker。实时栈不是冻结快照；无匹配行仅表示此轮未采到，不证明服务从未启动。
ASan/UBSan实际helper覆盖前缀选择、前2线程栈读取和map引用释放；当前ABI编译通过。

用户要求减少等待：本版target90，较前版少30秒。历史60秒未见BB，所以先试90；
若目标服务未被采到，不能将较早的快照解释为后续永久缺席。采样等待本身可能另加调度延迟。
内核和归档旧版在ignored的pre-gestalt-stack-v1，原镜像全部保留。
命令/内核日志/对象与最终BOOT摘要见本目录JSON。平台总检查的旧review版本差异仍未解决。
硬件预期：stacks3、MobileGestalt进程行和M1/M2 FP地址；后续根据实际服务端栈决定最小修复。

最终BOOT SHA256：`91025540c43ffcecbacaf9f565912dbc9be0e07ad606e739e9de1b441e30277e`。目标90秒与mode3已独立核对，上传结果见upload.json。

## 实机01:09:00

target90/main1/n107/cpu8，BB57，MobileGestaltHelper95已有8线程，visited4/busy0。
M1 n9/e0，M2 n16/e0；显示open2/swap0。90秒已足以采到本轮目标。
M2在处理NSXPC导出对象调用时，经_MGServerCopyAnswerWithError进入MobileGestalt内部计算，
最终在dispatch_semaphore_wait_slow等待。大偏移邻近导出符号仅作映像定位，不认定精确内部函数名。
证明helper已启动且执行服务调用，排除本轮单纯helper未启动的解释；仍不能确定所等待的provider。
下一步审阅原版内部等待函数和完成回调，找实际设备服务或依赖，暂不伪造MobileGestalt返回。
