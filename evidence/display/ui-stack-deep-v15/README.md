# BB同步XPC调用方定位（2026-11-04）

v14照片确认BB第二线程在同步NSXPC回复等待，但8级FP链到_sendSelector:withProxy:arg1:arg2:
即用尽上限，尚未采到调用方。第三线程位于start_wqthread。首线程仍等待HID异步初始化完成。
不能仅凭这组实时保存寄存器/FP样本确定XPC服务身份或因果关系，也不照搬其他设备的禁用列表。

本版只将模式2的FP链上限由8扩到16；模式1仍8级，默认不读用户VM。
仍只选择BB队列第2至第4线程；task map引用、解锁恢复IRQ后读取、独立worker与报告超时规则不变。
不改变任何服务状态、XPC结果、触控接口或Apple指令。旧kernel/archive在ignored的pre-ui-stack-deep-v1。

ASan/UBSan实际helper验证16级截断、两模式线程选择、map引用释放以及原错误/超时边界。
Mach-private当前ABI编译与late archive导入解析通过。内核/打包命令与摘要见本目录JSON和kernel.log。
平台总检查仍受旧review revision不匹配阻挡，未放宽。

预计读取b2 FP行前16地址，匹配原版共享缓存UUID并用本轮slide符号化，找NSXPC之上的调用方。
FP链达到上限不表示完整；live线程状态/栈非冻结快照。VM读取超时不取消worker。
单报告固定1792字节，异常长输出会截断；运行中队列编号不保证跨采样稳定。

最终BOOT SHA256：`93bd51e8388c88000848e4818b4df380aefe9c8b8510580f3b87499382f7d6f8`。主机检查通过，上传结果见upload.json。
