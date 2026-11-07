# v106 CX 上电期间的 XO 时钟验证

以 [v105 实测镜像](../cx-v105/device-result.json) 为基线。内核先按原条件启用 CX，
读到硬件应答后，核对 GMU RCGR 的 UPDATE 已清且当前源和分频是 XO 直通。按
[lmi clock_probe](https://github.com/Fsasdddd/lmi-uefi-touch-gpu/blob/0c9398400f937555918a53f1e9a97a90a3345257/tools/lmi-gpu-probe.c#L441-L470)
的顺序检查 AHB、CXO、CX GMU 分支。只对尚未置位的分支写 enable，先回读 AHB 的
enable，再要求 CXO、CX GMU 的 enable 和 CLK_OFF 分别为 1 和 0。

每个分支的原 enable 位按相反顺序恢复，再释放 CX。若某级恢复失败，
报告 `GPU xo hold` 并保留上游时钟和 CX，直到重启。此轮的寄存器访问限于 GCC 与 GPUCC。

`GPU xo rcg=CMD/CFG br=AHB/CXO/GMU mask=就绪/恢复 cx=应答/恢复`。
`mask=7/7 cx=1/1` 表示三条分支通过检查并恢复，CX 也正常恢复。
若源条件未通过，`rcg` 仍打印实测值，分支掩码为零。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --output out/data-bringup/gpu-xo-v106-build
python3.14 evidence/gpu/power-v104/prepare.py --xo-clocks
python3.14 -m unittest discover -s tests
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

2026-11-07 15:42（中国标准时间），Heimdall 成功上传 BOOT `d0a4c191…` 并请求重启。
详见 [打包记录](preparation.json)、[主机验证](host-validation.json)和 [上传回执](upload.json)。
启动后三指按住两秒，采集 `GPU xo` 一行。
