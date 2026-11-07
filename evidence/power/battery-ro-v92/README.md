# T970 电池总线与实际托管窗口观察 v92

继承 v91 的 3840 MiB 请求和按键 HID，增加 `t970-battery-ro=1 t970-memory-report=1`。
只读，不发送 I²C 请求，不改变时钟、引脚、充电器或内存分配。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/battery-ro-v92-build
python3.14 evidence/power/battery-ro-v92/prepare.py
```

BOOT `43258b3cf1c594b3221ccf03493e1ea42abf73b26b39f07b4c50d95852046085`。
编译、链接、prelink 和原始 HID ABI 核对通过；61 项测试通过（10 项跳过）。
配置的命令行长度在 Loader 的 1000 字节上限内。

三指报告新增两行：

- `Battery RO`：GCC 的 SE0／wrapper AHB 分支和投票、NORTH GPIO28／29 的复用与电平。
  只有投票齐全且三条分支都未报告 `CLK_OFF` 时，才读取 SE0 的固件协议／状态。
  `SE=gated` 时 `fw/st=0` 是未采样占位，不是硬件读数。
- `Memory owned`：读取 arm64 的 64 位 boot_args，报告真实 `physBase`、`memSize`、
  `memSizeActual` 和 `topOfKernelData`。`actual` 仍是 Loader 的拥有窗口大小，
  不是安装的整机 DRAM；此探针不提供完整 EFI 内存图，也不扩大 XNU 托管范围。

已刷入并保留 HID；传输回执见 `upload.json`。本版不读取 gauge 或 charger。

## 实机结果

vote=041007c0，clk=4220/0/80000002，gpio28/29=7/7，io=1/1，SE=gated。SE0和主AHB运行，从AHB有HWCG且报告关闭；引擎未读取。共享display_state只有896字节，Battery行末尾和整条Memory行被截掉，不代表Memory读取失败。v93优先输出外设行，并只临时清除从AHB的HWCG位，采样后恢复。
