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

## 待观察

`GPU clk ... div=1 back=<...1216d7f...> restore=1` 表示门控可写且已恢复。
若 `div=0` 或 `restore=0`，说明该分支位被硬件/固件锁定，需要换路径；
若报告整屏不再出现，说明写后访问挂死，需要回滚到 v102。

之后才是 RSC/PDC 与 CX/MX 投票、GPUCC/GDSC 上电，再进入 GMU 启动。
