# MobileGestalt后台工作线程（2026-11-04）

v16服务端共8线程，先前仅visited4，因此尚未采到后半工作线程。
新增mode4仅匹配MobileGestaltHelper，遍历最多8个线程，跳过队列前4个，
对第5-8个复制寄存器及最多16级FP链；最多4行存储，原模式1-3不变。
仅诊断，不改服务匹配、MobileGestalt结果或Apple指令；报告target90。

原版只读审阅明确：
- MobileGestalt 0x1a0230b54创建信号量，提交全局队列block0x1a0230c00后无限等信号。
- block使用MobileGestaltRunLoopMode运行RunLoop；正常路径会调用完成block并signal。
- 0x1a0231cac的回退路径查询syscfg-v2-data/AppleDiagnosticDataSysCfg，
  并匹配AppleDiagnosticDataAccessReadOnly；调用方传5秒给RunLoop辅助路径。
- 原版内核元数据中该kext仅匹配AppleARMNORFlashDevice/diagnostic-data,format1或AppleNANDConfigAccess，
  T970尚未实现对应板级配置载体。缺少匹配本身不证明永久阻塞，需区分正常超时/回调未执行/其他查询。

v16照片首个MG返回地址经重新核对为1b5d94be0（不是初次转录1b5d940e0）；
减slide后1a0230be0恰为semaphore_wait之后。初次解析精确地址已更正单独保存，旧文件保留历史说明。
CFString和原kext元数据均来自固定21H461原始文件，不伪造诊断数据或硬件能力。

ASan/UBSan实际helper覆盖mode4页选择、访问上限8、存储上限4和map引用释放；当前ABI编译通过。
沿用独立worker/try-lock/解锁恢复IRQ后读VM，报告最多20个100ms调度期限；阻塞worker不被取消。
队列顺序不是稳定线程身份，live栈不保证一致，1792字节报告可能截断。
旧kernel/archive保存于ignored pre-gestalt-workers-v1。主机检查不能证明硬件执行或桌面成功。
平台总检查旧review版本不匹配仍未解决。

下一轮看M5-M8的FP链，定位实际查询/RunLoop工作线程后再选最小修复。

最终BOOT SHA256：`6da8d322641f359a4147f729b3f1a087f2244908654b18289ed1e7b593ffa748`。报告mode4/90秒独立核对通过，上传结果见upload.json。

## 实机01:17:48

target90/main1/n109，helper94线程8/visited8/busy0；M5/M6/M7均16级e0且FP链相同，
M8 start_wqthread。显示open2/swap0。新链首个MG返回1a0232370紧随以全局1ede8a370为参数的锁调用。
实际owner和异步callback是否调度尚未确认；不能把这组锁等待直接当作配置数据缺失的证明。
按用户要求下轮一次采三进程前8线程、workqueue及等待事件，合并重复栈，减少逐页刷写。
