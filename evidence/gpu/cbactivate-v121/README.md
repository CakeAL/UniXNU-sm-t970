# v121 无流的 CB0 启停与 TLB 同步

[v120 实测](../cbroot-v120/device-result.json)确认真实页表可安装和撤销。
v121 复用相同的 42 个叶页。在上下文配置和走查都通过后，用固定版本
ArmSmmu4K 的 `ArmSmmu4KSyncContextTlb` 发出本地 TLBIASID 和 TLBSYNC，
以最多 1000 次回读等待 TLBSTATUS。随后确认上下文、六个流槽和 CM3 状态，
短暂置位 SCTLR.M，保持上下文故障中断关闭并回读故障状态。

撤销时先清除 SCTLR.M 并回读，然后执行第二次 TLB 同步，最后恢复 SCTLR、
TCR2/TCR、MAIR 和 TTBR。完成 v118 的两次整组回读后才释放页表与上游依赖。
同步超时、故障、路由变化或撤销不确定时保留依赖和页表。本轮保持 CM3 复位，
六个流槽为空，验证范围为本地启停和状态回读。

成功时 `GPU ctx` 应显示 `ok/ok/ok tlb=3/…`、`cfg/rb=3f/3f held=0`、
`bus=3/3 rsc=ff/ff xo=7 cxr=1 n=2`，其中 `ctl` 第一项的 M 位为 1，第二项为 0。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --output out/data-bringup/gpu-cbactivate-v121-build
python3.14 evidence/gpu/power-v104/prepare.py --cb-activate
python3.14 -m unittest discover -s tests
```
