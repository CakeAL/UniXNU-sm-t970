# v104 GPU 电源交接快照

以 [v103 实测镜像](../clk-write-v103/device-result.json) 为基线。内核使用锁定的
Sm8250Platform `A650GmuPower.h` 定义。FAT 中替换内核，并把 XNU 参数
`t970-gpu-w=1` 换成 `t970-gpu-p=1`。

`GPU pwr cfg/mem/dvm/axi=…` 依次报告 GCC 的 CFG AHB、MEMNOC GFX、SNOC DVM GFX
和 DDRSS GPU AXI。CFG AHB 的 bit0 为 1 且 bit31 为 0 时才读取 GPUCC。
报告的 `cx/hw/gx/ahb/gmu/smmu` 依次为 CX GDSCR、CX 硬件状态、GX GDSCR、
GPUCC AHB、CX GMU 和 HLOS SMMU vote 分支。若看到 `cc=skip`，先根据
CFG AHB 原值设计下一轮时钟验证。全部采样均为只读，访问范围为 GCC 和满足前置条件的 GPUCC。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-power-v104-build
python3.14 evidence/gpu/power-v104/prepare.py
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

内核预链接、FAT 回读、硬件 DTS/ADT 检查及单测通过。完整平台检查停在历史
UniXNU revision 核对。详见 [主机验证](host-validation.json)。

2026-11-07 15:24（中国标准时间），Heimdall 成功上传 BOOT `031095d5…` 并请求重启。
镜像哈希及命令见 [打包记录](preparation.json) 和 [上传回执](upload.json)。
机主截图确认启动到 launchd main，八核运行，35 次 GOP 帧复制和退役。CFG AHB
为 `1`，GPUCC 可读。CX/GX GDSCR 都是 `222001`，CX 硬件状态为 `5ff4`。
CX/GX 的软件 collapse 位为 1，读到的上电位为 0。下一轮单独验证 CX 软件 vote。
[实测字段和截图哈希](device-result.json)
