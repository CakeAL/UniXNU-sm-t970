# v103：GPU 分支门控受控写测试

BOOT `6b1240530b8b702f1ea1083d1f2adb94f2a9ec59203422932a75946399e6ec80`。v102 确认 GPLL0 600 MHz 运行、GPU 分支 `0x1206d7f` 的
DIV_GATE（bit16）为 0；v103 在 `t970-gpu-w=1` 时做一次受控写：

1. 读原值，置 DIV_GATE，等 10 µs，回读确认 bit16 置位；
2. 恢复原 bit，等 10 µs，回读确认恢复；
3. 报告追加 `div=<0/1> back=<回读> restore=<0/1>`。

只写 GCC 0x52000 的 bit16，不改 PLL、时钟源、RPMh 或任何电源轨；写后立即
恢复。这是 lmi `lmi-gpu-clock.c` 里 GPUCC 200 MHz 序列的第一步，用来确认
这条 GPU 分支在本机能安全置位/恢复。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/gpu-clk-write-v103-build
python3.14 evidence/gpu/clk-write-v103/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/gpu-clk-write-v103/boot-partition.img
```

## 实测

机主截图中的 `branch=1206d7f div=1 back=1216d7f restore=1` 确认置位期间只差
bit16，恢复后该位与原值一致。同屏已到 launchd main、八核、247 个进程和
43 次 GOP 复制与退役。Data 可用 44,345 个 4096 字节块。结果绑定到
[截图与字段记录](device-result.json)及本轮 BOOT 上传回执。

下一步用 [v104](../power-v104/README.md) 读取继承的 CFG AHB 与 GPUCC 状态。
