# BB/SB保存寄存器采样

参考umi3eb7257的BootUiTraceProbe.c和BootProcessProbe.c，使用独立Mach-private编译单元，
task/thread try-lock期间复制队列前4线程的PC/LR/x16/x1/x3及缓存slide；
恢复IRQ并释放全部锁后格式化。无用户VM读取、线程挂起或Mach端口查询。
该版本没有线程调度状态或调用栈，保存寄存器可能是上次进入内核时的状态，不能单独证明当前阻塞。

实际helper的ASan/UBSan检查覆盖过滤、4线程上限、忙锁、IRQ恢复、空/非64位状态、
缓存slide与输出canary。Mach-private实际ABI编译、内核e3dbfe75链接/预链接和
独立payload/FD/DTB/种子/八核/768MiB请求检查均通过。
BOOTd80a3773上传成功；主机检查不是设备证明，后续照片单独记录。

机主target120照片：main1/n148/cpu8/sec7、BB57/SB27，显示client2/open2/fail0，
swap/transfer/copy/retire0；KeyStore open49/call194/selector7成功。
两个目标均采到3线程、busy0、slide10914000。

原版缓存与其symbols UUID匹配后，导出符号和局部符号共同定位：

- BB队列首线程PC为semaphore_wait_trap+8，LR为libdispatch的dispatch_sema4_wait armv81变体+24。
- BB第二线程/SB第一线程PC为mach_msg2_trap+8，LR为mach_msg2_internal+76。
- 其余采样PC为workq_kernreturn+8，LR为pthread_wqthread+360。

这些结果不足以确定上层等待对象，也不能据此断言缺少哪一个驱动。下一步采有限FP链及线程状态。
`symbols.json`来自`symbolicate-ui-registers.py`，使用Apple dyld a571176的已编译布局偏移，
兼顾数字后缀、dylddata与dyldlinkedit子缓存，不仅查局部符号。
原始Apple文件、生成镜像和身份输入均在ignored存储，不随证据提交。
