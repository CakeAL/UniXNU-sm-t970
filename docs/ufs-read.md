# LUN0 只读数据与 GPT 核验

`t970-ufs-read=1` 复用已通过的单次 NOP 队列／候选 stream 设置及实际内存检查，
仅在 NOP、保护状态、GFSR及CB0 FSR均符合前提时继续。

固定序列：LUN0 标准 INQUIRY（36字节）、READ CAPACITY(10)（8字节）、
READ(10) LBA1 一块、再次读取同一块并逐字节比较、读取GPT分区项（最多4块）。
所有数据流向均为设备到主机，没有存储写入、Query写、START STOP、复位或PHY改写。
LUN0 对应目标 Android 观测的 `0:0:0:0`，不是扫描其他设备猜得，见
`evidence/adb-2026-11-01/gpt.json`。

每命令最多1秒。一个已完成、健康传输上的UNIT ATTENTION允许全序列最多一次重试；
超时、协议错误、fatal、其他SCSI错误不重试。后续命令执行前再次检查保护映射、
SMMU状态与doorbell；poisoned后禁止写DMA。终止时仍保留缓冲与路由到重启。

GPT检查：签名／版本、92..4096字节头长、头CRC、当前／备用LBA及容量范围、
128字节分区项和最多128项、分区项区域不覆盖可用区、分区项CRC、所有已用分区边界，
唯一完整UTF-16 userdata名称及本机原始边界2969600..62458874。
这些边界来自此前采集；不访问userdata内部，不假定根镜像已经可挂载。

预期标题 `T970 UFS read-only LUN0`，stage1=INQUIRY、2=容量、3=GPT头、
4=重复头、5=分区项、6=全部通过。`stage` 是已进入的阶段，成功还须各结果标志为1，
healthy=1、poisoned=0，最终传输状态无错误。
重复两次GPT头仅验证本次相同数据，不证明长时间／大块／并发稳定性。

实现使用现有 RootCommands.h 的只读 SCSI 入口和 RootLayout.h 的生产 CRC；
主机状态机测试用 zlib 独立CRC构造数据，并注入超时、UNIT ATTENTION、
头损坏、重复不一致、分区项损坏、错误块长、越界表和错误userdata边界。
