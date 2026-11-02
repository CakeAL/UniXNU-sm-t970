# 实际根因：正确根镜像配了旧错误 sparse 的 owner 策略

状态：**机主授权后两份载体已更新并整段读回验证，已返回XNU**。
回执见 `carrier-write-receipt.json`、`rescue-flash.json` 和 `xnu-flash.json`。
新鲜设备块证据见 `device-before-repair.json`：正确数据匹配新策略，而旧策略错误拒绝。
更新后两个关键根镜像块未变，见 `device-after-repair.json`（不是新的整卷读回）。

现有 `root-rewrite/receipt.json` 记录完整根镜像 fd43ee70… 已整段写入并读回一致。
本轮重新计算本机同一 raw 根镜像整段 SHA256，仍为该值。
但 `ufs-policy-carrier/root-manifests.json` 的窗口摘要为 OS47c1e4b0…／SystemOSee18c5c2…，
与 raw 根镜像 SHNGROOT 记录的 OSe5634d04…／SystemOSb4908cde… 不一致。

此前 `userdata-write-audit/audit.json` 已发现，09:16 旧 sparse 后两段由于源 seek 错误，
把根镜像开头 SHNGROOT 放到了后段起点。完整根镜像后来已直接重写，
策略生成仍使用保留的旧 sparse，因而把错误重现进哈希表。
`build-owner-root-manifests.py` 还有两处缺陷：SHA256 字段应位于窗口项偏移56，原来读80；
更关键的是读取了摘要却没有比较。六个样本验签未覆盖这个坏区域，不能替代全窗口比对。

`old-policy-full-check.json` 对旧 SystemOS 策略与原件的806400块逐块比较，首个不匹配
是块43008。`source-comparison.json` 显示该块 raw 根镜像与原始 SystemOS 一致，
旧 sparse 与旧策略均对应错误 SHNGROOT 头（SHA bc908a6c…）。
主机只读 F_LOG2PHYS_EXT 映射：`.03` 文件偏移0x2200000 的1MiB读取映射到
SystemOS块42898起，范围包含43008，与机主 stage171 的失败偏移吻合。
该映射是主机原件证据，不是新增设备读回。

修复后优先从已完整读回验证的 raw 根镜像生成：检查 SHNGROOT 校验和，正确解析摘要，
在任何签名前完整比对两个窗口；签名后再次比较，防止输入期间变化。
旧 sparse 现会明确拒绝（OS摘要不匹配），且不生成签名输出。

```sh
python3.14 -m unittest discover -s tests -p test_owner_manifest_inputs.py
python3.14 -m unittest discover -s tests -p test_policy_carrier_write.py
PATH=/opt/homebrew/opt/python@3.14/libexec/bin:$PATH python3.14 scripts/build-owner-root-manifests.py --image ../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/userdata/userdata-root.img --verify-all-blocks --output out/step7/owner-manifests-corrected
```

已验证：5项生成回归测试、5项写入中止／备份／读回顺序测试通过。
两份新包络 RSA 验签通过，真实 C 验证器核验全部 OS1483785块、SystemOS806400块；
窗口摘要匹配 SHNGROOT，公钥锚与现内核一致。完整哈希见 `root-manifests.json`。
重跑构建需使用新的输出目录。

准备的写入步骤见 `plan.json`：先用已资格验证的临时 Recovery BOOT取得root ADB，
核对型号／未挂载状态／userdata几何；**先备份并核对两份旧包络的SHA256**，
再更新 USERDATA 内固定 LBA5505024／5516624 的两个包络，共73287008字节。
每次 dd、sync、BLKFLSBUF 的退出码必须成功，随后按精确长度整段读回校验。
任何旧内容不匹配、写入或读回错误均中止，无自动重试。OS/SystemOS数据窗口保持原有输入。

机主明确回复继续后，先启动资格验证过的临时Recovery BOOT，两份旧包络先全部备份核对，
再更新载体且读回匹配，随后仅刷BOOT097c4f8c并重启，全部命令exit0。
原始包络备份留在忽略目录 `out/step7/policy-carrier-corrected-write/`。
机主随后画面变为 memorystatus no-victim，见 `../policy-memory/device-097c4f8c.json`。
不能仅凭新画面证明完整缓存映射或launchd主程序，但错误已不同于先前的缓存读取EACCES。
