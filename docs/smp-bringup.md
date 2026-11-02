# SM-T970 副核诊断

默认 DTS 和 board 参数保持 CPU0；实验镜像从已校验的 CPU0 payload 派生，
只改变 CPU 拓扑、PSCI 节点和显式 SMP 参数。内存仍为已实测的512MiB拥有窗口。
`scripts/prepare-smp.py` 比较捕获的8个 affinity、验证实际 SGI 目标表达式，
并在 FAT 写入后独立核对内核、信任、种子、非 CPU ADT、固件和 BOOT 尾部。

## 已观察到的结果

BOOT3c72017f：请求2核，但可用1核，CPU1 step4、PSCI返回0、timer/SGI均0。
BOOT9d4dc888的23:28:06照片再次显示相同副核结果，且main1、106个进程。
只读交接检查得到 table=want=c38eb228、data1=c44ca800、id1=100、
handler=start=c320800c。它排除了这些交接数值不匹配，不能证明副核已经执行复位入口。
证据分别保存在 `evidence/cpu/smp-bringup/cpu2` 和 `reset-context`。
预备8核镜像尚未刷入；先让CPU1上线并验证每核计时器和IPI，再扩展。

## 入口分段

参考T733的入口记录方法，设备诊断补丁增加独立的每核128字节记录：

| 数值 | 最后写入位置 |
| --- | --- |
| 0 | 尚无可见记录；不能单独证明没有进入 |
| 1 | reset_vector入口，在OSLAR操作之前 |
| 2 | 已匹配CPU数据项 |
| 3 | start_cpu准备跳入common_start，尚未启用MMU |
| 4 | arm_init_cpu进入C初始化 |

前3处只使用原路径在此处不依赖的x4/x5/x6和条件码，保留x0及交接寄存器，
限定索引小于8；第一处按实测Affinity1编号，其余读取CPU_NUMBER_GS。
不修改异常向量、PSCI目标、GIC、调度器、原复位处理器和CPU驱动。
记录区在启动准备时flush，采样前再次flush；汇编存储带DSB。
这不是对实机缓存一致性的验证，缺少标记仍须考虑可见性或记录代码自身故障。
实际链接后指令用ARM64模拟执行检查范围、每核写地址和原路径活跃寄存器。
模拟的MPIDR和CPU数据不能充当真实副核运行证据。

诊断线程目标等待改为10秒，合法范围5至300秒；从线程等待开始计算，
不等于按下电源后的10秒，也不是持续屏幕刷新。
线程让出CPU，最终有意panic显示 `E reset/found/common/C` 的8个核心记录。
普通board默认不加入终止采样参数。采样较早时服务数量不可与旧120秒结果直接比较。

## 参考范围

同为SM8250的umi使用PSCI SMC64、Affinity1编号、清理复位代码/数据、标准SGI0，
公开记录8核在线且每核有计时器计数。T970当前ArmCpu已有这些机制，仍需实机资格验证。
T733是SM7325，定制驱动的redistributor IPI开关不能直接移植到当前组件。
固定来源与版本见 `evidence/cpu/smp-reference-review.json`。

## MMU切换分段

BOOT95accf53的23:44:40照片观察到CPU1入口3，确认已走到common_start之前。
10秒时main0、2个进程；这只是较早采样，不能据此判定用户态回退。
下一版复用同一每核记录，增加下列位置；数值4仍专指最终C入口，并非大小排序：

| 数值 | 最后写入位置 |
| --- | --- |
| 5 | common_start入口 |
| 6 | TCR恢复完成 |
| 7 | 初始TTBR、MAIR及TLB设置完成，准备切换kernel_pmap |
| 8 | 准备启用MMU |
| 9 | 写入SCTLR、完成ISB及NEON/线程寄存器设置 |
| 10 | 已跳入高地址arm_init_tramp |
| 4 | 最终到达arm_init_cpu |

新增标记首先检查x21，主核冷启动直接跳过，不访问副核数据；
保留x0/x1、LR和交接寄存器，仅使用x4/x5/x6及条件码。
不改变TCR/TTBR/MAIR/SCTLR数值或原有TLB/缓存操作。
若停在某标记，只能说明下一标记尚未可见；不能据此直接宣判某个寄存器操作失败。

## 高地址跳转观察

BOOTb44e4108的23:52:50照片显示CPU1最后标记9，仍main0/n2/cpu1。
高地址标记10未见，尚不能区分跳转失败和高地址标记本身的访问/可见性问题。
新增两个观察点：11在BR x0之前（保存7个寄存器值之后），12为高地址入口第一组指令。
12直接使用标记9留下的物理记录指针x6，不先建立新的高地址记录指针。
原有10随后仍使用ADRP获得高地址记录指针；最终C入口仍为4。

V行读取CPU1在跳转前保存的目标VA、返回VA、boot虚拟/物理基址、TTBR1、TTBR0、TCR，
同时读取采样线程所在主核的TTBR1作比较。比较时须区分页表地址和ASID等高位。
字段是诊断快照；尚未写入标记11时，不能把零值当作有效寄存器状态。
记录从偏移8开始，7个64位字段结束于偏移64，处于CPU1独立128字节区域内。
汇编捕获只使用原路径不依赖的x5和既有x6，不改变x0目标、LR或交接寄存器。
模拟验证使用真实链接指令及模拟系统寄存器，执行低地址和完整64位高地址的BR，
检查11/12、字段写入边界与原路径寄存器保留；不证明实机页表或缓存一致性。

即便某标记可见，后面的DSB、寄存器读取或下一次存储也仍可能未完成；
缺少后续标记不是特定指令故障的直接证据。

## 页表交接发布对照

BOOT36c2f602的00:01:31照片记录CPU1标记11：TTBR1=0，主核TTBR1=c4325000；
目标fffffff0074084cc、返回fffffff0073fcdbc，TTBR0=c2f79000、TCR=22a51a251a。
页表根为零能解释高地址路径无法继续，但尚未证明它为何为零。
T733的ArmCpu55cc0617实际在CPU_ON之前额外清理sysreg_restore和cpu_ttep；
初次对照遗漏了这两项，现已补充固定来源记录。

板级资格实验增加显式`t970-smp-publish-state=1`：仅在启动副核的cpu_start路径中，
对当前cpu_ttep与完整sysreg_restore执行XNU的flush_dcache（每项8字节），再调用原平台唤醒。
不填固定地址，不修改页表/寄存器值；默认不开启。T733用驱动中的PoC clean，
这里在内核有精确类型的位置清理相同对象，以本板实测后再决定共享组件的正式修复。

最终二进制检查发现，C文件没有定义XNU_NATIVE_ARCH_TIMER，而汇编有此定义。
首个发布实验构建因此被编译掉，未刷入；C入口标记4此前也被编译掉。
已将这两个C位置改为本配置有效的!CONFIG_SPTM条件，并要求链接后的cpu_start包含
原有2次加新增2次flush、8字节参数和bootarg检查，且均在平台唤醒前；
实际C入口用模拟CPU数据检查8个有效编号和2个越界编号。
此前“标记4未见”不能单独判断C入口；驱动phase、实际MMU/TTBR记录不受影响。
该对照若成功，也仍需继续验证每核计时器、IPI与持续稳定性。

## 两核上线与IPI检查

BOOT6fe3e519的00:13:58照片确认cpu2/sec1、CPU1 step7/fail0、C入口4；
CPU0/CPU1计时器计数22925/22334，CPU1 TTBR1=c4325000与主核一致。
在保留其它启动机制的情况下，加入两项发布后越过了此前TTBR1=0的启动阻塞。
这验证本板两核上线与计时器，不证明IPI、长期稳定或8核已完成。
当时两核SGI计数均0，main0/n2为10秒早期采样。

后续显式`t970-ipi-check=1`仅在诊断deadline后且CPU1 step7、在线数至少2时：
调用现有ArmCpu的armcpu_ipi_selftest向affinity100发送一次标准SGI0，
让出调度器等待100ms，再记录CPU1 SGI计数和现有armcpu_gic_diag的只读状态。
不启用SPI替代、不遍历发送SGI0..15、不读取/消费IAR、不修改GIC分组或屏蔽配置。
该额外100ms是调度目标等待，未标定实际时钟精度；总目标为原10秒加此短等待。

I行含attempt、普通发送总数sent、显式自测发送总数test、收到IPI总数recv、CPU1前后计数，
G的8项依次是IGROUPR0/ISENABLER0/ISPENDR0/IGRPMODR0/WAKER/GICD_CTLR/IPRIORITYR0/found。
attempt0未启用，2表示副核尚未就绪而跳过，1表示已调用发送并完成短等待及GIC读取。
只读GIC状态用于缩小范围；发送计数增加而接收不变尚不能直接证明EL2拦截。
主机替身验证36种开关/就绪/投递结果组合，真实投递仍需本板截图。

BOOT7e60f7c9第一次在UFS handoff NOP stage0拒绝，尚未提交该NOP命令；
原图不足以区分ready()/映射漂移等具体准入条件。机主重启相同镜像后通过根卷读取，
00:25:00照片再次确认cpu2/sec1、CPU1 step7、两核计时器与匹配TTBR1。
I行attempt1/sent2/test1/recv0/cpu1=0>0，GIC目标帧found1：
显式发送函数已执行，但未观察到SGI0处理计数。不能由此直接认定是EL2拦截或选定替代IRQ。
IPI投递仍是扩核前的阻塞；即便单次投递成功，发送线程未固定核心，仍需后续双向核间验证。
两次启动结果分别保存，未放宽UFS准入门槛。

## 实际汇编指令遗漏修复

继续对照T733时先建立了redistributor SGI0实验分支1eff4aa，主机76例通过，未刷入。
随后反汇编实际ArmCpu对象发现：旧标准发送路径的`dsb ishst; msr ...; isb`
只产生首条DSB，根本没有ICC_SGI1R_EL1写入。T733正常发送路径使用显式换行。
因此此前sent/test计数只能证明调用了C++发送函数，不能判断GIC或EL2是否丢弃了SGI。

独立ArmCpu工作树`.cache/armcpu-sgi-asm`提交b5f9775777aafe850a4ec8778b03154dfcabbd2b，
把17个多指令字符串的分号分隔改为显式换行，同时恢复计数器读取、DAIF更新与同步屏障。
默认组件9066、目录和设备feed未修改；这次每条构建/打包命令显式选择
`--local-module driver:ArmCpu=.cache/armcpu-sgi-asm`。
源码SHA、对象/归档SHA和可移植组件提交补丁见sgi-asm/component.json与armcpu-change.patch。
组件提交暂只在本机，尚未推送远端；旧源内核及未刷的redistributor实验均保留。

新的实际指令检查在旧71606266内核上按预期拒绝，在新对象、内核和payload上通过：
正常/诊断发送均有DSB→MSR ICC_SGI1R_EL1→ISB；并确认GIC/计时器同步、DAIF和计数器读取。
prepare-smp现在要求明确的已审阅组件提交、干净工作树及实际构建树源码路径匹配。
BOOT1c778e4b已刷入，两核、标准SGI0、10秒目标加100ms检查；实机投递仍待回报。

00:46:05照片确认BOOT1c778e4b收到真实SGI：CPU0/CPU1计数44/102，合计146，
I行sent146/test1/recv146，CPU1在检查期间99→102。它证明两核都有接收，
但因为同时存在内核发送且线程未固定，不能把增量严格归因于唯一一次诊断发送或独立双向测试。
10秒时仍main0/n2，用户态持续推进待后续检查。

机主明确要求跳过四核、直接验证八核。BOOTd95c45d9沿用相同a65817b8源内核和9dc8a62c
payload内核，只扩展ADT/PSCI CPU拓扑及cpus=8；非CPU ADT、固件、信任和Data种子逐项核对保持。
已仅刷BOOT，exit0正常结束并请求重启，八核实机结果待回报。
armcpu_smp_running为非原子的共享累加，sec不作为唯一验收依据；逐核stage/timer/sgi与
XNU processor_avail_count联合观察。当前仍使用标准SGI，未刷redistributor方案。

## 八核实机结果

BOOTd95c45d9的00:49:07照片：cpu8/sec7，CPU1–7均step7/PSCI0/fail0，
全部副核C入口4；CPU0–7 SGI计数54/62/59/26/6/24/2/1，合计234与recv234一致。
这确认8核启动及每核实际SGI接收。
计时器计数21084/23357/2086/5/0/0/2385/0；CPU4/5/7在此早期采样尚未观察到计时器中断，
不能记为8核计时器负载测试已通过。main0/n2，用户态持续推进与GUI仍未验证。
下一阶段需要逐核工作负载/计时器检查、持续多核运行和越过main前启动阶段。

## 用户态推进：20秒与缓存追踪

八核0dba26bc仅把终止采样从10改为20秒，沿用相同a65817b8/9dc8a62c内核；
与旧八核ADT仅/chosen/random-seed不同。00:58:19照片复现cpu8/sec7、所有副核step7/C4，
main0/n2，blocks371515；10秒照片为189168。跨次启动的块数增长提示仍在进行读取，
不能直接推断具体dyld阶段或以此证明没有任何等待。
CPU5已观察到timer2，CPU4/6/7此时timer0；快照不能替代逐核负载验证。

采样线程在Data/策略安装后、exec launchd前启动；目标时刻主动panic终止观察核心，
并非持续刷屏。因此10秒main0不能单独证明启动卡住。
下一版30秒加显式`t970-runtime-cache-trace=1`，使用已存在的PID1缓存调用追踪格式化器，
紧凑显示runtime/C行、最近最多12条已完成的相关调用及进程名。
默认详细CPU复位报告保留；不改变open/fcntl/共享区域映射的返回或授权行为，
不额外读取用户地址，不将追踪内容用于策略判定。
这是无锁的尽力诊断快照，记录可能正被更新；最后完成的一项也不等于正在执行或阻塞的一项。

30秒79a949b6照片：cpu8/sec7/main0/n2、blocks546747、init cache syscalls82，
最近的openat/fcntl均error0，最后完成的openat打开dyld_shared_cache_arm64.39。
fcntl命令97按当前XNU头文件是F_ADDFILESIGS_RETURN（登记文件内签名并返回结束偏移），
不把它单独当作整个共享缓存映射或用户态启动已完成。

主机原SystemOS目录有主缓存、52个编号分片及单独symbols文件；.40至.52共13项逻辑大小
989839360字节。目录清单不代表运行时剩余精确百分比，symbols不预设为启动必读。
下一版be219c43只将目标采样改为45秒，源/打包内核与30秒版完全一致，仍保留紧凑追踪。
