# SystemOS union 与参考移植核查

`dc42838f` 的照片与只读主机 `lstat/readlink` 核查共同表明：
`System/Cryptexes/OS` 是指向空 Preboot 下缺失目录的链接，不是可直接挂载的目录。
照片见 `device-dc42838f.jpg`，原始字段／关联边界见同名 JSON；主机路径见 `host-paths.json`。

按机主要求比较 T733 `3bb0d6f…` 和 SM8250 umi `3eb7257…` 的启动配置，
两者启用 readonly SystemOS root union、cache startup、boot manifest 和签名哈希缓存。
源码固定链接和快照哈希见 `references.json`。本轮恢复该布局，停止要求后期 cryptex 别名存在。
`/private/preboot/Cryptexes/OS` 的规范视图需要后续 Data 准备，不能从别的设备推断已实现。

T733 另修复 `kernproc->fd_cdir` 与 `rootvnode` 的共享引用：本机 XNU 的
`set_rootvnode` 同样只提供一个引用，旧 `checkdirs` 在 callback 和全局转移时重复释放。
对实际 XNU 函数的主机测试旧版本失败，修复后五种 cwd/rdir 场景通过。
这不是照片中 ENOENT 的根因；作为独立、经源码与测试核对的正确性修复纳入。

```sh
python3.14 scripts/check-union-root-reference.py --source ../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/tree/.cache/xnu-work/bsd/vfs/vfs_syscalls.c
python3.14 ../UniXNU/unixnu defconfig sm-t970_defconfig -D .
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 out/step7/record-union-kernel-build.py out/step7/union-reference-kernel.json
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 evidence/storage/ufs-union-reference/verify-build.py
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 scripts/build-smmu-report.py --mode publish --kernel-build out/step7/union-reference-kernel.json --output out/step7/probes/ufs-union-reference
```

构建器记录 tracked 和未忽略的新输入，前后哈希稳定。编译参数重放预处理确认 union=1、
无 DYLD_SHARED_CACHE_DIR 覆盖，诊断只要求真正的 `/System` 缓存路径。
FAT／FD／容量检查通过。旧 `check-platform.py` 的组件断言问题保留，未声称通过。

BOOT `49f3b166316b3314d36c4bbbbe64a1434ab8302609c5649c8dfc8b006fd20ff7`，
kernel `1d83105ebe04011b84915342aee4fea8173843bba531d4c3f7d3e0f47c66a93c`。
22:35 仅上传 BOOT，Heimdall exit 0 并请求重启；见 `flash.json`／`flash.log`。
打包时 `image.json` 的未刷写标记保留其准备时状态，当前以回执为准。

机主随后照片（`device-49f3b166.json`／`.jpg`）确认越过挂载及缓存 vnode 探测，
实际 dyld 仍以 namespace 6/code 1 报 libSystem 缺失、no dyld cache；carrier acc/rej 均为 0。
union 同卷可能不调用 carrier，不能据此断言没有发起共享映射。下一步记录真实
open/openat、fcntl 与共享映射返回码，不再仅凭路径和最终错误猜测。
缓存完整映射、launchd 主程序、可写 Data 与界面尚未验证；未改写系统卷或 Data。
