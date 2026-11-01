# 单个无效 SMR 的 ID 字段测试

上一轮 BOOT `933a5d77…` 完整显示 87 个槽，确认控制器可读、doorbell=0，且唯一有效
映射属于显示控制器。当前问题先缩到 SMR 字段是否接受写入，不启动 DMA 或重建 UFS。

本轮参数 `t970-smr-id-test=1`，预期标题 `T970 SMR ID test (VALID stays zero)`。
它是带两个临时寄存器写入的诊断，**不是只读快照**，也不建立活动映射。

## 前提与范围

1. 精确核对已测 ID0/1/2、87 组、非 EXIDS 模式、几何与初始 GFSR=0。
2. 供电／时钟门槛通过，HCE/ready 位成立，transfer/task doorbell 都为零。
3. 唯一有效映射仍为显示槽 04：SMR=`84020820`、S2CR=`4`。
4. 槽 `56`（十六进制，十进制 86）仍为无效 SMR=0、S2CR=`000200ff`。
5. 写入前重新读取完整匹配状态，发现任何变化即拒绝；再核对目标槽和故障值。
6. 只写 `SMR[56]`（偏移 `0x958`）为 `000000a5`，执行 DSB，读回。
   随即恢复原值 0，执行 DSB，核对恢复值、S2CR 和全部匹配状态。

两个写入值均保持 VALID=0、mask=0。没有 S2CR、context bank、全局控制、GCC、PHY、
SCM、队列或存储写入。出现意外读回也尝试恢复同一槽；不能据此保证发生异常后的恢复已完成，
必须以完整结束画面中的恢复／保护检查为依据。

与三星内核的字段探测方式对照：
[arm_smmu_test_smr_masks](https://github.com/LineageOS/android_kernel_samsung_sm8250/blob/ad129ac77e9d871770d61f7bd219a836d7f35b74/drivers/iommu/arm-smmu.c#L2957)。
本轮只测 ID 字段，并额外恢复原字；不照搬通用驱动对全局或 context 的初始化。

## 画面解读

| stage | 含义 |
| --- | --- |
| 1 | ID／几何／故障前提不符，未写 |
| 2 | 控制器或时钟前提不符，未写 |
| 3 | 显示／目标槽前提不符，未写 |
| 4 | 写入前发现状态变化，未写 |
| 5 | 已执行测试及恢复尝试，继续检查下列字段 |

stage=5 时，`observed=000000a5` 且 `idAccepted=1` 才表示该 ID 字段接受本次写入。
`restored=0`、`restoreOK=1`、`mappingsUnchanged=1` 是恢复与保护条件；比较覆盖 sCR0、
ID 和全部 SMR/S2CR，GFSR 前后值单列。任一失败均不继续 DMA，也不尝试修补其他槽。
stage<5 的默认零值不是测试成功。意外异常／复位需单独记录，不能解释成写入被忽略。

即使 ID 写入成功，也没有证明 VALID、S2CR 或 context 可写；即使失败，也没有证明
TZ 永久锁定。上游确有部分 Qualcomm 固件的 S2CR 写回特殊行为，但本轮不测试它，
不将其他平台的 quirk 当成 T970 根因。

```sh
python3.14 scripts/build-smmu-report.py --mode smr-id \
  --kernel-build out/step7/smr-id-kernel.json \
  --output out/step7/probes/smr-id-test
```

保留已测 `515105d7…` FD，只准备新的 BOOT；传输及机主观察与成品哈希一起归档。
