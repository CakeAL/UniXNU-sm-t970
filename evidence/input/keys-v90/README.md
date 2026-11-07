# T970 音量加 GPIO 编号修正 v90

v89 已实机得到电源和音量减各 `2/2`，但音量加一直读成按住。
原厂 `pinctrl-spmi-gpio.c:pmic_gpio_of_xlate` 匹配的是 **1 起始** 的物理 GPIO 编号，
`pad->base = start + i * 0x100`，`gpio_idx=i+1`。DT 的 GPIO3 在 SID4 的 `0xc200`，
不是 `0xc300`。v90 只把 PPID 从 `0x4c3` 修正为 `0x4c2`，仍不发送 HID。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --output out/data-bringup/keys-v90-build
python3.14 evidence/input/keys-v90/prepare.py
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/keys-v90/boot-partition.img
```

BOOT `f72005c420b2342ebdcb4b83b883a4e50ebdb5b63158c57d32f0ff3929d5da7f`，
内核构建、prelink、HID ABI 核对通过。上传成功并重启，等待实机三键各两次的计数。
ADT（3840 MiB 请求）、配置、Data、信任缓存、固件和分区尾部均保持。
构建输入／镜像及上传记录见 `preparation.json`、`upload.json`。

## 实机结果

2026-11-07 12:23:27：`v=50010000 pon=13 gpio=051 mask=0 power=2/2 up=2/2 down=2/2 stage=5 samples=15197 errors=0`。三键原始边沿全部通过。`main=1 cpu=8 sec=7 pages=0xe81db`，3840MiB请求继续启动。照片及哈希见 `device-result.json`；尚未发送HID。
