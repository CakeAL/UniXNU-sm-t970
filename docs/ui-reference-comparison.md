# UI启动对照（2026-11-03）

## 2026-11-04：Apple logo、LaunchServices 与数据卷

- [Bergamota / Poco F1 的固定版本记录](https://github.com/ry-diffusion/Bergamota/blob/37a7a7a917fc09945ed2f7d1ae68b84d4525b4cb/NOTES.md)：iOS 16 曾在 Apple logo 停留约 15 分钟；SpringBoard 主线程的 Control Center → LaunchServices → unfair lock 栈与 T970 的 target300 照片高度相似。该项目继续采样 SpringBoard 和 lsd，并结合统一日志发现 lsd 建库时反复等待 MobileGestalt 的 Wi-Fi 地址查询；该设备加入独立构造的 ADT 地址后报告到达锁屏。这是 iOS 16 / Poco F1 的实机结论，不是 T970 的实机根因。
- T970 target125 与 target300 的 SpringBoard 上层栈相同，target300 的 PC/LR 位于 unfair-lock 等待；此时没有 lsd 栈和锁拥有者信息。两次是独立启动，不能单独证明永久死锁。
- 对当前 21H461 原始缓存及 `bb4d8474` 的实际打包 ADT 做只读检查：libMobileGestalt 映像中存在 `mac-address-wifi0`、`mac-address-bluetooth0`、`marconi-wifi` 和 `IONetworkController` 字符串；该 ADT 两种地址属性均缺席。缓存映像归属、UUID、ADT 哈希和限制见 `evidence/display/springboard-mode7-v27/reference-check.json`。字符串存在不证明对应代码在本次运行中被调用，也不确认属性格式或返回语义；不把另一设备的地址当作本板硬件值。
- [EVB10 固定记录](https://github.com/Ken-u/UniXNU-evb10/blob/e03f9880ae8fc420fa337366a444c8888b0e3fdc/porting.toml)报告 iPadOS 17 的 256 MiB Data 卷因 ENOSPC 使 SpringBoard 停滞，512 MiB 到达锁屏、最终配置 2 GiB。T970 使用 512 MiB **逻辑** RAM Data 种子，每次重启丢失修改；当前没有运行时 ENOSPC 或空闲空间测量，不能把此参考当作本板证据。它与 768 MiB EFI 内存请求是不同资源。
- [Sirius 设备记录](https://unixnu.com/devices/sirius-dddqmmx)报告 Setup 启动约 295 秒；较早采样可能只看到中间阶段。T970 新的 90 秒批量栈若尚未达到 LaunchServices，结果不能排除稍后出现该等待。

下一步针对 SpringBoard 与 lsd 各采最多四线程、每线程最多八层栈，目标90秒；若报告出现目标进程则检查 reseed、XPC 及锁拥有者线索，再判断是否值得设计只改 ADT 地址的受控对照。该方案不对真实 Wi-Fi 或蓝牙功能作声明，且照片空间或实时采样可能截断。持续 Data 的 UFS 写入仍未授权或实现。

实机 `aeb13ffc` 的 90 秒样本显示 lsd7线程、采前4，其中一条通过 XPC 进入等待数据库 seeding 的函数，另两条在安装记录恢复及 dispatch group 等待；SpringBoard 仍在等待 BackBoard 主屏幕信息、尚无 swap。采样没有覆盖 lsd5–7，不能认定数据库由 Wi-Fi 地址阻塞。照片和符号见 `evidence/display/springboard-mode7-v27/`。

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
