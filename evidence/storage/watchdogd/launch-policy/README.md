# 临时launchd策略镜像2387e904（实机结果待回报）

在已实测启动watchdogd的6b83f4e6基础上，新增设备补丁t970-watchdog-launch-policy.patch。
只有参数t970-disable-watchdogd=1明确启用时，才在Data挂载成功、init exec之前安装策略。
普通board参数未添加它；不修改watchdogd、launchd、原OS或critical-exit处理。

helper要求NATIVE_RAM_BLOCK、UFS持久化mode0、Data阶段4且非只读、当前凭据uid0。
预查disabled.plist和disabled.migrated，任一存在或查找异常就拒绝，绝不覆盖旧策略。
目录nofollow检查并设置root:wheel/0755；两文件O_CREAT|O_EXCL|O_NOFOLLOW新建。
策略内容仅com.apple.watchdogd=true，root:wheel/0644，完整写入、设置元数据、fsync和close。
这些操作都成功后，才新建同所有权的空迁移标记，让原launchd读取原有override机制。
实际错误及阶段经panic报告；策略失败不会被当作成功继续执行。

主机原种子来源目录中没有这两个文件；packed seed4591566e保持不变。
实际helper通过ASan/UBSan执行15个API失败点，以及持久化/UID/mount守卫、已有文件、
mkdir EEXIST、部分写入、错误节点类型与关闭/引用释放检查。API是替身，不是APFS实机验证。
helper中嵌入的配置逐字节等于此前原launchd二进制loader/job-gate测试的disabled.plist。

源内核39d7cfe1，payload内核7ad48eae，完整BOOT2387e904。
独立检查真实PMGR340-slot归档、PMGR与RamBlock/策略符号、全部FAT输入、原trustcache、
精确FD515105d7/firmwareDTB/header v2/容量/零尾部，以及实际命令行只增加策略参数。
未选择--watchdog-policy的核查会拒绝这份带策略参数的镜像，负例已通过。
先前正常Data源内核40672e83与6b83f4e6 BOOT均保留。

只上传BOOT，Heimdall exit0，正常结束并请求重启；未做分区读回。
策略是否实际安装、watchdogd是否跳过、其他服务是否继续，均待设备证据。
色条保留不定位执行进度；没有新文字不等于正常运行或卡死。

可复核命令（设备仓库）：
```
python3.14 scripts/check-watchdog-launch-policy.py --source out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data/tree/.cache/xnu-work/bsd/kern/kern_exec.c --output out/new-policy-host-check
python3.14 scripts/check-data-payload.py --work out/data-bringup/sm-t970/ipados-17.7.11-21H461/sm-t970_data --boot out/data-bringup/watchdog-policy.img --seed out/step7/data-seed-512/data-512.dbr --watchdog-policy --output out/new-policy-pack-check
```
