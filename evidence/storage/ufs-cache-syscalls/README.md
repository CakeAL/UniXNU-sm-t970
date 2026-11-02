# dyld 缓存 syscall 返回码诊断

前一版 BOOT `49f3b166…` 已通过挂载及 `/System` 缓存 vnode 探测，但实际 dyld
仍报 namespace 6/code 1 的 libSystem 缺失、no dyld cache，carrier acc/rej=0/0。
照片与边界见 `../ufs-union-reference/device-49f3b166.json`。同卷 union 不一定调用 carrier，
所以计数为零不能定位失败，也不证明没有调用共享映射。

本版按 umi 有界、只读内核状态观测的方法加入 `t970-cache-syscalls.patch`：
观察 PID1 的真实 open/openat、fcntl、shared-region 返回码；保存 24 条，fatal exit
的原有 panic 中附最近 12 条。namei 仅在它原有的 copy 成功、长度验证后提供内核缓冲区，
不添加 copyin/copyinstr，不解引用 syscall 的用户指针，不改变错误、策略或返回行为。
路径为 PID1 最近复制的 namei 路径，不是完整的线程因果跟踪；`(no path note)`
也不证明没有进入 namei。范围和参考链接见 `design.json`。

```sh
python3.14 scripts/check-cache-syscall-trace.py --source ../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/tree/.cache/xnu-work/bsd/dev/arm/systemcalls.c
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 out/step7/record-cache-kernel-build.py out/step7/cache-syscalls-kernel.json
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 scripts/build-smmu-report.py --mode publish --kernel-build out/step7/cache-syscalls-kernel.json --output out/step7/probes/ufs-cache-syscalls
```

实际 helper 主机测试、稳定输入内核构建、链接符号、独立 FAT／FD／容量检查通过。
旧 `check-platform.py` 的历史组件断言失败未修复，也未声称通过。
内核 `170cc979f376f82a2e603b74be4377cbf41d8f3d498fcb83b7ebfa2bf8b34a67`；
BOOT `dd007d580e5ca5b5a29df04cc7861c36c09b23f8a10c7032b4f5fbaad421731a`。
本机镜像 `out/step7/probes/ufs-cache-syscalls/boot.img`；上一轮原始内核／改动源码
保存于 `out/step7/cache-syscalls-baseline/`，旧镜像各自保留不改。
22:47 仅上传 BOOT，Heimdall exit 0 并请求重启，见 `flash.json`／`flash.log`。
`image.json` 保留打包时状态；刷写以回执为准。实际启动跟踪尚待机主照片。

每条格式为 `sc<调用号> e<errno> r<返回值hex> a<fd或计数> c<fcntl命令> <路径>`。
常用调用：5/398=open；463/464=openat；92/406=fcntl；294=shared-region-check；
536=shared-region-map。e0 是 syscall 成功，返回值与具体调用一起解释；例如 r 值是十六进制。
暂不把任何一条 syscall 成功当作完整缓存映射或 launchd 主程序通过。
