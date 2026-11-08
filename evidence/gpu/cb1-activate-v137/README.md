# v137 CB1 启停与 ASID 2 TLB 同步

模式 33 从[实测通过的 v136](../cb1-root-v136/device-result.json)构建，
安装并走查独立的 17 页 CB1 映射。复用 v121 的 ArmSmmu4K
TLBIASID 和轮询同步路径，分别在 CB1 开启前和关闭后同步 ASID 2。
开关前后检查 live SID5 和原有 stream 状态，CB1 通过轮询观察 fault。
关闭读回失败或同步超时会在诊断行标出阶段，页表和 SQE backing 保留至重启。

实机预期 `GPU cb1ctx ok/ok tlb=3/2 ctl=a7/a6 f=400/400 leaf=17 held=1`。
`tlb` 的首项为两个同步的完成位图，次项为状态轮询总数。
在该探针中 CP 保持空闲，GPU stream 仍处于 FAULT 路由。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --sqe-firmware .cache/firmware/gpu-candidates/samsung-common-a650_sqe.fw --output out/data-bringup/gpu-cb1-activate-v137-build
python3.14 evidence/gpu/power-v104/prepare.py --gpu-cb1-activate
python3.14 -m unittest discover -s tests
```

[镜像清单](preparation.json)和[主机验证](host-validation.json)绑定
BOOT `f697aa74ba25972dde443854f12e06d974b4ff860598c47f5c76ab0408e01792`。
Heimdall 在 19:37:12 确认 BOOT 上传并请求重启，等待设备报告。
见[刷写回执](upload.json)和[传输日志](flash.log)。
