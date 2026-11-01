# 单次 UFS NOP 传输实验

`t970-ufs-nop=1` 延续已通过的实际内存归属预检，只发送一次 NOP OUT，
验证 NOP IN、task tag、长度及结果。不会调用普通 hostBringUp、Query、SCSI、
START STOP、分区读取或存储写入。它是诊断停止镜像，不能作为日常启动镜像。

## 前提与范围

严格核对已观测 SMMU ID、sCR0、87组表、唯一显示映射、CB0原配置和空队列。
使用实际 boot_args physBase/memSize 内、自有的连续缓冲；不借用固件描述符。
CB0仍为 CBAR=100ff、CBA2R=1、SCTLR=e0，不写 context，CB4／CB73不改。
CB0没有有效 NS stream 引用是候选条件，不是隐藏固件资源独占的证明。
候选 SID e0/4e0 来自目标无效字段及 SM8250 对照，实际 UFS 路由仍需命令结果证明。

先屏蔽 HCI 中断，停止空的 transfer/task 两类列表并有界等待。仅在无效槽55/56
写 S2CR=TRANS/CB0、读回，再设精确 SID 的 SMR VALID；不修改全局策略。
每步保护显示，提交前再核对完整表及 CB 状态。不改页表、不全局 TLB invalidate。
SMR/S2CR 的寄存器及先 S2CR 后 SMR 的顺序参考
[Linux v6.12 arm-smmu](https://github.com/torvalds/linux/blob/v6.12/drivers/iommu/arm/arm-smmu/arm-smmu.c)，
context 类型参考[寄存器定义](https://github.com/torvalds/linux/blob/v6.12/drivers/iommu/arm/arm-smmu/arm-smmu.h)。

替换 UTRLBA 为自有地址、读回，启动 transfer 列表。保留既有 IS/UIC/FSR 证据；
只由共享命令入口确认完成位。NOP沿用 RootCommands.h 及 TransferPoll.h，
超时200ms，不取消、不重试、不重新初始化 PHY、时钟或控制器。

## 结果解释

`stage=6 success=1 submitted=1` 表示一次合法 NOP 响应；还必须结合 `protected=1`、
GFSR、FSR前后及 controller状态判断。stage<5表示尚未尝试命令，stage5是尝试后未成功。
FSR=400是先前原始观测，比较前后变化，不把 GFSR=0当所有context无错误。

所有路径都以诊断停止结束；缓冲及已安装路由保留到重启，不回收、不自动恢复固件列表。
超时后控制器可能仍持有DMA内存，不能再使用该缓冲。下一次操作须重新进入固件／Download Mode。
`routesRetained=1` 表示不执行回滚策略，并不保证失败前已安装了全部路由，需看stage和原始值。
固定使用已测试 FD 515105d7…；根卷挂载仍未启用。

## 实机结果

BOOT `fb2be3f4…` 的机主照片确认 `stage=6 submitted=1 success=1 protected=1`，
`poisoned=0`，OCS=0、response=20000001、protocol=0、polls=2。
GFSR=0、CB0 FSR前后均400，显示映射仍为84020820/4。
一次NOP及其响应完成DMA往返；两候选SID同时安装，不能声称已分别验证两条stream。
数据传输、读盘、重复稳定性和根卷均未通过；下一步识别LUN并验证数据输入。
完整转录见 `evidence/storage/ufs-nop/device-result.json`。
