# UI启动对照（2026-11-03）

本轮重新通过GitHub连接读取固定提交的实际代码，范围不止README。
具体提交、文件与blob见`evidence/display/ui-call-v9/reference-sources.json`。

| 项目 | 源码中的处理 | 本板差异与下一步 |
| --- | --- | --- |
| umi，SM8250，同21H461 | `umi_memory_profile.py`先核对原厂DT、保留区、iomem和UEFI描述，再使用高地址窗口；owned请求为`0x130000000`（4.75GiB） | 本板仅512MiB请求，照片managed约438.8MiB。不能照抄umi的地址或增加DTS包络；先审阅本板EFI可分配范围与内存压力 |
| umi / T733 | 显示归档另外链接KeyStore状态组件；T733的`DisplayRegistration.cpp`调用`t733_keystore_start`，board显式启用`offline-key-events=1 sheng-aks=1` | 本板T970Display没有该注册调用，当前命令行也无这两个开关。这是具体接口缺项，尚不是backboardd未spawn的已证实原因；应单独审阅/接入目录中的`AppleKeyStoreState`，保持RAM Data限定 |
| umi / sheng | 启动前写入launchd overrides；源码记录通过隔离服务打断同步XPC等待。sheng另有显式lite列表 | 本板仅禁用watchdogd；需要取得本板等待链或受控单因素对照，再选择隔离项，不能将他板列表整批当作本板修复 |
| T733 | 显式禁用watchdogd、locationd、identityservicesd，保留原launchd及系统服务 | 提供了比全量lite更小的对照方案；本板尚无同一依赖环证据，不据此宣称修复 |

T733与umi的显示服务均有独立的状态服务接入；显示stage8不等于所有用户态依赖已齐备。
T733已报告锁屏/桌面；umi验证摘要仅确认Hello/Setup，未确认完成设置或主屏。

## 本板证据与实验顺序

本轮照片为target60、main1/n69、cpu8/sec7、SB27；BB0、显示client/swap/transfer/copy/retire/vsync均0。
SB匹配spawn返回1/e0，BB匹配spawn返回0/e-1，path-copy-errors0。
job-lookups bb0/e-1、sb0/e-1：照片中的数值是**0，不是1**。
它不能证明本轮有读取相应plist，launchd可能使用其签名缓存；原版缓存的backboardd项已在主机确认存在。

1. 保留当前60秒基线与用户照片；120秒版只改终止时间，先区分较晚启动与持续缺席。
2. 单独审阅AppleKeyStoreState接入，观测服务发布/客户端/selector。目录组件已存在，不重新实现协议。
3. 同时审阅本板EFI conventional memory证据，再决定更大owned请求。free0xb9仅为空闲页计数，不能单独判定OOM。
4. 若仍未spawn，按参考项目的方法取得服务等待链，再做最小服务隔离。

## 后续实机结果

- BOOTdb0121c9，target120：BB57、显示client enter/open/fail=2/2/0，swap/transfer/copy/retire均0。说明启动较晚，不能继续用PID1直接路径探针的BB0推断缺席。具体是否经过xpcproxy尚未采样证明。
- BOOTb9cc7afb，KeyStore接入，target60：stage4/meta0/ready1，open/refused/calls=1/0/1，selector0返回0；main1/n69，显示客户端仍0。
- BOOTf6fd6636，单独请求768MiB，target60：managed pages0x2b187（约689.5MiB），main1/n69，KeyStore与前轮相同，显示客户端仍0。扩容生效，但没有证据说明它消除了启动阻塞。
- BOOTec912b09，保留768MiB/KeyStore、移除定时终止和UI退出陷阱：机主报告持续仅有色条，未见新图形。不能将保留画面解读为具体函数阻塞。

当前重点转到已打开客户端后的等待位置。参考umi的`BootUiTraceProbe.c`，先在独立诊断worker内，
持task try-lock、短暂关闭IRQ并持thread sched try-lock时复制保存的寄存器，随后释放所有锁再格式化。
Mach-private结构必须在独立编译单元中使用；参考`BootProcessProbe.c`明确避免混用BSD与Mach私有头。
本板先不读用户VM或挂起线程，只取BB/SB队列前4个线程的PC/LR/x16/x1/x3。
这是运行中近似样本，不是完整栈、原子快照或已确定的等待链。
