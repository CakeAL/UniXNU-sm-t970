# SM8250 GPU 资源探针 v99

BOOT `76dd4b3261348ea43aee1302760ac4178d5f84491e887331451aa2339b404174`。基于 v98，只把只读的 SM8250 GPU 电源档资源接到三指报告：

- 新增 `GPU arc db= cx= lv= min= mx= lv= min=` 一行；
- 解析 ARC cmd-db（`0x80860000 + 0x20000`，触摸/RSC 路径已映射过该块）里的
  `cx.lvl`/`mx.lvl` 资源，输出 DB 版本、资源地址、电压档数和最低 SVS 档索引；
- 不请求 RPMh、不写寄存器、不碰 GPU/GMU 窗口。

解析器移植自 [lmi-uefi-touch-gpu](https://github.com/Fsasdddd/lmi-uefi-touch-gpu)
的 `lmi-gpu-resources.c`（MIT），只保留只读解析和报告；端口方案见
[GPU 移植方案](../../../docs/gpu-port-plan.md)。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/gpu-arc-v99-build
python3.14 evidence/gpu/arc-v99/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/gpu-arc-v99/boot-partition.img
```

## 边界

这一步只证明 ARC 资源表可读、CX/MX 档位地址和最低 SVS 档满足约束；不证明
GPU 已上电、GPUCC/GDSC 可用或 GMU 能启动。GPU/GMU 窗口的读取仍要先做
时钟/电源资格，否则有挂死风险。

## 待观察

三指报告的 `GPU arc` 行。若显示 `refused`，请把整行发来（含 cx/mx 的
valid/地址），据此判断 cmd-db 布局差异；若正常，下一步对照 DT 的 OPP 和
电源域，再做 GPUCC/GDSC 只读资格确认。
