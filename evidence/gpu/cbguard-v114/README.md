# v114 VA64 写后守卫诊断

[v113 实测](../cbfmt-v113/device-result.json)确认 CBA2R.VA64 写到 1，但写后空闲
检查触发 `busy-hold`。v114 采用 lmi 的显式 LDR/UXTW 读取 GPU SMMU，目标 W
寄存器与地址寄存器分离。置位后记录所有守卫，再决定是否恢复。

仅 CBAR 读数变化时，若布局有效、六个 SMR 全零、SCTLR.M 清零且无故障，
允许恢复原 VA64 值。恢复后仍须核对 CBAR、S2CR0 和全部 CB0 原值。发现流、
翻译、故障、无效读数或恢复差异时，保留依赖到重启。

- `GPU cbfmt` 的 `rb` 表示已执行恢复回读，`guard=写后/恢复后` 为十六进制位图。
  位 `1/2/4/8/10/20/40` 依次表示布局、全局故障、CB0 故障、CBAR 非零、EXID、
  SCTLR.M、SMR 非零。恢复位 `80` 表示 S2CR0 变化。`diff` 是 15 个 CB0 字的恢复差异。
- `CB guard` 给出写后守卫的 ID、故障、CBAR、SCR0、SCTLR 和非零 SMR 位图。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-cbguard-v114-build
python3.14 evidence/gpu/power-v104/prepare.py --cb-guard
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```
