# T733 内核方案对照（2026-11-02）

审阅固定到 [T733 3bb0d6f](https://github.com/RigoLigoRLC/unixnu-sm-t733/tree/3bb0d6f7840f088db6a0ec88ecb841e12042422f)。
这是同一 iPadOS 17.7.11 的 XNU 适配，不是换了几个不同版本的内核。
本板固定 XNU 为 xnu-10063.141.1，Darwin 23.6.0；T733 同名 OS profile 的
原始内核版本仍应以其解析结果为准，不从目录名称推断其源码提交。
它还使用自己的 UniXNU 基线 12729b7b1d52cf7056c30625786c08c9763345ac。
下列结论来自具体补丁内容和 board/defconfig，不把 README 的设备成果视为本板验证。

## 修改范围

五份清单中有32个设备自有补丁：设备 series 16、diagnostics 4、early-entry 7，
另有5个由 arch/OS 清单引用。这些补丁涉及34个 XNU 路径；数量不含共享 arch、SoC、
组件补丁。清单选入也不等于行为启用，例如 T733 的 CONFIG_XNU_BOOT_PROGRESS=n，
而早期标记和 USB 调试为 y。完整路径、摘要和来源链接在
[sources.json](../evidence/storage/t733-kernel-review/sources.json)。

| 问题与方案 | 内核修改位置 | 与 T970 的关系 |
| --- | --- | --- |
| SystemOS 只读 union 启动，区分启动时缓存路径与随后 Data 布局；修复 kernproc cwd 与 rootvnode 共用引用时重复释放 | bsd/kern/kern_exec.c；bsd/vfs/vfs_syscalls.c | T970 已恢复 union，并已采用 native-union-root-reference 修复；不能把真实设备的 cryptex 路径直接当成当前只读根的可挂载目录 |
| 内核入口、MMU、C 初始化、页表和异常的屏幕检查点；给早期 framebuffer 别名多预留页表映射空间 | osfmk/arm64/start.s、arm_vm_init.c、sleh.c；osfmk/arm/arm_init.c、pmap/pmap.c；pexpert/arm/pe_init.c | 定位方法可参考；T733 的 early_entry 实现和内存输入不能直接套用。本板已有可重复的 exec 前复位证据，不能仅凭粉条回退到 MMU 故障判断 |
| 防止无串口时 printf 经 PE_kputc 回落到 console_write_unbuffered 后重复进入输出；复制 panic 参数并保留异常 PC/LR/ESR/FAR | osfmk/kern/printf.c、debug.c；osfmk/arm64/sleh.c | 日志可观测性的候选；与驱动和输出通道一起审查，不能仅添加 printf 就声称已有实机日志 |
| USB 环形日志、exec 成功事件、退出原因、进程/线程快照、共享区域地址和异常栈 | bsd/kern/kern_exec.c、kern_exit.c、kern_proc.c；osfmk/kern/exception.c；osfmk/vm/vm_shared_region.c；console/serial_console.c 等 | 对当前 exec/用户态定位最有参考价值。需要其 native_usb_* 源码、NativeUsbDebug 组件及 T970 控制器/DMA适配；当前先用现有隔离探针，未导入整套USB代码 |
| 签名验证后修改的代码页被回收再载入时，清除 vnode 验证位并重新验签/应用修补，避免跳过修补 | osfmk/vm/vm_fault.c；bsd/kern/ubc_subr.c | 本板对应位置也缺少这项处理，是后续候选；尚无证据将当前停留色条归因于它，不与当前 exec 检查混改 |
| kalloc 类型分区超预算时输出详细数据；有界 try-lock 快照列出 zone 扩展者和页等待 | osfmk/kern/kalloc.c、zalloc.c | 属于内存诊断，不是放宽内存限制。T970 已消除约69.9MiB的重复策略表分配；实机实际回收量与后续可用内存仍需观测 |
| framebuffer 使用经板级确认的 Normal Non-Cacheable 属性；显示复制线程临时绑定性能核 | osfmk/console/video_console.c；osfmk/kern/sched_prim.c | T733 的DPU映射和CPU编号是板级事实，不能移植到当前CPU0 T970配置 |
| 将产品个性化 chip-id 与平台 UUID 输入分开；挂载 Data、插件、launchd job、亮度偏好；复制 staged_system_apps 并逐文件 fsync | iokit/Kernel/IOPlatformExpert.cpp；bsd/kern/kern_exec.c；bsd/miscfs/bindfs/* | 属于后续Data与系统服务阶段，不能用来证明本板已启动桌面；本轮不改Data、不引入额外写入 |

T733 还在 board.toml 使用有原字节检查的用户态 text_fixups，处理 AttentionAwareness
初始化等待、无 Apple 数据保护的偏好写入、FairPlay 请求超时、DC ZVA、CoreImage/CoreUI
软件渲染及颜色格式。这些不是32个 XNU 补丁的同义项，也不是当前应批量复制的修复清单。

## 当前剩余工作

不能把未知故障精确数成“还剩几个 bug”。目前实机已确认的待定位现象是正常版
BOOT12766f5f 停留色条；与它相关的 exec 返回、缓存映射和后续运行进展仍待确认。
BOOTc544bae1 的立即复位只证明到达 exec 调用前，不证明 exec 成功。
BOOT17bda459 的返回后探针已经上传，但本轮机主报告尚未获得可用的XNU观察，
随后回到 Download；不能据此说 exec 卡住或推翻之前的正检查点。

从这个点到可用系统仍有以下工作组；各组可能包含多个未知问题：

1. **exec / dyld / 内存：** 定位正常版停留，确认签名、缓存映射和首个用户进程运行；256MiB owned窗口继续保持。
2. **可写 Data 与 launchd 服务：** 当前未配置完整Data启动链；需要独立设计、验证持久布局、种子及其写入方案。
3. **基本交互：** XNU显示/软件呈现、触控及按键尚未完成；panic文本或固件菜单不等于桌面显示驱动。
4. **平台稳定性：** 正式日志通道、内存覆盖、IRQ/计时器和多核、存储长期稳定性与电源管理需分别验证。
5. **完整设备体验：** GPU、无线、音频、充电/电池、亮度及休眠等仍有板级实现和验证工作。

T733 README 的实机记录已包含桌面、8核、持久Data、触控、按键与软件显示，
同时列出 GPU 加速未接入，S Pen、无线、音频和系统休眠待后续实现。
因此它是可参考的成熟启动链，不是所有外设都已经解决的终态。

本轮镜像、校验及上传见 [policy-memory](../evidence/storage/policy-memory/README.md)。

## 映射之后的参考与本板进展

后续实机已依次显示共享映射kr=0、postmap close6/err0、真正main marker1/err0。
最新状态以handoff及policy-memory中的对应图像/回执为准，前文pending是较早快照。

这一阶段最直接的参考是SM8250 umi的分阶段观测：exec尝试/返回、用户SVC、异常、
critical exit各有独立记录，并读取原XNU的initproc_spawned字段区分“执行dyld”与
“launchd达到main”。本板采用这个状态语义，保留原sysctl/权限处理，观察原字段，未导入
其板级内存布局或驱动；现已实测main标记1。

T733的native-text-repage处理代码页被回收后重新加载时遗漏fixup的问题；本板对应代码
尚无该修复，应结合页重载及故障PC确认相关性。其libsystem_platform清零路径改走既有
paired-store循环来避免DCZVA故障，需核对同一21H461缓存UUID/原字节及本机异常证据。
AttentionAwareness启动等待、CoreImage/CoreUI与显示格式策略属于更后的框架/桌面阶段。

umi README报告Hello/Setup而非已验证完成桌面；T733的成熟软件显示路径也不代表GPU、
无线、音频和所有电源功能完成。两者对当前256MiB诊断窗口的内存策略都不能直接移植。
完整固定提交链接与结论在
[postmap-references.json](../evidence/storage/t733-kernel-review/postmap-references.json)。
