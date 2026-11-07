# v107 GMU 寄存器只读探针

基于 [v106 的实测 XO 路径](../xo-v106/device-result.json)。只在 CX 应答、XO 源符合预期、
AHB/CXO/CX GMU 全部启用并重新读到运行状态时映射 GMU。T970 原厂 DT 的 GMU 窗口为
`0x03d6a000 + 0x30000`。GMU MMIO 映射为只读，CX 和时钟沿用 v106 的暂时投票与逆序恢复。

按 [lmi mode 4](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-probe.c#L395-L423)
读取 CM3_SYSRESET（`+0x14000`）。读到 reset=1 后读取 FW_INIT_RESULT（`+0x14070`），
再仅在 FW_INIT 为 0 时以 1 ms 间隔采两次 AO 计数器低位（`+0x14220`）。
报告 `GPU gmu read reset=1 fw=0 ao=…/… xo=7/7 cx=1/1` 可核对 GMU 可访问、
计数是否推进，以及三条时钟和 CX 是否恢复。时钟前置失败时仍报告 `GPU xo` 或 `GPU cx`。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-gmu-v107-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-read
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

2026-11-07 15:52（中国标准时间），Heimdall 成功上传 BOOT `5354324f…` 并请求重启。
详见 [打包记录](preparation.json)、[主机验证](host-validation.json)和 [上传回执](upload.json)。
启动后三指按住两秒，采集 `GPU gmu` 一行。
