# RAM Data接入（2026-11-02）

BOOT97271e99的18:22照片显示真正main marker1、err0、pages0x1b709，
即XNU管理约439MiB，比原256MiB窗口下约187MiB增加约252MiB。
512MiB请求已实机生效；free尾数字模糊，只记约2–3MiB。
free是vm_page_free_count，不包含全部可回收页，不能单凭此数判断耗尽。
物理8GB与EFI owned窗口不同，本轮没有修改DTS或回收保留区。

## 选择与配置

新增catalog RamBlock@25c57e0e；保留runtime NativeRamBlock。
board选择/归档该组件，但正常sm-t970_defconfig不启用Data；
新sm-t970_data_defconfig启用NATIVE_RAM_BLOCK和OWNER_DATA_MOUNT，并绑定真实种子UUID。
默认owned请求更新为已验证512MiB，ADT使用PackedRAMDisk与ephemeral-storage。
UFS持久化mode默认0，没有sheng-data-persist=2；只刷BOOT。

原32MiB种子复制到新的忽略文件，扩展文件至512MiB，hdiutil仅附加该文件，
根据其PhysicalStores寻找确切APFS容器，再diskutil apfs resizeContainer至完整大小。
卷UUID保持C25160D3-B586-4C11-9D3A-42CB2741227C，随后正常卸载并无损编码。
编码1040512字节，逻辑512MiB；输入和摘要见ram-data-integration/seed.json。
这不是预分配512MiB RAM：RamBlock以非零页和新增写入页为存储，重启丢失更改。
尚不能称满足完整iPadOS容量、权限、密钥或持久化要求。

## 构建与实际发现

独立输出在主框架out/t970-data-bringup，设备out/data-bringup为其忽略符号链接。
原始e4632618内核、旧输出、FD515105d7及原根卷/载体保留。
初次构建树位于设备out时，一个既有VerifiedRoot祖先查找失败；移至框架out后完成。
框架90b1574修正catalog archive名与runtime对象名不同的审计路径，并补全
现有主机Data挂载检查的可选回调替身；未修改XNU/Apple运行策略。

首次Data BOOT911a462a在18:34照片报AMFI: No PMGR，尚未进入Data挂载。
原因已由archive日志确认：新输出无参考内核，build-platform-power.py静默生成FirstPassStub。
这是构建回退错误，不是APFS或Data种子的实机结果。该镜像已在忽略目录保留并隔离。

修复取消隐式空实现：没有参考时直接失败；新树可通过UNIXNU_PMGR_REFERENCE_KERNEL
显式提供保留的已验证内核。此次重建使用原e4632618参考，完成真实PMGR ABI340项审计。
check-data-payload.py检查真实归档成员、源内核PMGR注册/虚表及RamBlock符号、源/打包内核摘要、
FAT内核/种子/trustcache、全部ADT属性以及header/精确FD/DTB/容量/零尾部。
实际缺失参考输入、先前失败的空PMGR内核都已验证被拒绝。
实际native_owner_data_prepare函数的9组主机API注入检查通过（不执行APFS）。

修复源内核40672e83，打包内核8ae115da，BOOT6b83f4e6。
Heimdall只刷完整BOOT，exit0且结束会话/请求重启正常；尚未读回或获得修复版实机反馈。
18:42实机随后报watchdogd[102]退出，namespace2/subcode5即SIGTRAP。
由于OWNER_DATA_MOUNT在exec前强制检查准确设备、可写APFS，服务启动证明越过挂载成功门槛。
Data写入与持久化、持续服务和桌面仍未验证；当前定位转为watchdogd。
原watchdogd离线执行显示缺IOWatchdog或打开失败均可能BRK，具体故障PC仍待捕获。
T733使用临时watchdogd启动禁用策略；本板已准备只禁用该job的原launchd配置并通过
原launchd二进制loader/权限/job-gate的主机替身检查，尚未在RAM Data应用。

## 命令

以下从UniXNU主目录执行；需要Python3.14的python3位于PATH前部：

```sh
./unixnu defconfig sm-t970_data_defconfig -D ../UniXNU-sm-t970 --out out/t970-data-bringup
UNIXNU_PMGR_REFERENCE_KERNEL="$PWD/out/sm-t970/ipados-17.7.11-21H461/sm-t970/kernel/kernel.macho" ./unixnu build kernel -D ../UniXNU-sm-t970 --out out/t970-data-bringup
./unixnu build payload -D ../UniXNU-sm-t970 --out out/t970-data-bringup --data-ramdisk ../UniXNU-sm-t970/out/step7/data-seed-512/data-512.dbr --kernel-arg launchdsuffix=release
```

bootimg必须显式复用设备out/step7/ufs-readonly-inputs/SILICIUM_UEFI.fd与
out/firmware-inputs/firmware.dtb；完整输入/输出/刷入回执见
evidence/storage/ram-data-integration及其pmgr-repaired子目录。
旧check-platform依赖历史框架、五组件和256MiB快照，仍需独立迁移复核；没有删除断言冒称通过。
