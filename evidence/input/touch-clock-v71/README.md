# T970 触控 SE5 时钟探针 v71

v70 实测 SE5 关闭，从 AHB 报关闭且 HWCG 置位，GPIO12/13 仍为 GPIO。v71 在 v69 的启动基线使用 `t970-touch-bus-report=2` 和 75 秒终止报告。仅在 wrapper 两个 AHB 投票已存在且 SE5 投票未置位时临时置 SE5 投票。如果从 AHB 因 HWCG 报停，暂时清它的 HWCG 位。三条分支都报告运行时读取 SE5 固件版本、FIFO 禁用位和状态，随后恢复原控制位并读回。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py \
  --cached-headers --output out/data-bringup/touch-clock-v71-build
python3.14 evidence/display/hello-black-v64/prepare.py --touch-clock
```

宿主模拟通过已有 SE5 投票时拒绝、时钟未就绪时跳过寄存器、时钟就绪时采样并恢复原状态三个用例。时钟控制引用 [Kona GCC](https://github.com/mukahraman/kernel_samsung_sm8250/blob/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/clk/qcom/gcc-kona.c) 与 [时钟分支实现](https://github.com/mukahraman/kernel_samsung_sm8250/blob/97e4a5b907053c98b357da957a48586f66ad59c5/drivers/clk/qcom/clk-branch.c)。不改变 RCG、引脚、供电或 GENI 寄存器，不发送 I²C 命令。

## 实机结果

`vote=041007c0/041087c0/041007c0 clk=4220/0/0 restore=1 SE=read fw=303 fifoOff=1 st=0`。SE5 已装载协议 3（I²C）的固件，FIFO 接口关闭，采样时 SE 状态为 0。投票和受控位恢复成功。见 `device-result.json`。
