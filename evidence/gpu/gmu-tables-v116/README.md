# v116 GMU/HFI 页表走查

诊断构建从 ArmSmmu4K 固定提交 `8bb168ad058c28d5c04f179ba407875eacba7ef3`
读取源码。启用 `t970-gpu-p=13` 后，由 XNU 分配并持有 200 KiB 连续物理内存。
开头 8 个 4 KiB 页作为页表池，随后 42 页覆盖 lmi 的五个 A650 GMU RAM 窗口。
探针只填零数据和页表，以 v112 的 SMMU ID 编码 TTBR0，然后沿编码地址通过 CPU 映射
读取实际描述符。结束即释放内存。此模式没有 GPU/SMMU MMIO 和固件执行。

启动后三指按住两秒，预期报告为
`GPU tables ok rc=0 table/leaf/read=5/42/2560 tcr=8080201c`。
失败时首字段区分分配、地址范围或连续性、建表、绑定、编码和走查阶段。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --output out/data-bringup/gpu-gmu-tables-v116-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-tables
python3.14 -m unittest discover -s tests
```
