# UI有限FP链诊断（2026-11-04）

接续ui-wait-v12的BOOTd80a3773照片：main1/n148，BB57/SB27，open2/swap0。
本次所附照片字段与既有记录一致，不视作新镜像运行结果。

保留已有工作区的栈采样改动并完成集成：默认仍只读保存寄存器；
显式t970-ui-stack=1才启动独立内核worker，引用目标task map，释放task/调度锁并恢复IRQ后，
读取队列首线程最多8级FP链。每次16字节，校验用户地址、16字节对齐、单调前进与1MiB步长。
报告方最多20个100ms调度期限，未完成仅报告phase/pid，不读取部分缓冲。
调度期限不是硬实时墙钟上限；卡住的VM读取不会因此取消，worker/map引用可能保留到诊断终止。
线程仍在运行，FP链不是一致冻结快照，st字段仅为瞬时调度位，不能单独推出等待对象。

实际helper ASan/UBSan检查通过，覆盖锁/IRQ恢复、空状态、截断、有效FP链、
读取失败、非法FP、循环链、worker启动失败和超时隐藏部分输出。
当前Mach-private ABI编译通过，late archive依赖检查通过。
平台总检查仍因框架HEAD不同于旧审阅revision拒绝，未放宽检查。

构建命令：

```sh
python3.14 -m unittest discover -s tests -p test_ui_wait_state.py
python3.14 scripts/build-ui-wait-snapshot.py --tree out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree --output out/data-bringup/ui-stack-object-v2
python3.14 ../UniXNU/unixnu build kernel -D . --out out/data-bringup --local-module driver:ArmCpu=$PWD/.cache/armcpu-sgi-asm
python3.14 evidence/display/ui-stack-v13/build-image.py
```

环境PATH同脚本：.cache/bin、Homebrew LLVM/lld。旧kernel/archive保存在ignored的
out/data-bringup/pre-ui-stack-v1，旧BOOT及照片保留。最终准备摘要与校验见本目录JSON。
未刷写设备；本轮主机检查不能证明栈读取成功或桌面呈现。
下一轮读取S/b FP行的n/e与返回地址，匹配共享缓存UUID后符号化；若worker busy，先按phase定位。

最终BOOT SHA256：`a708fadf1c93f6681cb654959ca48f45ee9280b4373547529ca1540dd07d9ee9`。内核链接/预链接和独立FAT往返检查通过。

## 实机结果与后续定位

BOOTa708fadf上传exit0；机主00:46:53照片确认stacks1、main1/n147/cpu8/sec7，
BB57/SB27均采到8级且e0。显示open2/fail0、swap/transfer/copy/retire0，尚无桌面。
照片按上传顺序和独有stacks1字段关联，无设备摘要读回。
共享缓存slide0xf55c000，symbols UUID匹配。BB链为dispatch_semaphore_wait_slow →
IOHIDSessionOpen → IOHIDEventSystemOpen → BKHIDSystem startHIDSystem；
SB链为mach_msg → BKSDisplayGetMainScreenInfo → BKSDisplayServicesStart →
BKSSystemShellService初始化 → FBSystemShell初始化。主程序4个地址未用缓存slide符号化。
原版IOKit反汇编和indirect symbol表核对：IOHIDSessionOpen在0x190003e84调用dispatch_async，
0x190003e90调用dispatch_semaphore_wait（参数-1），其block入口0x1900045d8，
完成处0x190004980信号量通知。说明等待异步初始化完成，不能单凭此判定触控驱动缺席。
下一轮检查BB其余线程的FP链，区分队列初始化任务阻塞与未派发。
