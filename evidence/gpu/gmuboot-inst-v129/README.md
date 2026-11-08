# v129 SID5 保留原始取指属性

[v128 实测](../gmuboot-exec-v128/device-result.json)记录了 HFI 队列和电源日志
起始页上的 IND 权限故障。此前借用的 FAULT 表项保留了
`S2CR0.INSTCFG[27:26]=3`，所以 SMMU 把匹配 SID5 的读请求标为取指。
`FSYNR0.IND` 记录应用覆盖后的属性。见 [Arm SMMUv2 §3.4、§9.6](https://documentation-service.arm.com/static/5f900d34f86e16515cdc08fb)。

模式 25 将 SID5 翻译表项的 INSTCFG 设为 0，以使用请求原有的属性。
对于实测继承值 `0x1f3aeaff`，预期读回 `s2=1038eb00`。
完整回读匹配后才发布 SMR0。临时 RAM、HFI 队列和电源日志按原始页表
以 XN 建立。若后续仍有权限故障，沿用已有的有界捕获和重试。
验收点是 `FW_INIT`、HFI 就绪和故障数，后续独立验证 `FW_VER` 应答。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-gmuboot-inst-v129-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-boot-default-inst
python3.14 -m unittest discover -s tests
```

[镜像清单](preparation.json)和[刷写回执](upload.json)对应 BOOT
`866a0644d8bbba90ce7dd2caa08d78e479b36713f59bb802b59fe0650b7cb2e3`。
Heimdall 确认上传并请求重启。[实机报告](device-result.json)回读
`s2=1038eb00 fw=100 hfi=1/20000001 rst=0 pf=0`，GMU 已运行，
HFI 队列已就绪。八核在线，Data 查询成功，GOP 完成 32 次拷贝和回收。
[主机验证](host-validation.json)包括路由回读与撤销模型、封包和独立
DTS/ADT 检查。完整平台检查停在历史框架版本校验。
