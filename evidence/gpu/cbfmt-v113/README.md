# v113 CB0 AArch64 格式切换

在 [v112 实测布局](../smmu-v112/device-result.json)及相同的 CX、时钟、SMMU 总线前置
条件下，复用 [lmi 的 CB0 格式探针](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-probe.c#L107-L131)。
确认六个 SMR 均为零、CBAR/CBA2R 为零、SCTLR.M 清零、故障状态为零且 CB0 快照稳定，
再将 CBA2R.VA64 置一并恢复。该步只写 `GPU SMMU + 0x1800`。写入和恢复都使用
实际 W 寄存器。恢复后比对 S2CR0 和全部 15 个 CB0 快照字。

`GPU cbfmt ok/ok va64=0/1/0 ... bus=3/3 rsc=ff/ff xo=7 cxr=1` 表示格式位和
各级恢复均通过。若发现流、故障或恢复状态不确定，保留上游依赖到重启。
SCTLR.M 和流路由维持原态，下一阶段才引入自有页表和 SID5 attach/detach。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-cbfmt-v113-build
python3.14 evidence/gpu/power-v104/prepare.py --cb-format
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

2026-11-07 18:53（中国标准时间），Heimdall 成功上传 BOOT `cc2fb731…` 并请求重启。
机主截图确认 VA64 从 0 写到 1，随后触发 `busy-hold`。第三个 0 是恢复读数的默认值。
同屏八核在线，GOP 完成 32 次复制和退役。 [实测记录](device-result.json) · [上传回执](upload.json)
