# SE0 时钟与实际托管内存 v93

BOOT `bb5bd9d090c20e64bfea37aff50c267f635619db15d178a38b8da3d7ed2637c6`。
在 v92 基础上优先排列外设报告，避免共享 896 字节缓冲截断；只临时清除
slave AHB 的 HWCG 位，确认运行后读取 SE0，再恢复原位。不发送 I²C 事务。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/battery-clock-v93-build
python3.14 evidence/power/battery-clock-v93/prepare.py
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/battery-clock-v93/boot-partition.img
```

12:47:35 实机照片及 `device-result.json` 确认：

- `Memory owned base=c007c000 size=f0000000 actual=f0000000 top=c43b8000`。
  Loader 实际拥有 3840 MiB，管理页 `0xe81d9`；没有完整 EFI 图或全 8 GB 验证。
- `Battery CLK slave=80000002/0 restore=1 SE=read fw=303 fifoOff=0 st=0`。
  固件协议 **3 是 I²C**，版本 3，FIFO 启用，M/S 引擎未忙。
- 桌面 `main=1 cpu=8 sec=7`；三键观察无错，`hid=1/15/0`。

原始镜像、构建日志留在忽略目录；当前源文件后来已进入 v94，故本目录
`source/` 保留 v93 编译时快照。`preparation.json`、`upload.json`、`flash.log`
分别记录准备、传输和重启请求，未做 BOOT 分区读回。
