# v118 CBAR Stage 1 残留时的依赖释放

[v117 实测](../cbbar-v117/device-result.json)确认 CBAR 写回零后仍读到 `0x1f300`，
VA64 回到零。v118 在相同的 CM3 复位和无流条件下复现该写入。仅当置位、
写回和 VA64 恢复后的 CBAR 都精确读到 `0x1f300` 时，才将其作为允许的残留值。
[lmi 的 A650 撤销实现](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-route.c)
也在撤销时保留 CBAR Stage 1。

探针在释放前做两次相隔 1 ms 的回读。CM3 保持复位，CB0 的 SCTLR、TTBR、
FSR 等其余快照字、六个 S2CR、SCR0 和 SMMU 标识保持原值，六个 SMR 与
全局故障为零。任何差异都保留上游依赖。写入范围限于 CBAR 和 CBA2R。
若实机复现 v117 的 CBAR 行为，成功时 `GPU cbar` 应读到
`latched/inert/ok bar=1f300/1f300 rb=1 va=1/0 f=8 diff=0 bus=3/3 rsc=ff/ff xo=7 cxr=1 n=2`。
此处 `f=8` 表示仍观测到 CBAR 非零，`n=2` 表示两次完整检查都通过。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --output out/data-bringup/gpu-cbrelease-v118-build
python3.14 evidence/gpu/power-v104/prepare.py --cb-release
python3.14 -m unittest discover -s tests
```
