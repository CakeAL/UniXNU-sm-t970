# SMMU 只读核查

本轮从 `47b113f` 接手。已有 UFS 写入失败／复位记录，但未确认安全世界永久锁定 SMMU，
也未证明所有 SCM 路线不可用。用户确认接手时的未提交 SMR 写入实验还没有刷入；
原始修改已保存在本机忽略目录 `.cache/handoff-ufs-resume/`。

## 已发现的证据边界

- `0x15000000` 的 `+0x00` 是 sCR0；ID0/1/2 是 `+0x20/+0x24/+0x28`。
  原 `collectUfsSmmuStreams` 用 sCR0 低位推导组数，现改为 ID0.NUMSMRG，并处理 EXIDS。
- ID0 bit30 表示 S1TS，ID2 bit12 表示 4K 表格式支持；二者合起来不应命名为“AArch64 支持”。
- `ID1.NUMS2CB` 描述前部 stage-2-only banks，不能把 bank 1 固定当成首个可用 bank。
  接手的 bank 递增实验改为从该字段指定的边界起步，仍未通过实机 DMA 验证。
- SMR 写入读回零不单独证明 TZ 锁定、缺时钟或错误几何中的哪一种。
- 当前 `BoardInit.c` 先执行两个 SCM 调用，再画两个结果标记。仅凭第一个红标记，
  不能推出第二个调用没有返回。它没有做调用可用性查询，也没有分别归档传输状态与服务返回值。
  Linux 的 SCM 代码分别处理 x0 状态和 x1 服务结果，先协商约定并查询可用性；
  后续应按本机 SCM 协议核查，不能先猜设备 ID 再宣布接口不可用。

寄存器依据：[Linux v6.12 arm-smmu.h](https://github.com/torvalds/linux/blob/v6.12/drivers/iommu/arm/arm-smmu/arm-smmu.h)、
[几何解码](https://github.com/torvalds/linux/blob/v6.12/drivers/iommu/arm/arm-smmu/arm-smmu.c)。
SCM 依据：[约定／可用性查询](https://github.com/torvalds/linux/blob/v6.12/drivers/firmware/qcom/qcom_scm.c)、
[SMCCC 调用与结果](https://github.com/torvalds/linux/blob/v6.12/drivers/firmware/qcom/qcom_scm-smc.c)。
这些是实现参考，不能代替 T970 的运行时读数。

## 本轮镜像范围

`t970-smmu-report=1` 在 `NativeUfs::start` 最前面的平台匹配路径执行：

1. 映射原厂 DT `apps-smmu@15000000` 的 1 MiB 窗口。
2. 只读 sCR0、ID0/1/2、sGFSR；解码 4K／64K 页、CB 数量与偏移。
3. 有效且支持 stream matching 时最多读取 128 个 SMR；区分普通与 EXIDS 有效位。
4. 报告 `0x60/0xe0/0x4e0` 三个**候选** SID 的匹配数量和首条 SMR/S2CR。
   这些候选不是已确认的 T970 路由；不复用其他设备的 stream，也不写任何槽位。
5. 主动 panic 显示快照后停止，不调用 UFS 控制器、队列、NOP、根卷挂载或存储写入。

`native-ufs-root` 已从本轮启动参数移出。旧 `t970-ufs-writable-smr` 被拒绝，不再扫描改写活跃槽。
预期画面以 `T970 SMMUv2 RO` 开头；这是刻意的诊断停止，需保存完整原始数字再判断下一步。

## 固件与复现

复用已实机测试的 CPU0/initrd FD，SHA256 为
`515105d758a9d61078dffce5012db0754a71cec351a1bb34b30ee791196b5690`。
它不 dispatch UfsDxe，避免更晚的 PHY／SCM 原型在内核快照前改变状态。
当前工作树的 UFS 固件原型保留，不能把它当作本轮实际使用的 FD。

```sh
python3.14 scripts/extract-baseline-fd.py
python3.14 -m unittest discover -s tests -p test_t970_smmu_report.py -v
python3.14 scripts/build-smmu-report.py --output out/step7/probes/ufs-smmu-readonly
```

提取工具验证旧 BOOT 全文件哈希、Android v2 布局及 FD 哈希，只输出到忽略目录，
不覆盖不同内容的文件。主机构建后还需核对 payload 参数、内核／FD／DTB 哈希与 BOOT 容量。
打包工具使用本轮最终内核构建记录约束输入，独立从 FAT 提取内核和参数，再从 BOOT
提取 FD 核对；任一不符即拒绝。它不执行 USB 命令。
本轮不写 USERDATA。先前 USERDATA 根镜像写入已有独立回执；恢复 BOOT 不等于恢复旧 Android 数据。

## 本轮实机观察

机主确认 BOOT `7f729c2a…` 出现预期标题，并提供照片。原始转录和照片哈希见
`evidence/storage/readonly-smmu/screen.txt`、`device-result.json`。

```text
SCR0=002d0406 ID0=4c017e57 ID1=6000004a ID2=00005111 GFSR=00000000
SMS=1 EXID=0 S1=1 pageShift=12 CB=74 S2CB=0 CBoff=80000
groups=87 scanned=87
SID0060 n=0; SID00e0 n=0; SID04e0 n=0
```

已确认进入只读路径并读完所报告的 87 组匹配寄存器。`slot=4294967295` 是没有匹配时的
哨兵值；该行默认的零值并非完整 stream 表内容。sCR0.CLIENTPD=0、USFCFG=1 对应
客户端未禁用、未匹配 stream 采取 fault 策略；本轮没有触发 DMA，GFSR=0 不等于 DMA 正常。

这仍未确认 T970 的 UFS SID、SMR 写权限、PHY／队列状态或存储读取。
下一项测量结合[同类设备对照](ufs-reference-comparison.md)核对时钟和固件前提，
再采集完整 stream 表，避免把候选匹配缺失解释成永久安全锁。
