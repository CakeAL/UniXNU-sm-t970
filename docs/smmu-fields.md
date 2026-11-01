# 合并核查 SMMU 字段与 context 状态

前轮 `ee45890a…` 已实机确认无效 SMR 的 ID 字段可写且恢复成功。
本轮 `t970-smmu-fields=1` 合并剩余字段检查，不提交 UFS 命令、不启用 DMA。
预期标题 `T970 SMMU fields (no UFS commands)`，末行 `END SMMU fields`。

## 执行范围

先复用已验证的单槽 ID 测试及全部拒绝条件；还要求 sCR0.CLIENTPD=0、USFCFG=1。
始终只操作槽 `56`，偏移 SMR=`958`、S2CR=`d58`，写入回调每次执行 DSB。

1. **VALID 核查**：S2CR 必须仍为原始 `000200ff`（FAULT），将 SMR 临时设为
   `800000a5` 并读回，再恢复 0。未匹配请求本已采取 fault 策略，临时规则也采取
   fault；不建立 translation/bypass DMA 路由。`a5` 是字段测试值，不是 UFS SID。
2. **S2CR 核查**：确认 SMR 已恢复为零且完整映射未变后，临时写 TRANS/CB0=`0`，
   读回，恢复 FAULT=`200ff`。所有 S2CR 写入都要求目标 SMR 保持无效。
3. **有界恢复**：若直接恢复 FAULT 未读回原值，仅在 SMR 仍为零时尝试 BYPASS=`100ff`，
   读回；必要时再做一次直接 FAULT 恢复。Linux 的 Qualcomm 实现记录了部分固件忽略
   FAULT 写入、将 BYPASS 写入转为 FAULT 的行为。本轮通过实际读回区分，不能预设 T970 存在该 quirk。
   最多八次写入（含 ID 测试）；没有循环重试或扫描改写活动槽。
4. **只读 context**：在完整恢复且 GFSR 仍为零之后，读取 CB0/1/2/3/4/73 的
   CBAR、CBA2R、SCTLR、FSR。按已测几何检查边界；不写 context，不清 FSR，不修改显示 CB4。

任何映射恢复检查或 GFSR 检查失败，停止后续步骤并显示结果。异常中断执行时不能
保证恢复已经完成；必须查看完整结束画面。未完全恢复的无效槽也不能继续用于传输。

## 画面解读

| 字段 | 含义 |
| --- | --- |
| stage=0 | 初始 fault-policy 前提不符，未运行 |
| stage=1 | 只进入 ID 检查；idStage 描述是否执行了该检查 |
| stage=2 | 已尝试 VALID 及恢复，没有进入后面的 S2CR 核查 |
| stage=3 | 已尝试 S2CR，未进入 context 读取 |
| stage=4 | 执行到 context 读取；仍需分别判断各 accepted、恢复和故障字段 |
| VALID/S2CR accepted | 仅表示对应字段是否精确读回测试值 |
| fallbackUsed | 是否尝试了 Qualcomm 特殊恢复方式，不单独证明该 quirk 成立 |
| allRestored / mappingsUnchanged | 目标两字及 sCR0、ID、所有已扫描 SMR/S2CR 是否恢复／保持一致 |
| contexts | 已完成读取的 context 数；原始零值不能单独证明 context 无主或可写 |

单个 accepted=1、stage=4 或 context 可读均不表示 DMA、SCSI 或根卷读取通过。
需检查 `END`、`allRestored=1`、`mappingsUnchanged=1`、`gfsrAfter=0` 后再安排传输适配。

寄存器和特殊恢复依据：
[SMMUv2 定义](https://github.com/torvalds/linux/blob/v6.12/drivers/iommu/arm/arm-smmu/arm-smmu.h)、
[qcom_smmu_write_s2cr](https://github.com/torvalds/linux/blob/v6.12/drivers/iommu/arm/arm-smmu/arm-smmu-qcom.c#L366)。

```sh
python3.14 scripts/build-smmu-report.py --mode fields \
  --kernel-build out/step7/smmu-fields-kernel.json \
  --output out/step7/probes/smmu-fields
```

仍复用固定 FD `515105d7…`；新的 BOOT 单独核验并归档，不再次写 USERDATA。

## 实机结果：cfbd84ba…

机主照片确认 stage=4，ID、VALID、S2CR 的 accepted 均为 1。
VALID 读回 `800000a5`，S2CR 读回 `0`；恢复后 SMR=0、S2CR=`200ff`。
`allRestored=1`、`mappingsUnchanged=1`、`gfsrAfter=0`，显示映射保持不变。
直接 FAULT 恢复成功，fallbackUsed=0；本轮没有验证或观察到 Qualcomm 特殊恢复 quirk。

| CB | CBAR | CBA2R | SCTLR | FSR |
| --- | --- | --- | --- | --- |
| 0～3 | `000100ff` | `00000001` | `000000e0` | `00000400` |
| 4（显示） | `0001f000` | `00000001` | `000000e0` | `00000400` |
| 73 | `00000000` | `00000000` | `3ab3a706` | `00000000` |

CB0～4 已有配置，SCTLR.M=0 只说明读出的翻译开关位未设置，不能单独证明 context 无主。
CB73 的读数不是已验证的干净 context，不能照搬其他设备“使用最后一个 bank”的选择。
CB0～4 的 FSR 没有本轮操作前基线，不能把 `400` 归因于本次测试；GFSR 为零也不代表所有 FSR 为零。
原始转录、照片可用性和镜像绑定见 `evidence/storage/smmu-fields/device-result.json`。

下一步核对独占 bypass context 与有界命令测试方案，保留显示 CB4，排除未确认的 CB73。
这些字段检查通过后仍需独立验证 DMA、命令完成和已知数据块读取。
