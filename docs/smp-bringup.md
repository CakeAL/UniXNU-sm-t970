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
