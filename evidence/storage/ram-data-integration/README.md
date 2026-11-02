# RAM Data接入证据索引

新配置sm-t970_data_defconfig与catalog RamBlock，主机ABI和9例实际挂载函数/API替身检查通过。
512MiB逻辑APFS种子编码1040512字节；主机磁盘正常卸载，未写设备USERDATA。
具体源、命令及限制见docs/ram-data.md和build.json。

本目录根的validation/payload/boot/upload等属于首次911a462a：主机通过包装检查，
但18:34实机AMFI No PMGR。device-result.json与原图保留失败；没有Data成功结论。
根因是初次独立输出无参考内核，脚本静默归档FirstPassStub。build-platform-power.py现已拒绝该回退。

pmgr-repaired/属于6b83f4e6：真实PMGR340项ABI、归档成员/注册符号及RamBlock/完整包装检查通过。
缺失参考与实际旧空PMGR内核均被拒绝。BOOT-only上传exit0正常结束；没有分区读回。
后续18:42的watchdogd PID102/SIGTRAP证据在../watchdogd/，表明越过强制Data挂载门槛。
Data具体写入/持久化与持续服务、桌面仍未验证。上传回执中pending为上传当时状态。

历史平台检查依赖旧框架/五组件/256MiB快照，本轮运行仍失败并保留platform-check.log；
不删断言、不冒称通过。独立新配置的源编译、原存储ABI、Data挂载函数及包装检查另行报告。
