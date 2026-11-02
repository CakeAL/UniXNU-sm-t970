# 512MiB EFI owned window：正常运行镜像

2026-11-02，上一版 BOOT870a11da 已实测 launchd main，但终止停点只剩260页空闲。
平板有8GB物理内存，当前XNU只获得256MiB诊断窗口；不能将这两个数字混为一谈。

`scripts/prepare-owned-window.py --mib 512 --output out/step7/probes/owned-512-normal`
从固定SHA256的正常release镜像73a5738b复制，只修改ADT
`/chosen/darwinboot-memory-size` 为 `0x20000000`。
脚本解析整棵ADT并独立读回FAT中的内核、ADT、trustcache及配置；
正常内核0b04a782保持，无main终止探针。Android头、BootShim、精确FD515105d7、
firmware DTB、尾部均与正常源逐字节一致。board.toml与DTS保持。

输出BOOT867efc599a7686a86f4fa4c4394c26979b99a1789f452ac1da2d8da588e9728a，
完整71303168字节。机主确认进入Download后，仅上传BOOT，Heimdall exit0，
正常结束并请求重启；未写USERDATA/DTBO/RECOVERY。见preparation.json、upload.json及原始flash.log。

DarwinBoot的AllocateWindow只从EFI conventional memory寻找连续区间并正式AllocatePages；
请求512MiB不是声明某块物理区域可用，分配失败应显示NO WINDOW而非回收保留区。
当前源码支持该请求，实机是否采用512MiB仍须读取loader窗口或内核页数确认。
未完成BOOT分区读回，不能把上传当作落盘比对或启动成功。

可写Data仍未配置。本版让launchd继续正常执行；新panic、自动重启及服务阶段均待设备反馈。
后续Data先采用RamBlock独立可变APFS种子进行接入验证；大于2GiB的逻辑种子依赖持久写后端，
不能直接用于尚未验证写入窗口的T970。不得直接启用sheng-data-persist=2。

机主随后报告867efc59貌似卡粉条。由于保留条不定位执行阶段，接着使用
`--confirm-main`生成97271e99：ADT请求仍512MiB，内核加入已验证的真正main终止观察器，
原handler参数/返回及marker不伪造，two existing main-probe tests pass。
Heimdall仅刷BOOT，exit0并正常结束/请求重启，见main-checkpoint/。
此版用于读取实际pages/free确认内存状态；当前设备为该检查版，观测仍待回报。
