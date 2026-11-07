# v102：GPU 父时钟与分支门控只读快照

BOOT `f99055795fa586f7d4ee6155503c7210b30c71aed4e5ff27acafb5dc0e3eec4c`。v101 已拿到 CX/MX 九档 corner 码；GMU 启动前还需要
GPUCC 的父时钟/门控资格，所以 v102 先只读 GCC：

- `GPLL0_MODE`、`GPLL0_L`、`GPLL0_ALPHA`、`GPLL0_USER`、`GPLL0_STATUS`、
  GPU 分支门控（`0x52000`）；
- 报告新增 `GPU clk gpl0=... branch=... run=... post=... hz=...`；
- 只读：不写 PLL、分支、RPMh 或电源；GCC 块在触摸/I2C 路径已安全访问。

偏移和 `hz = 19.2MHz*L + (19.2MHz*alpha >> 16)` 取自 lmi 的
`lmi-gpu-clock.c`（MIT）。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/gpu-clk-v102-build
python3.14 evidence/gpu/clk-v102/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/gpu-clk-v102/boot-partition.img
```

## 待观察

`GPU clk` 行的 `run`、`post`、`hz` 和 `branch`。这决定 GPUCC 200 MHz 的
父时钟是否已运行、GPU 分支门控是否关闭；之后才设计 GPUCC/GDSC 的受控
上电和 GMU 冷启动。
