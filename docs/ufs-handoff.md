# SM8250 UFS 只读交接快照

这是 `7f729c2a…` 原始 SMMU 报告之后的一轮诊断，参数为 `t970-ufs-handoff=1`。
目标是一次拍到原始 stream 表、正确的 SM8250 时钟状态以及满足前提时的 HCI／队列状态。
它在 `NativeUfs::start` 的最前面执行，最后主动 panic 显示，不进入传输或根卷路径。

## 来源与修正

`GccUfs.h` 改为三星 SM8250 内核 `ad129ac…/drivers/clk/qcom/gcc-kona.c` 的
UFS 时钟偏移；T970 实测 DT 的控制器、GCC、时钟 ID 与 GDSC 引用已有板级记录。
可机读的源码符号／偏移见 `evidence/storage/handoff-readonly/clock-source.json`。
对照与上轮结论见 [参考核查](ufs-reference-comparison.md)。

移除原诊断中 SM8550 的独立 memory-PHY GDSC 映射。修正仅用于内核只读诊断；
没有修改 UEFI 的 PHY／SCM 原型，也没有更换厂商二进制或启动它们。
仍使用精确哈希 `515105d7…` 的已测 CPU0/initrd FD。

## 范围与解读

- 读取 SMMUv2 控制／ID／全局故障寄存器，以及最多 128 组 SMR/S2CR；
  包括无效槽的原始数值，不写 stream 或 context bank，也不读取 context-bank 寄存器。
- 读取 GCC UFS GDSCR 和九个时钟分支，不强制开时钟、不复位 PHY、不调用 SCM。
- 只有 GDSC PWR_ON=1、AXI/AHB enable=1 且两者 CLK_OFF=0，才映射并读取 HCI。
  对硬件门控但暂时 idle 的分支也保守跳过；跳过不等于 UFS 损坏。
- HCI 只读 CAP/VER/IS/HCS/HCE、UTRLBA/U、doorbell、run-stop 和 task-list 状态。
  不分配 DMA 描述符，不停止或启动队列，不清中断，不发 NOP／SCSI 命令。
- `HCstate=0` 表示前提不满足，1 表示已读，2 是 HCI 映射失败，3 是 GCC 映射失败。
  状态不为 1 时，HCI／QUE 行的零是未采样默认值。
- 表格格式为 `十六进制槽号:SMR/S2CR`，六列。以 `END slots=N` 确认表格结束；
  `valid` 是满足当前有效位规则的槽数。87 个槽位全部显示，不只显示三个候选 SID。

格式测试覆盖最大 128 槽：每行不超过 155 字符、报告不超过 31 行和 3600 字节。
这按已测 2800×1752 屏幕及当前 panic 字号计算；实机照片仍须确认完整末行。
本轮是顺序采样，寄存器之间不是原子快照。任何其他 panic 或缺失末行都单独记录。

## 构建与验证

源内核构建记录必须包含本轮所有驱动文件与配置的哈希。构建期间保持输入不变，
保留旧内核和旧镜像，然后执行：

```sh
python3.14 -m unittest discover -s tests -p test_t970_smmu_report.py -v
python3.14 scripts/build-smmu-report.py --mode handoff \
  --kernel-build out/step7/ufs-handoff-kernel.json \
  --output out/step7/probes/ufs-handoff-readonly
```

打包工具拒绝缺少关键头文件哈希的记录，并独立检查 FAT 内核／参数、BOOT 内 FD
和已测分区容量。它不会刷写。后续使用本机补丁版 Heimdall 仅刷 BOOT，并将回执与
机主观察绑定到成品哈希；本轮不再次写 USERDATA。
