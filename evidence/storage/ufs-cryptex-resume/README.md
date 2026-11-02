# dsh 接手：让 cryptex 路径改动实际进入镜像

旧图按机主报告关联 BOOT `a41b5c11…`／kernel `d66b832b…`，不是设备读回证明。
`device-a41b5c11.json` 保存照片字段与关联边界；照片本身见 `device-photo.png`。
保存的主机内核哈希匹配，但当时解析配置和实际编译记录仍为
`XNU_OWNER_UNION_SYSTEMOS=1`，三路径诊断又会无条件 panic，故不能据此声称 dyld
执行过或缓存映射失败。

本轮显式关闭 union、重新生成 `.config`，并仅在挂载错误或 cryptex 缓存 lookup
失败时 panic。成功则继续 launchd。`compiler-check.json` 通过实际 clang 编译参数
重放预处理，确认生效的挂载点、环境目录、carrier 目录及条件 panic。
`verify-build.py` 保存该次主机检查的原脚本，默认读取本机已存在的构建树。

```sh
python3.14 ../UniXNU/unixnu defconfig sm-t970_defconfig -D .
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 out/step7/record-kernel-build.py out/step7/cryptex-resume-kernel.json
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 evidence/storage/ufs-cryptex-resume/verify-build.py
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 scripts/build-smmu-report.py --mode publish --kernel-build out/step7/cryptex-resume-kernel.json --output out/step7/probes/ufs-cryptex-resume
python3.14 scripts/check-hardware-description.py --unixnu ../UniXNU --firmware-dtb out/firmware-inputs/firmware.dtb --output out/step7/cryptex-resume-hardware
python3.14 ../UniXNU/scripts/porting-record.py check --device .
```

打包要求不存在的新输出目录；复现须换目录。构建记录保存的是构建当时输入哈希，后续
文档更新不在内核中。首次尝试因系统 Python 3.9 缺少 tomllib 退出，使用上述 PATH 后成功。
`check-platform.py` 已运行，但其早期五组件断言阻止后续检查；详见
`platform-check.log`。独立 DT/ADT 检查通过，不等于该脚本通过。

- 源内核：`8262854bf783e882ebafcb8c230844039493f7e6ecf226185bba03be4196e693`
- BOOT：`dc42838f17c0e82a542839fdcb013a33ef6711c5a19e46b2d6545579d30a1700`
- 本机 BOOT：`out/step7/probes/ufs-cryptex-resume/boot.img`（62,713,856 字节）
- 上轮原始内核／源码／配置／编译记录：`out/step7/cryptex-resume-baseline/`。
- 上轮 BOOT：`out/step7/probes/ufs-publish36/boot.img`，保留不改。

机主明确授权后，22:23（Asia/Shanghai）仅刷 BOOT，Heimdall exit 0，
日志确认 `BOOT upload successful`、`Rebooting device`。回执见 `flash.json`／`flash.log`。
`image.json` 的未刷写标记保留其打包时状态；当前刷写状态以回执为准。
实机启动结果待机主照片，不以传输成功代替验证。若挂载／路径失败，
看 mount/mstatus/sys/cryptex；若执行到 launchd 后退出，看 carrier acc/rej 与退出原因。
不从主机构建推断缓存映射、用户态进展或外设完成。
