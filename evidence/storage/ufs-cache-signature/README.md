# .03 缓存签名添加失败的边界核查

BOOT dd007d58 机主照片：缓存 `.02` 打开、F_ADDFILESIGS_RETURN(97) 成功；
`.03` 打开成功但命令97返回 EACCES13。见 `device-dd007d58.json`／`.jpg`。
主机原始缓存及 .01-.04 逐页 CodeDirectory 验证均通过，哈希都在当前使用的
原始 System trust module；数据见 `host-code-signatures.json`。这不是设备读回或运行时验证。

加入仅锁存首个 PID1 EACCES 的签名阶段／偏移／内核已有 CDHash 观测。
`stages.json` 给出阶段定义；未改错误、策略或原始文件。
实际 helper 的 PID/错误过滤、首失败保留、偏移/哈希编码及空哈希主机测试通过。

```sh
python3.14 scripts/check-cache-signature-stage.py --source ../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/tree/.cache/xnu-work/bsd/kern/kern_descrip.c
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 out/step7/record-csig-kernel-build.py out/step7/cache-signature-kernel.json
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 scripts/build-smmu-report.py --mode publish --kernel-build out/step7/cache-signature-kernel.json --output out/step7/probes/ufs-cache-signature
```

内核 e1c866a2…、BOOT 6b04878c… 构建输入稳定，链接及独立 FAT/FD/容量检查通过。
22:58 仅刷 BOOT，Heimdall exit0 并请求重启；回执与完整哈希见 `flash.json`。
打包时 `image.json` 状态保留；实际状态以回执及后续观察为准。
随后机主照片见 `../ufs-cache-read-source/device-6b04878c.json`：
`stage=171 off=2200000 cd=55b4a307efbf08234c98c81f09f1d17e5efc0d0a`。
即原始 AMFI 及前置签名设置已经通过，失败来自 native4k 准备中的真实 vn_rdwr，
文件偏移34MiB；不能再把这次 EACCES 归因于 AMFI 拒绝或缺失信任条目。
下一轮区分 MAC 读取检查与 VNOP_READ／底层完整性错误。
