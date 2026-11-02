# 策略内存复用及用户态启动验证

2026-11-02实机已确认launchd到达main：`initproc-main/device.jpg`显示
`launchd main marker=1 err=0`，BOOT870a11da、源内核e4632618。
该诊断只读真正的kern.initproc_spawned，保留原处理/权限路径，不伪造标记；
观察后有意停在panic画面。系统服务、可写Data与桌面仍未验证。

## 已完成的证据链

- 修正载体后BOOT097c4f8c出现no-victim内存panic。原载体与复制哈希表各占73,293,824字节。
- 精确来源的载体改为只读借用，保留独立只读公钥页并重新验证。实际configure/free的
  ASan/UBSan+mprotect检查覆盖借用/回退、保护/验证/分配失败和释放；原256MiB窗口不变。
- 原机DTBO恢复后重新进入XNU。原数据被机主删除后，已重新完整恢复并读回根镜像和载体；
  详见相邻root-restore-twrp-20261102与bootloader-audit-20261102。
- release-exec-status：正式/sbin/launchd原exec返回0，仍不能单独证明main。
- first-unix-syscall：用户态SVC到达BSD入口。
- shared-map-result：实际vm_shared_region_map_file返回kr=0。
- post-map-syscall：既有记录确认PID1缓存系统调用536返回0，后续close6也返回0。
- initproc-main：真正main标记1，原sysctl返回0。此时free=0x104页约1MiB；
  属于诊断停点快照，不单独判定耗尽，也不据此把保留区当RAM。

每个子目录保存准备/独立校验、上传回执、实机结果及对应照片；历史pending字段
是当时的准备/上传状态，后续结果以device-result.json为准。原始内核、正常版12766f5f、
全部探针与BOOT/RECOVERY/载体备份保存在ignored out/；公开目录不含镜像或私有种子。
当前设备仍为会有意停止的870a11da诊断版，TWRP保留于RECOVERY。
