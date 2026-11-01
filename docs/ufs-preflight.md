# 零命令传输预检

`t970-ufs-preflight=1` 只读核对当前控制器、完整 stream 表及 CB0 状态，
通过后分配 XNU 自己的连续缓冲，核对其物理范围完全落入运行时 ARM64 boot_args
的 physBase/memSize。不得用 DTS DRAM 包络或 memSizeActual 代替加载器交接范围。

候选为残留字段对应的 e0/4e0、无效槽 55/56，以及无活动 NS stream 引用、
保持原配置不变的 CB0。它们只是下一轮实验的候选，预检不建立这些映射，也不证明
隐藏的固件资源归属。CB4 保留，未确认的 CB73 排除。

不写 MMIO、不修改 context、不中断固件队列、不提交 NOP/SCSI、不读写存储。
只有分配器拥有的内存会被分配；缓冲保留到诊断停止。没有借用固件请求列表。
现有 hostBringUp 不能直接使用：其默认 SID、context 重写、完整初始化及中断清除
行为必须经过 T970 专用入口审阅。下一轮命令测试须保留超时后的 DMA 缓冲并停止重试。

预期标题 `T970 UFS preflight`，检查 ownedOK、planOK、实际地址及 END。
即使均为1，也只确认可进入有界命令测试，仍未证明 DMA 或根卷可读。
