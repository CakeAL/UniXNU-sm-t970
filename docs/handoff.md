# SM-T970 移植交接（2026-11-01）

接手者请先读本页，再看 `porting.toml`、`docs/bring-up.md`、`docs/storage.md` 和
`evidence/bring-up/README.md`。

## 最新：PID1已打开缓存.39，45秒检查版已刷入（2026-11-03）

79a949b6的01:07:19照片：cpu8/sec7/main0/n2，blocks546747、cache syscalls82，
最近openat/fcntl均e0，最后打开dyld_shared_cache_arm64.39；c97是F_ADDFILESIGS_RETURN。
原SystemOS目录含52个编号分片，.40–.52逻辑大小约990MB；当前证据支持缓存准备继续推进，
尚未观测到此轮共享缓存映射返回与launchd main1。

当前be219c43沿用完全相同3d114c44/89855bef内核，只延后终止采样到45秒；
仍八核、标准SGI、相同RAM Data/信任输入及PID1紧凑追踪。
准备/打包检查通过；BOOT-only上传exit0正常结束并请求重启，实际结果待回报，见runtime-cache30/device-result和runtime-cache45。

## 最新：八核20秒复现，PID1缓存追踪版已刷（2026-11-03）

八核0dba26bc沿用已验证的内核，仅延后到20秒终止采样；实机仍cpu8/sec7/main0/n2，
blocks371515，对比10秒189168提示继续读取。CPU5有timer2，CPU4/6/7此时未观察到timer。
这两张是不同启动的快照，不当作同次运行的精确速率测量；更不能由main0单独断言卡死。

当前BOOT79a949b6：新增显式t970-runtime-cache-trace=1，八核、目标30秒加100ms。
画面紧凑显示runtime、C行和已有PID1缓存系统调用记录（最后完成的最多12条），
不改变授权/返回值，不额外copyin。追踪是尽力快照，不直接代表当前正在阻塞的调用。
源内核3d114c44、ArmCpu b5f9775，构建与格式化器/实际调用/SGI/发布/独立打包检查通过。
见evidence/cpu/smp-bringup/runtime20及runtime-cache30；新实机结果待回报。

## 最新：八核启动与各核SGI已实测（2026-11-03）

当前BOOTd95c45d9已收到00:49:07实机照片：cpu8/sec7，全部副核step7/PSCI0/fail0/C4，
八核SGI54/62/59/26/6/24/2/1合计234，I行recv234；实际标准SGI投递已覆盖所有核心。
计时器21084/23357/2086/5/0/0/2385/0，CPU4/5/7此时尚未观察到timer中断。
10秒main0/n2，尚未证明用户态持续启动或桌面；后续需每核工作负载/计时器和启动推进验证。
证据见evidence/cpu/smp-bringup/sgi-asm/cpu8/device-result.json。

内核仍使用显式本地ArmCpu b5f9775（.cache/armcpu-sgi-asm），默认目录/feed9066保持；
后续每条构建/打包命令必须保留local-module，prepare-smp必须传armcpu-source。
八核这张图是CPU阶段成功，不把旧120秒CPU0的main1与当前八核main0混为一轮结果。

## 最新：两核SGI已收到，按机主要求直接验证八核（2026-11-03）

00:46:05照片确认BOOT1c778e4b两核SGI计数44/102，总recv146，CPU1在检查期间99→102。
标准SGI指令分隔修复已在实机产生接收；独立固定发送核心的双向测试尚未完成。
10秒main0/n2仍是早期快照，不能视为用户态持续启动已通过。

当前已刷八核BOOTd95c45d9（exit0正常结束并请求重启），按机主明确要求跳过四核。
沿用相同源内核a65817b8/payload内核9dc8a62c、ArmCpu b5f9775，只改拓扑和cpus=8。
八核结果待回报，逐核查看C行及XNU cpu数；sec是非原子共享计数，不单独据此判断遗漏核心。
当前实际源码必须用.cache/armcpu-sgi-asm的显式local-module；默认目录/feed仍旧版本。
证据见evidence/cpu/smp-bringup/sgi-asm/device-result.json和cpu8上传回执。

## 最新：修复实际SGI指令缺失（2026-11-03）

BOOT1c778e4b已刷入，BOOT-only、exit0正常结束并请求重启；两核，10秒加100ms采样。
ArmCpu实验提交b5f9775777aafe850a4ec8778b03154dfcabbd2b在.cache/armcpu-sgi-asm；
构建/打包均须显式--local-module driver:ArmCpu=<该路径>，prepare-smp须--armcpu-source。
默认组件/目录/feed仍9066；组件提交只在本机，补丁与源码/归档哈希已归档。

旧对象/内核中分号分隔内联汇编只生成首条DSB，没有SGI写入，之前sent/test不代表硬件发送。
本次统一修正17个字符串。新对象、内核、payload均实查通过SGI写入及同步/计数器/DAIF指令；
旧内核负对照按预期拒绝。T733 redistributor方案的本地实验未刷入，优先验证正确标准指令。
页表发布、C入口标记、96组汇编入口及独立打包检查保留通过；实际新SGI投递待回报。
证据见evidence/cpu/smp-bringup/sgi-asm。下一张图看两核SGI、I行recv和launchd main。

## 最新：两核和计时器已实测，标准SGI未收到（2026-11-03）

BOOT6fe3e519的00:13:58照片确认cpu2/sec1、CPU1 phase7/C4、timer22925/22334，
副核TTBR1=c4325000与主核一致。页表交接发布已越过此前副核启动阻塞。
新BOOT7e60f7c9只刷BOOT，上传exit0正常重启；第一次UFS NOP stage0拒绝，
机主重启相同镜像后恢复读取，两核/计时器再次确认。
IPI采样attempt1/sent2/test1/recv0/cpu1=0>0，目标GIC帧found1。
目前不能把在线2核等同于调度已完成；先定位SGI投递，再逐步4/8核。
默认DTS仍CPU0；8核预备镜像未刷。主机36种IPI逻辑检查、链接后调用核对、
原96组入口/2组跳转/10组C标记及独立打包均通过；实际SGI投递尚未通过。
详见evidence/cpu/smp-bringup/ipi-check/device-result.json，含首次失败和重启后成功照片。

## 最新页表交接对照（2026-11-03）

BOOT6fe3e519已刷入，BOOT-only、exit0正常结束并请求重启；目标等待10秒，2核。
显式t970-smp-publish-state=1在副核唤醒前清理当前cpu_ttep和sysreg_restore。
直接依据T733 ArmCpu55cc0617的同类清理；本板上一张36c2f602照片记录CPU1 TTBR1=0、
主核c4325000。实机是否修复尚待新V行、CPU在线/每核计时器/IPI记录。

此前C标记4被XNU_NATIVE_ARCH_TIMER的C宏条件编译掉，已改为有效的!CONFIG_SPTM。
首个清理构建也被此条件编译掉，未刷入；最终payload已核对两次清理的真实符号地址/8字节参数、
平台唤醒前的调用位置，并执行10组实际C入口标记模拟。旧C4缺失不能单独定位入口。
汇编96组、跳转2组、helper6组和独立payload校验通过，默认CPU0配置与旧镜像保留。
详见evidence/cpu/smp-bringup/reset-publish和docs/smp-bringup.md。

## 最新副核诊断（2026-11-02）

最新BOOT36c2f602已刷入（BOOT-only，exit0正常结束并请求重启）：目标10秒，
跳转前捕获V行，11为BR前，12为高地址入口使用原物理记录指针，随后10和最终C标记4保留。
此前b44e4108实机标记9，尚不能区分高地址跳转与新地址下记录访问问题。
96组入口与2组实际链接跳转模拟、runtime回归、独立打包通过；实机高地址结果待回报。
证据见evidence/cpu/smp-bringup/trampoline-trace。

当前已刷BOOTb44e4108：副核MMU分段5/6/7/8/9/10，最终C入口仍为4。
目标等待10秒；96组链接后指令模拟和payload异常向量比较通过，BOOT-only上传exit0正常重启。
实机结果待回报，见evidence/cpu/smp-bringup/mmu-trace；默认CPU0与原镜像保留。

23:44:40照片确认BOOT95accf53的CPU1入口3：副核已到common_start前，C标记4未见。
10秒时main0/n2为早期采样，不能与旧120秒进程数直接比较。下一版细分MMU切换路径。

BOOT9d4dc888实机main1、106进程，但请求2核仍只有1核，CPU1 step4/PSCI0、timer0/SGI0。
reset table、CPU1 affinity与reset handler均匹配。尚未确认副核进入复位代码。
已刷BOOT95accf53：四段入口标记、目标等待10秒；Heimdall exit0正常结束并请求重启，实机结果待回报。
它是一次终止采样，不是持续刷新。主仓库d57d612修复显示区边界，独立比较确认异常向量和标记保留。
默认CPU0、普通镜像2387e904、原内核及旧诊断镜像均保留；8核版本尚未刷入。
具体标记及可见性限制见[smp-bringup.md](smp-bringup.md)。

## 最新实机：109个进程，SpringBoard27/backboardd56/runningboardd26

BOOTeeeba83b的19:36:40照片：runtime target120 main1 n109 wd0 sb27 bb56 rb26 D0 W0 S4，
累计964876个verified blocks。诊断线程完成了deadline等待并报告进程列表，计时精度未测。
临时策略下此时没有观察到watchdogd；有真实界面服务进程，但不证明它们正常呈现或桌面可用。
XNU的软件显示后端目前仍关闭，不能继续把保留紫条当成早期启动故障。
结果和原图绑定见evidence/storage/watchdogd/runtime-report/device-result.json。

机主希望同时推进多核；T733使用定制ArmCpu55cc0617及redist-ipi方案，不能只复制其参数。
同为SM8250的umi实测8核，其audit_umi_smp.py使用PSCI SMC64/清理reset代码和数据缓存、
Affinity1 CPU编号与普通SGI0，开启self-ipi、关闭spi-ipi。T970已有对应共享入口/ArmCpu代码，
下一步需独立验证本板的每核在线、计时器和IPI，不把对方成果当作本板实测。

## 当前镜像：服务采样eeeba83b，实机结果待回报

在已实测main/Data/策略成功基础上新增显式t970-runtime-report=120的一次性内核线程。
Data/策略安装后休眠让出CPU，目标120秒后有意panic显示原main状态、进程数量、
watchdogd/SpringBoard/backboardd/runningboardd PID、Data/策略状态、累计校验块及前18个进程名。
该时间从诊断线程开始等待算起，不是开机计时；实际时钟唤醒/进程采样均待本次实机结果。
枚举不等待exec过渡，callback上限512、名字缓冲512字节，PID出现不代表UI可用。

源内核ab84b0ca与真实PMGR重建成功，实际helper有界行为/调度API替身检查和策略回归通过。
独立打包检查要求符号、明确bootarg120及全部固定输入；普通board参数不添加此终止诊断。
BOOTeeeba83b仅刷BOOT，Heimdall exit0正常结束/请求重启。普通2387e904和检查28268af5均保留。
详见evidence/storage/watchdogd/runtime-report，下一步读取runtime行和进程名以定位服务/显示阶段。

## 最新：main1/Data0/policy0/stage4已实测，正常2387e904已恢复

正常2387e904超过4分钟保留紫条后，隔离28268af5只读检查版19:10照片显示
`main=1 e=0 D=0 W=0 S=4`。RAM Data挂载和策略/迁移标记的实际写入、root元数据、
fsync/close均已完成，并继续到真正launchd main。不是只凭紫条推断成功。
尚不能证明原launchd随后加载override、watchdogd跳过、后续服务或桌面正常。

脚本boot-state-probe.py只改固定内核副本的空白padding和原sysctl尾分支，
保留原handler/参数/返回，27组Unicorn状态/错误测试和实际镜像独立读回检查通过。
检查版有意终止；已仅刷BOOT恢复原正常2387e904，Heimdall exit0且正常请求重启。
图像/镜像绑定与恢复回执见evidence/storage/watchdogd/boot-state-main及policy-normal-resume。
下一步采样后续进程，区分无显示输出和服务等待，不继续以紫条时长定位。

## 当前镜像：临时watchdogd策略2387e904，待实机回报

已在成功挂载RAM Data后、exec前接入t970-disable-watchdogd=1的显式策略。
只在RAM Data/持久化mode0/root凭据下新建root-owned的disabled.plist与迁移标记，
已有配置拒绝覆盖，任何写入/元数据/fsync/close错误均停止并报实际错误及阶段。
原launchd/watchdogd、原OS、critical-exit panic都不改；board默认参数不添加此项。

源内核39d7cfe1、BOOT2387e904已完成构建，实际helper15个API失败点及守卫/清理检查通过，
helper配置与已测试的原launchd配置一致。打包检查核对真实PMGR/全部FAT/ADT/种子/精确FD/DTB，
并要求策略实现符号与实际bootarg；拒绝未声明策略的检查负例通过。
BOOT-only上传exit0并正常结束/请求重启。当前策略安装和服务继续尚待设备回报；
保留色条不能当作成功或失败证据。详见evidence/storage/watchdogd/launch-policy。

## 当前镜像：RAM Data已越过挂载检查，watchdogd SIGTRAP

BOOT6b83f4e6经过超过2分钟保留色条后，18:42照片出现watchdogd[102]退出，namespace2/subcode5。
源码reason.h/signal.h对应SIGTRAP。系统已经拉起服务，不是凭色条推断的早期卡死。
本版OWNER_DATA_MOUNT在exec前强制检查Data设备/可写/APFS，失败即panic；
因此服务启动证明越过该挂载成功门槛，不等于单独写入测试或持久化验证。
下一步只为RAM Data安装root-owned的原launchd禁用watchdogd策略；不吞掉critical-exit panic，
不修改原OS/watchdogd或伪造IOWatchdog硬件。候选plist与原二进制host分支测试已准备，尚未应用。
具体根因PC尚未捕获：缺IOWatchdog与service-open失败都可触发BRK，不能只凭SIGTRAP二选一。
新证据见evidence/storage/watchdogd。

## 已完成：真实PMGR与RAM Data版本6b83f4e6

512MiB main检查已实测：18:22照片marker1 err0、pages0x1b709约439MiB，扩容生效。
随后完成RamBlock、512MiB逻辑APFS种子和Data挂载配置的独立构建；首次911a462a报
AMFI No PMGR，定位到新目录的PMGR脚本隐式FirstPassStub（此前漏检）。
现已取消该回退，显式使用原e4632618参考重新审计/构建真实PMGR；新增打包检查拒绝空实现。
修复BOOT6b83f4e6已仅刷BOOT，Heimdall exit0正常结束/请求重启。当前不是main终止探针；
原始内核/旧BOOT/根卷/载体均保留。现已获得上段的服务退出证据。

使用sm-t970_data_defconfig，输出在主框架out/t970-data-bringup，设备out/data-bringup符号链接。
主框架新增构建/主机测试修复90b1574。默认板级owned请求现为已验证512MiB，DTS不变。
完整说明与命令见docs/ram-data.md；结果绑定见evidence/storage/ram-data-integration。
下列“待512MiB结果”等文字保留当时历史状态，以本段与device-result.json为准。

## 当前镜像：512MiB main检查，实际扩容结果待设备回报

先上传无终止探针的正常BOOT867efc59，只在原正常release镜像中将chosen内存请求
由256改为512MiB；机主报告貌似卡粉条。该画面本身不能定位，不能当作分配失败。
为核实实际窗口与内存余量，随后上传BOOT97271e99（同一512MiB ADT，恢复已验证的main
终止观察器），两次Heimdall均exit0且正常结束/请求重启。当前设备为97271e99，待拍摄
`launchd main marker=...`、`pages`和`free`；没有BOOT读回，不冒称落盘比对完成。

8GB为设备物理内存；256MiB是原XNU获得的诊断owned window。DarwinBoot仅能通过
EFI ConventionalMemory正式申请更大连续区间；本轮没有改DTS或回收保留洞，board默认仍256MiB。
源码、固定镜像及包装范围检查见evidence/storage/owned-window-512，主机准备脚本支持
正常和--confirm-main两种模式。main检查有意停止，不能误报服务已继续执行。

另已在主机新建32MiB APFS Data种子，复制原OS39份var文件，DBRDISK1编码1007696字节，
完整逻辑内容摘要与原容器相同，正常卸载；没有写平板或修改OS镜像。
该最小输入尚未集成RamBlock/OWNER_DATA_MOUNT，不满足完整系统运行容量声明。
下一步先确认实际内存分配，再完成RamBlock种子与挂载接入；持久UFS写入仍禁用。
证据见evidence/storage/data-seed-preparation。

## 当前里程碑：launchd已到达main（2026-11-02 14:51）

机主照片显示 `launchd main marker=1 err=0`，BOOT870a11da（raw50cd2ef8）。
这是原sysctl_handle_int返回后，读取真实kern.initproc_spawned=1得到的证据；
XNU只允许PID1首次设置它，并明确标为launchd到达main。探针不写/伪造该状态。
当前有意停在诊断panic；不要当作正常系统崩溃，也不要说桌面已可用。

此前06a968f7已实测dyld shared map kr=0；24d8643b实测postmap sc=6 err=0，
证明完整缓存系统调用536成功后，用户态继续并完成close。分别保存原图与镜像绑定。
新的入口空白诊断仅改普通已核验panic内核副本，原源e4632618和正常0b04a782均保留。
本次main停点free=0x104页约1MiB，256MiB owned窗口仍很紧；服务阶段与内存运行状态
需继续取证，不能擅自把DTS保留洞改为RAM。可写Data尚未配置，软件显示/输入及桌面待适配。

本轮按机主要求以中文commit收束功能修复与实机证据，不继续刷入探针。
提交检查：24项针对测试、4组实际源码/生命周期检查通过，结构化记录13区通过。
check-platform仍因旧五组件selection快照与既有VirtioMmioBlock选择不一致而失败；
保存commit-check-platform.log，不删断言或冒称通过，本轮未改DTS。
现有DTBO为已恢复原机备份，TWRP保留。最新证据索引：policy-memory/README.md。
下列定位步骤保留历史顺序；有当时pending字样的回执须连同后续device-result读取。

## 最新：共享缓存映射函数已返回，待直接读取返回码

机主确认dbe8ca9d约35秒后复位。这证明vm_shared_region_map_file已返回（此前setup返回0），
但不包含kern_return_t，不能据此说缓存映射成功或launchd main执行。
新的06a968f7只修改已验证正常panic内核0b04a782的空入口padding116字节与该调用点，
保留原callee及参数，返回后将W0显式零扩展、写到Darwin变参栈槽，调用现有panic渲染器。
预期屏幕 `diagnostic: dyld shared map kr=<实际值>`，有意终止，不再按时间复位。
0为该次调用KERN_SUCCESS，非零按原XNU返回枚举调查；即使0也不证明后续用户态启动。
源内核e4632618和正常副本均保持；实际指令、Darwin参数ABI、改动范围及打包检查通过。
必须使用原未插桩源推导MMU/entry地址，正常副本的SCTLR序列已被早期标记替换。
最新回执见policy-memory/shared-map-result；设备观测待回报。

当前处于首用户进程启动调试：已确认root/SystemOS、正式init exec返回0、BSD入口、
共享缓存映射函数返回。尚待映射成功码、dyld继续执行、launchd main与服务启动证据。
到可交互桌面还需可写Data、软件显示及输入等独立工作；无法按未知bug数量估计时间。

## 最新：用户态已到BSD系统调用入口（2026-11-02 14:07）

无复位73a5738b机主照片停留旧彩条，没有新panic文本，不能据图定位MMU。
随后bb452d74探针在_unix_syscall的_get_bsdthread_info调用返回后复位；
机主确认约6秒重启，证实用户态SVC已到BSD入口，不记录PID/系统调用号，
尚不证明具体handler完成、共享缓存映射或launchd main。
原图及结果见policy-memory/release-normal，正检查点见first-unix-syscall。

下一镜像dbe8ca9d使用同一e4632618源与release参数，恢复原exec/Unix入口，
只在__shared_region_map_and_slide的vm_shared_region_map_file返回后6秒复位。
源码setup必须先返回0才会调用此点；后续正信号仍不包含映射函数返回码。
镜像、独立FAT调用/FD校验与上传回执见policy-memory/shared-map-return，观测待回报。
6秒不是从开机计时；前置缓存读取、哈希等可能耗时，无复位不能单独当卡死。

## 最新：正式launchd exec返回零，恢复无复位运行（2026-11-02）

机主确认7ac0a4ba（launchdsuffix=release，直接/sbin/launchd）粉条后6秒复位，
即原___mac_execve本次返回W0=0。不能证明launchd main或dyld缓存映射；
源码还说明某些越过不可返回点的激活失败可能返回0，需观察继续运行的结果。

准备并上传无终止探针BOOT73a5738b（raw2dfe0789），在原正常12766f5f payload副本中
只追加launchdsuffix=release；正常内核0b04a782、ADT和trust-cache均逐字节/摘要保持，
exec调用恢复原BL97fffc98，保留正常panic画面，无人为6/16秒复位。
原始e4632618源内核及board默认不变，DTBO保持恢复的原机版本，根卷与载体保持已核验值。
上传回执和最终状态见 `evidence/storage/policy-memory/release-normal/`；机主观测待回报。

## 当前exec定位（2026-11-02）

TWRP完整读回发现Heimdall上传全分区后BOOT仍有旧footer，实际对照未生效；
随后通过TWRP直接写646f44ad并完整读回，证明17bda459前缀不变、尾部全零。
机主手动System仍停三星页；只读vbmeta与原备份一致flags3，bootloader版本仍T970ZCU2CVK1，
但DTBO不同。已保留当前DTBO be754ac7，恢复原机备份49bcf93a（Heimdall exit0）。
其后机主确认出现粉条、约6秒复位：第一次init exec调用已返回，不等于成功。
完整证据见bootloader-audit-20261102；DTBO恢复后尚未单独读回，不把具体差异宣称为唯一原因。

新增受源内核e4632618哈希限制的exec-return-status探针，直接调用原callee后立即检查W0：
零6秒／非零16秒。Unicorn执行实汇编覆盖0、2、12、13和全1返回值、原参数不变与无内存写入；
未知源拒绝，3项测试通过。BOOT201d98d2已刷入，机主确认16秒复位，即首个候选exec返回非零。
重要：DEVELOPMENT默认先尝试/usr/appleinternal/sbin/launchd.development，原始卷没有这个文件；
探针截断了正常回退，因此不能认定正式/sbin/launchd失败或精确errno。
同一探针已显式--kernel-arg launchdsuffix=release直达/sbin/launchd；
BOOT分区镜像7ac0a4ba（raw前缀dfdb220a），完整FAT内核与上一版逐字节相同，
独立校验配置只有该额外参数，board默认不变。上传回执见policy-memory/release-exec-status，观测待回报。

## 当前BOOT尾部对照（2026-11-02 13:41）

机主确认恢复后仍停三星/RPMB页，未按键；主机ADB无设备、Heimdall可检测Download。
此前BOOT全分区读回尾64字节仍有旧AVBf，指向56438784偏移、2112字节metadata，
该位置现为零而非AVB0。原Android备份同footer指向有效AVB0。尾部共14个非零字节。
这是包装候选原因，不能称实机已证实；备份vbmeta flags3也不是当前vbmeta实测。
制作完整71303168字节BOOT646f44ad：17bda459全部62713856字节不变，余8589312字节补零。
仅刷BOOT，上传100%报告成功，但session-end确认失败exit1，未确认重启与读回。
下一步机主手动正常重启（黑屏立即松开电源/音量下），记录是否进入UniXNU。
若仍不进入，用现有TWRP读回完整BOOT，核对尾部，并只读比较当前vbmeta/DTBO与备份。
不继续改XNU补丁，不重写已核验根卷/载体。证据：policy-memory/boot-tail-control。

## 当前交付：完整恢复后已重启（2026-11-02 13:37）

根镜像9382658048字节已写入并完整读回匹配fd43ee70；两份固定corrected策略载体
均先备份、写入、sync/flush并完整读回匹配8fefc15f／869a186a。
BOOT17bda459的62713856字节也已通过TWRP写入、刷新并全部读回一致。
13:37:16+08已adb reboot，当前观测待机主回报。此BOOT是exec返回后6秒复位探针。
TWRP保留在RECOVERY。未重分区、未创建可写Data，不得再次格式化USERDATA。
实机当前根内容以 `evidence/storage/root-restore-twrp-20261102/` 的新完整回执为准。
下列“正在恢复”和“只读待核对”文字保留为本轮历史步骤，现已完成。

## USERDATA删除后恢复（2026-11-02）

机主进入TWRP后要求刷入镜像，又明确说之前删除了UserData。
只读核对：设备BOOT前62713856字节精确匹配c544bae1，RECOVERY全部86888448字节
精确匹配TWRP b5c722e7，补足此前session-end失败的写入验证。
但SHNGROOT头已变、OS/SystemOS两个关键块均为零；以前的完整根读回不能继续代表现状。
已正常卸载/sdcard和/data，TWRP root/分区几何/无挂载检查通过；
正在用原完整raw源fd43ee70恢复9382658048字节并完整读回。
后续必须核对/恢复两个固定corrected载体，再写BOOT17bda459并核对读回。
TWRP模型是SAMSUNG_gts7xlwifi；检查器只额外接受它与精确product=gts7xlwifi组合，
不放宽root、sda36、243668070400字节、4096扇区与无挂载要求；回归检查通过。
当前结果以 `evidence/storage/root-restore-twrp-20261102/` 为准，未完成前不重启。
根内容删除与三星bootloader屏幕是不同证据，不将前者直接当成后者原因。

## TWRP刷写（2026-11-02 13:23）

机主提供 `out/minsos/twrp_gts7xlwifi.tar` 并明确要求直接刷写。
已核对唯一regular成员recovery.img、header2、gts7xlwifi属性及86888448字节容量，
只向RECOVERY上传TWRP `b5c722e7…`，保留旧备份 `out/device-backup/recovery.img`。
Heimdall上传100%且报告RECOVERY upload successful，但session-end确认失败，exit1；
不把它记作完整成功，不自动重刷。使用--no-reboot，下一步机主按键进入Recovery，
ADB可用后先验证RECOVERY及BOOT实际字节。本轮未写BOOT或USERDATA。
详细回执见 `evidence/storage/twrp-install-20261102/flash.json`。

## 当前会话（2026-11-02 下午）

机主已要求继续。T733固定提交审阅见 [内核方案对照](t733-kernel-comparison.md)。
exec返回后6秒探针 BOOT `17bda459…` 上传成功，但机主报告没有进入预期启动，
随后回到Download，没有本轮exec结果。已重新上传昨晚的精确对照 `c544bae1…`，
13:19照片为三星标志和bootloader信息，主机仍检测Download接口；未看到本轮UniXNU。
没有证据把这次现象归因于exec，亦不能把RPMB fuse Set一行当作校验失败。
两版FD、固件DTB、BootShim和命令行一致，载体不变，本轮未写USERDATA。
机主有现成TWRP并询问切换，已请其进入并保持只读；下一步通过root ADB读取
BOOT实际字节、核对镜像前缀SHA256，排除上传/启动选择问题，再恢复exec定位。
照片含DID，只留ignored输出；公开文字与回执在policy-memory对应子目录。

## 最新实机状态（2026-11-02）

只读载体复用版 BOOT `12766f5f…`（源内核 `e4632618…`）实机停留色条，
机主重启复测超过3分钟无变化；色条会残留，不能定位为MMU卡死。
隔离的共享分支 `vr_open` 返回后6秒复位探针 BOOT `ef97eb6a…` 已刷入，
机主报告粉条后约10秒自动重启，确认该调用至少一次返回。
它不记录返回码，不能证明验签成功、两个设备均已准备或launchd开始执行。

下一张 BOOT `c544bae1…` 已于00:21:47刷入成功：在
`_load_init_program_at_path` 的 `___mac_execve` 调用前立即复位。
这版不执行该调用，没有额外6秒等待；机主确认立刻重启，已到达exec调用边界。
尚未证明exec成功、完整缓存映射或launchd主程序执行。机主要求今天停止、明天继续；
当前BOOT仍是会自动重启的诊断镜像。下一轮从exec内部进展定位开始，勿重复判定为早期MMU卡死。
精确镜像、指令独立校验、上传回执和观测均在 `evidence/storage/policy-memory/`。
正常镜像与源内核保留，board.toml没有复位探针；本次只写BOOT。

## 最新：正确策略已部署，进入内存压力定位

BOOT097c4f8c＋正确策略的机主画面变为
`memorystatus_jetsam_thread: no victim! available pages:3060`；free=0x760。
这不是此前initproc缓存读取EACCES画面，但不能据此单独证明完整缓存映射或launchd主程序。
照片及精确镜像／策略绑定见 `evidence/storage/policy-memory/device-097c4f8c.json`。

源码确认原载体73293824字节一直保留，块设备又各自复制对应哈希表，额外73293824字节。
本轮让块设备借用精确匹配的、驱动已分配并验签的载体，把载体设为只读，
仍为每个设备单独复制／保护公钥页并在保护后重新vr_open；其他来源保留复制路径。
设备销毁不释放全局借用载体，只释放私有公钥页；自有复制仍按原路径释放。
实际configure/free源码的ASan/UBSan＋mprotect主机检查覆盖借用、回退及保护／验签／分配失败。
内存panic追加pin/borrow/copy及native4k读量／blob数，borrow是别名字节，不是额外分配。
不扩大256MiB EFI owned窗口，不改DTS或物理内存归属。构建和实机结果另记。

## 当前根因与修复准备：旧 sparse 被签进了新 owner 策略

最新独立主机全表比较发现，旧策略与已部署 raw 根镜像不匹配。
平板完整根镜像 fd43ee70… 已读回通过；策略却继续使用早先已知有 seek 错误的旧 sparse。
SystemOS 首个错误策略块为43008，错误 sparse／策略在此对应 SHNGROOT 头；
raw根镜像与原始SystemOS在此一致。主机APFS映射显示，机主 .03 偏移34MiB处的
1MiB读取覆盖该块，与 stage171 的拒绝吻合。

修复了签名器 SHA 字段偏移80→56及缺失的全窗口摘要比较，优先使用完整 raw 根镜像。
旧 sparse 会拒绝；新策略通过 RSA 与真实C验证器全量 OS1483785／SystemOS806400块。
5项生成和5项写入中止／备份／读回测试通过。新策略及固定载体修复计划在
`evidence/storage/policy-carrier-repair/`。机主授权后已完成临时Recovery启动、
两份旧包络备份、固定载体更新及精确长度整段读回。新鲜设备关键块与正确策略一致、
与旧策略不符；更新后这些根数据块未变。全部命令成功，已返回XNU BOOT097c4f8c。

读取来源诊断候选内核88f716b0／BOOT097c4f8c完成主机构建和打包，但未刷写；
发现输入根因后暂停该候选测试。修复需临时Recovery BOOT取得root ADB，先备份并核对
旧包络，再仅更新 USERDATA LBA5505024／5516624 两段签名载体，并整段读回。
现有 OS/SystemOS 数据镜像无需重写。BOOT6b04878c的最后设备结果仍是读取拒绝。

## 最新：6b04878c 定位到 native4k 的实际读取失败

机主照片显示 `csig EACCES stage=171 off=2200000`，CDHash 正确匹配主机 `.03`。
这意味着 AMFI 和前置签名设置已经通过，EACCES 来自文件偏移34MiB处的真实 vn_rdwr。
证据见 `evidence/storage/ufs-cache-read-source/device-6b04878c.json`。

下一版区分 vn_rdwr 内部 MAC 读取检查（201）和文件系统 VNOP_READ 错误（202），
并显示真实 UFS owner-integrity 失败计数及首个拒绝块的 index／物理LBA／长度／
预期和实际 SHA256 前8字节。hash位0=预期索引有效，位1=诊断SHA计算成功。
不重读、不重试放行，原来块校验失败仍返回 NotPrivileged；只对同一已拒绝 bounce
快照多算一次哈希。9项现有状态测试和实际诊断 helper 的 ASan/UBSan 检查通过。
新的构建／打包／刷写及设备结果分别记录，不从读取EACCES直接断言存储损坏。

## 最新：dd007d58 已定位到 .03 的签名添加 EACCES

机主照片显示 `init cache syscalls=18`，可见的最近 12 条中：
`.02` 的 openat 与 `F_ADDFILESIGS_RETURN(97)` 均成功；`.03` 的 openat 成功返回 fd4，
随后 `fcntl(fd4,97)` 返回 EACCES(13)。最终仍是 dyld namespace 6/code 1。
照片、关键行与原始镜像关联见 `evidence/storage/ufs-cache-signature/device-dd007d58.json`。
未显示的早期 6 条不能推断，不能笼统宣称全程没有共享映射调用。

只读检查原始主机文件：主缓存及 `.01`～`.04` 的全部 CodeDirectory 签名页匹配，
各 CDHash 都在原始 System trust module；`.03` 为
`55b4a307efbf08234c98c81f09f1d17e5efc0d0a`，6958 个 16KiB 签名页无不匹配。
检查对象是主机原件，不等于设备运行时数据或签名策略已验证。

下一版只加签名流水线边界观测：首个 PID1 EACCES 的阶段、文件偏移、内核已有的
CodeDirectory 哈希；原有验证和错误行为不变。阶段 1=读取签名，2=blob_add 兜底，
10=初始化，11=首次重组，12=MAC/AMFI，13=二次重组，14=多级哈希，15=辅助签名，
16=entitlements，17=原始 16KiB 到 4KiB 准备，171=该准备中的实际文件读取。
主机 helper 检查 PID／错误过滤、首失败锁存、偏移／哈希编码与空哈希通过；
下一版构建、刷写和实机结果另记，尚未选择放宽验证或更改原始文件的方案。

## 当前：dc42838f 挂载 ENOENT，按 T733／umi 恢复启动布局

本节更新前一轮关于“空目录挂载点”的判断，保留旧镜像与证据。
机主启动照片关联 BOOT `dc42838f…`／kernel `8262854b…`：
`mount=2 stage=3 auth=0 mstatus=2 sys=2 cryptex=2 preboot=2`。
SystemOS 媒体探测仍为已命名、已授权，挂载调用返回 ENOENT，尚未进入 dyld。

只读检查原始 OS：`System/Cryptexes/OS` 与 `App` 是符号链接，分别指向
`../../private/preboot/Cryptexes/OS`／`App`；`private/preboot` 为空。
所以前一版直接挂到 OS 链接会遇到缺失的目标目录，不是“dyld 的唯一真实缓存路径”。

按机主要求核对 T733（`3bb0d6f…`）和 SM8250 umi（`3eb7257…`）：
两者初始启动均启用只读 SystemOS root union、cache startup、boot manifest 和
4K 签名哈希缓存。共享 `zzyb-native-cryptex-os-view.patch` 在可写 Data 就绪后建立
规范 cryptex 路径视图；本设备目前未准备该 Data，不能照搬后期目录。
本轮恢复 root union，诊断按实际配置检查 `/System/Library/Caches/com.apple.dyld/`，
不因尚未建立的 cryptex 别名而中止。

同时移植 T733 的 `native-union-root-reference.patch`：本机 XNU 的
`set_rootvnode` 让 kernproc cwd 借用 rootvnode 引用，而 `checkdirs_callback` 又释放一次。
对实际 XNU 函数的主机计数测试复现旧代码引用错误，补丁后五种 cwd/rdir 场景通过。
这是独立的正确性修复，当前设备照片没有证明发生过此类 panic。
详细路径与固定源码链接见 `evidence/storage/ufs-union-reference/`。
新内核 `1d83105e…`、BOOT `49f3b166…` 完成构建／编译分支／引用计数及打包检查；
22:35 仅刷 BOOT，Heimdall exit 0 并请求重启。机主照片确认挂载／`/System` 缓存
vnode 探测已过，真实 dyld 仍报 namespace 6/code 1 的 libSystem 缺失、no dyld cache，
carrier acc/rej 均为 0。union 同卷可能不调用 carrier；尚不能定位打开、签名或映射失败。
下一版加入有界 syscall 结果观测和内核已复制的 namei 路径记录，不读额外用户指针。
只观察 PID1 的 open/openat、fcntl、shared-region 返回码，保留 24 条、退出时显示
最近 12 条；路径是最近的内核复制记录，不是完整的线程因果跟踪。不会改变错误或策略。
格式 `sc<调用号> e<errno> r<十六进制返回值> a<fd/计数> c<fcntl命令> <路径>`；
92/406 为 fcntl，463/464 为 openat，536 为共享映射。下一版哈希／回执另存
`evidence/storage/ufs-cache-syscalls/`。内核 `170cc979…`、BOOT `dd007d58…`
已通过 helper／稳定输入构建／链接与 FAT/FD/容量检查；22:47 仅刷 BOOT，
Heimdall exit 0 并请求重启，等待机主的真实 syscall 跟踪照片。

## 接手 dsh：cryptex 路径与构建配置（2026-11-01）

机主提供 BOOT `a41b5c11…`／kernel `d66b832b…` 的启动照片，显示
`mount=0 stage=6 auth=1 mstatus=0 sys=0 cryptex=2 preboot=2`。
镜像关联按机主报告记录；照片本身没有镜像哈希，未做设备读回。
证据见 `evidence/storage/ufs-cryptex-resume/device-a41b5c11.json`。

主机保存的内核哈希确为 `d66b832b…`，但当时 `.config` 及 `kern_exec.c`
编译记录仍为 `OWNER_UNION_SYSTEMOS=1`：只修改 defconfig 没有更新已解析配置，
所以新 `/System/Cryptexes/OS` 挂载分支没有生效。另外三路径探测会无条件 panic，
成功挂载也不能启动 launchd；本照片不证明 dyld 已查找或映射缓存。

本轮显式设 `CONFIG_XNU_OWNER_UNION_SYSTEMOS=n` 并重新运行 defconfig，保留上一轮
内核、源码与编译参数于忽略目录 `out/step7/cryptex-resume-baseline/`。
挂载点、`DYLD_SHARED_CACHE_DIR` 和 carrier 目录继续使用
`/System/Cryptexes/OS/System/Library/Caches/com.apple.dyld` 对应布局。
诊断仅在挂载失败或 cryptex 缓存探测失败时 panic；成功则继续启动 launchd。
新 BOOT 为 `dc42838f…`（内核 `8262854b…`），实际 clang 参数重放预处理、
FAT／FD／容量检查通过；DT/ADT 和适配记录检查通过。`check-platform.py` 因历史
五组件断言未通过，详见新证据 README。镜像位于
`out/step7/probes/ufs-cryptex-resume/boot.img`。机主授权后于 22:23 仅刷 BOOT，
Heimdall 上传及重启命令成功（exit 0），回执见新证据 `flash.json`／`flash.log`；
缓存映射和 launchd 进展待机主启动照片。

## 关键发现：UFS 已经通了

survey 镜像（`c404ce26…`）的 7 个样本全部匹配、14 次读零错误，靠的不是新建 SMMU 上下文，而是
**复用固件留下的 handoff 状态**：

- SMMU CB0：`cbar=0x100ff`、`cba2r=0x1`、`sctlr=0xe0`；
- 固件已配好的 stream：SID `0x0e0` / `0x4e0`，slot 55/56（`smr=800004e0` 等）；
- DMA 缓冲分配在 DarwinBoot owned window 内（preflight 强制）。

之前所有失败都在“驱动自己建 SMR/CB”这条路上。**下一步只剩发布**：用这套已验证的
gHost（smmu/CB0/streams/DMA）走 `NativeUfsWholeUserdataBlock`/`NativeUfsBlock`，把
userdata 的 OS 窗口发布成 IOMedia（UUID 匹配 ADT 的 `04769D26…`），让 APFS 挂根。

## 发布路径已跑通到 owner 策略（BOOT `ca021c28`）

实机结果（`evidence/storage/ufs-publish/device-ca021c28.json`）：

```
T970 UFS publish: publication stopped
stage=policy count invalid phase=1 window=0 bytes=16a408600
windows=2 prepared=0 published=0 policies=0 verify=ffffffff
w0 OS off=100000 size=16a408600
w1 SystemOS off=16a600000 size=c4e00000
```

handoff 准入、调查版 NOP、正式 manifest/GPT 读取、窗口计划全部通过，停在空策略表；一个窗口
也没发布（prepared=0 published=0）。窗口几何与 host 侧从镜像首块解出的 SHNGROOT manifest
逐字节一致：

- OS：`0x100000`，6,077,580,800 字节（1,483,785 块，哈希表 47,481,120）
- SystemOS：`0x16a600000`，3,303,014,400 字节（806,400 块，哈希表 25,804,800）
- 合计哈希表 73,285,920 字节，加两份 manifest 约 73.3 MB → **不能进内核**（BOOT 68 MiB）

**策略载体已实现（主机侧 + 内核侧）**：`scripts/build-owner-root-manifests.py` 从 sparse 段流式
签名两个窗口（OS 11,593 块 / 47,481,664 字节，SystemOS 6,301 块 / 25,805,344 字节），并用真实 C
验签通过；内核 `installOwnerPolicyCarrier` 从 LBA 5,505,024 / 5,516,624 读入、`vr_open` 校验后填
策略表。下一步是把两份包络写进 userdata 并刷发布镜像。

**下一步**：manifest 放到 userdata 镜像之后的固定区（镜像止于 LBA 5,260,288，LBA 5,505,024
起留 18,000 块），启动时用同一 handoff 通道读入、用编译进内核的 owner 公钥做 RSA 校验，再填
`verified_root_policies`；每块读取仍按策略校验。

## 发布路径已接上固件 handoff（`t970-ufs-publish=1`）

- 新增 `hostBringUpHandoff`，`hostBringUp` 在发布模式下直接走它：只映射 controller/SMMU、
  在 owned window 内取 DMA，然后复用调查版的 NOP/上电/TUR 序列；**不写** SMMU、不写队列、不写存储。
- 只要求 `CB0` 仍是活动翻译（`CBAR0=0x100ff`、`CBA2R0=1`、`SCTLR0=0xe0`）、`GFSR=0`、
  DMA 落在 owned window 内；其余 SMMU 状态只记录。
- 第一版把调查版 `healthy()` 的快照当成前提，实机 BOOT `3b0d7d73` 直接否定：
  `0x954/0x958` 读 0（那些 SID `0xe0`/`0x4e0` 的 park 项是调查自己的 NOP 测试写的），
  `CB0 FSR=0x400` 是内核之前就有的旧记录。现在改成**故障漂移**判定：进入时抓
  `GFSR`/`CB0 FSR` 基线，NOP／上电／TUR 后必须不变。
- 接上正式 `startRoot`：读 manifest → 建窗口计划 → `NativeUfsBlock`(owner 校验) → 发布。
  仍然 fail-closed：任一窗口不通过就一个也不发布。
- 发布中止的 panic 会打印 `stage`、窗口数、`prepared/published/policies/verify` 和
  `w0..w3` 的窗口名/偏移/字节数；bring-up 被拒绝时打印 CB0 三元组与两个 stream 值。
- 第一版 `t970-ufs-publish=1`（BOOT `11a1d635`）实机停在 magenta 条、无 panic 文本：
  handoff 路径没接管请求列表，控制器仍按固件的 UTRLBA 取描述符，敲门铃即死。已补
  `hostStopQueue`/`hostStartQueue`（只跳过 SMMU 那一半）。调查版没踩到是因为
  `t970_nop::run` 自己停/起过队列。
- 内核侧仍挂空策略表（`verified_root_policy_count=0`），所以本版预期停在 `policy count invalid`。
  这不是回退：策略哈希表若要塞进内核，OS 6.08 GB 约 46.4 MB + SystemOS 3.30 GB 约 25.2 MB，
  合计约 71.6 MB，BOOT 上限只有 71,303,168 字节。**策略载体必须移出内核**：
  计划把两份 manifest 放到 userdata 固定区（镜像之后），启动时经同一 handoff 通道读入并在
  运行时填充 `verified_root_policies`，仍用编译进内核的 owner 公钥做 RSA 校验。
  详见 [根设备发布](ufs-publish.md)。

## 当前：完整根镜像已重写并通过整段读回，XNU交叉核验BOOT已启动

- 机主要求“你能直接刷么”，已授权继续完成当前完整根镜像部署；仍先验证通道。
- OdinMac本机也封装Heimdall，不作为独立大文件通道。准备官方Recovery派生的BOOT临时镜像，
  不改原Recovery；见 [ADB通道](adb-rescue.md)。Recovery菜单服务禁用，不含自动写盘命令。
- 20项测试通过；BOOT42,930,176字节，SHA256
  `e67fe744d4ee9e2be7a0ab906d47a064b7409cc1a4db4c7eecaacaae9519a721`。
  原内核gzip往返及全部ramdisk条目检查通过；三星目标gzip／USB路径尚未实测。
- 临时BOOT已上传并自动重启，Heimdall exit0；ADB recovery模式可用，uid0、SM-T970。
  sda36容量243668070400、逻辑块4096、运行时设备号259:42，data／metadata未挂载；Recovery菜单程序未运行。
- 原RECOVERY已备份到忽略路径out/device-backup/recovery.img，86,888,448字节，SHA256
  `3b6df60e4aff4506b8a3f0e20111d1b5fb4053ee82170a5132999ac590ac28cb`，未改Recovery分区。
- Linux清理块缓存后manifest仍读回全零，与XNU诊断一致。自带dd的direct模式EINVAL，
  改用sync+成功BLKFLSBUF再按确切字节数读取，已资格验证4096字节数据通道。
- 准备scripts/write-root-image-adb.py连续写完整fd43ee70…镜像，再清理块缓存并读回完整长度SHA256。
  已按机主指令执行本次USERDATA写入：write exit0、sync及BLKFLSBUF成功，read exit0。
- 9,382,658,048字节全部读回，SHA256精确匹配源镜像
  `fd43ee7035ce185ce4215ac93fdc006fd784a54b3b7442e21457c226cbe03093`。
  回执／日志在 `evidence/storage/root-rewrite/`。仅重写镜像长度，未改分区表／Recovery。
- 已通过ADB回Download Mode，重新上传已审阅的c404ce26…UFS survey BOOT并自动重启，Heimdall exit0。
  准备／回执在 `evidence/storage/root-rewrite/post-survey/`；机主在外，待返回后屏幕确认7样本全部匹配。
  当前设备不再运行Linux ADB，不能把没有ADB设备当作失败。
  根设备发布／文件系统挂载仍未启用。
- 原厂BOOT和UFS调查BOOT均保留；当前运行临时Linux root ADB。

## 前轮：根镜像调查完成（传输一致，部署内容不完整）

- 参数仍为 `t970-ufs-image=1`，新标题 `T970 UFS root image survey`；见 [调查解释](ufs-survey.md)。
- 7个原样本各读2次；预期哈希不符继续记录实际摘要，传输错误或重复不一致立即停。
  输出matchMask/repeatMask/zeroMask，不把completed当作样本匹配。
- 18项测试、配置检查、内核构建及预链接通过，输入稳定；内核
  `3e657c8fc7f385a287715e3ee516b3001d32d6bf1ec42d52cc13206ec92f1839`。本轮尚未刷写，继续使用FD `515105d7…`。
- 代码提交 `09bff63`，独立封装与DT/ADT检查通过；BOOT
  `c404ce262b69cb7bc0af22dc5da866506c7c3faf3cdfc824971f2b311d46b2b4`，62,713,856字节。
- 已检测Download Mode后仅上传BOOT，Heimdall exit0，`--no-reboot`；等待机主画面及三个mask。
  未重新生成旧稀疏成品，未写USERDATA。回执／实测在 `evidence/storage/ufs-survey/`。
- 照片确认completed1、matched0、reads14、healthy1、poisoned0；matchMask60、repeatMask7f、zeroMask5f。
  7样本两次完全一致；manifest、OS首中尾、SystemOS首尾均零。SystemOS中部128KiB与源文件精确匹配；
  SystemOS尾部源样本本就为零，所以matchMask还包含bit6，不能算作第二个非零匹配。
- 所有传输／SCSI／协议错误为0，GFSR0、FSR400。当前根镜像内容不完整，不能启用挂载。
  编码错误及未验证的分段DONT_CARE保留行为须解决；不凭这些结果继续改SMMU。
- 下一步准备完整镜像写入后读回校验的部署方式；没有新的USERDATA写入授权时仅准备与检查。

### 根镜像修复准备（未写入）

- 机主确认只有三星原厂Recovery。root ADB环境暂未可用；只读检查脚本已准备，
  从运行时sysfs取得sda36 major:minor来检查挂载，不假定Linux设备号。
- 官方LineageOS gts7xlwifi 20261029 recovery已下载并核对SHA256
  `2f5bbdfccba07af0524d3695f00977d3fcfc2eac994a7491e15cd15462f4bbd8`，
  86,888,448字节符合RECOVERY分区，但超过BOOT；未刷入任何分区。不可直接作为BOOT使用。
- 机主随后询问Odin及具体镜像，已切换为准备单个完整USERDATA包：
  `out/step7/odin-userdata/sm-t970-userdata-root.tar.md5`，唯一成员userdata.img.lz4。
  7,100,088,380字节，LZ4完整解压和tar唯一成员hash核验通过，包SHA256
  `99f4dc685297e6c12b054ce5529f66ccf86cd6f4f64f6894ba802767740b2c4d`。
  19项主机测试通过；不使用旧三段sparse，没有执行新的USERDATA写入。
  准备证据在 `evidence/storage/deployment-preparation/`。
- Odin截图ID:COM空，Whisky USB支持未验证。需要真正识别设备；上传后还必须读回验证。

## 前轮：根镜像样本核对（manifest读回全零，继续只读调查）

- 参数 `t970-ufs-image=1`；见 [样本范围](ufs-image.md)。复用NOP和GPT前提，
  对manifest及OS/SystemOS各3个128KiB样本分别读2次，对照源镜像SHA256。
- 17项主机测试、精确源镜像／7样本常量核验、配置检查、内核构建通过，输入稳定；内核
  `2d35ad10fa101cd03108f97fd106e6855bac7a16234d823102fe394969664875`。仍使用FD `515105d7…`。
- 代码提交 `0c20e6d`；独立封装与DT/ADT核验通过，BOOT
  `c92ee8831053d8aa13a5ce8022fa9632cd6f8b6d3ad10b83ad8c4aff6092d80c`，62,713,856字节。
- 已检测Download Mode并仅上传BOOT，Heimdall exit0，`--no-reboot`。当前安装本轮镜像，
  机主照片确认success0、sample0=manifest、reads1、healthy1、poisoned0，GPT通过。
- observedSHA=ad7facb2…，恰为4096字节零块；预期manifest为bc908a6c…。
  SCSI/OCS/protocol/residual均0，GFSR0／FSR400。其余样本尚未尝试，不能归因于UFS故障。
- 旧归档seg0保存了失败尝试；本地找到flash-seg0b.log成功重试，已补充审计，不能断言第0段从未成功。
- 编码器已确认错误：后两段首个RAW块在跳过DONT_CARE后没有seek，错误复制源offset0。
  修复仅影响以后生成；原稀疏文件保持不变。分段刷写DONT_CARE是否保留旧内容也未实测。
  见 `evidence/storage/userdata-write-audit/audit.json`。未再次写USERDATA。
- 回执／实测在 `evidence/storage/ufs-image/`。下一轮读取所有样本及重复值，内容不符继续记录，传输错误停止。

## 前轮：LUN0只读数据核验（实机通过，继续根镜像读回）

- 参数 `t970-ufs-read=1`；见 [只读数据范围](ufs-read.md)。先用已通过NOP入口建立实验队列。
- INQUIRY、READ CAPACITY、重复GPT头及最多4块分区项，核验CRC和本机userdata边界。
  不访问userdata内容，不写存储。最多一次已完成UNIT ATTENTION重试，超时／协议错误不重试。
- 16项主机测试、配置检查、内核构建／预链接通过，输入哈希稳定；内核
  `3956c0e72d9682024623e477555f804e469df767052e16f03a1864ab2c4b5bc5`。仍使用FD `515105d7…`。
- 代码提交 `fa9a0e6`；独立封装与DT/ADT检查通过。BOOT
  `e6c49073395655a947d3f53b31206e268a14cccea895ff18201cc96fd3a577aa`，62,713,856字节。
- 检测Download Mode后仅刷BOOT，Heimdall exit0，`--no-reboot`；当前安装只读LUN0镜像。
  机主已提供完整结束画面，回执与观察在 `evidence/storage/ufs-read/`。
- stage6、commands5、UA0、healthy1、poisoned0。INQUIRY／capacity／header／repeat／entries／geometry全为1。
  lastLba=62458879、blockBytes4096、GPT count40、headerCRC=e5897a71、entriesCRC=a60c0f35，
  userdata=2969600..62458874。result/OCS/SCSI/sense/protocol/residual均0，GFSR0、FSR400。
- 已证明小规模SCSI数据及GPT读盘；尚未读取userdata内容，未发布根卷或挂载文件系统。

### 后续根镜像接入核查（主机结果）

- 本地userdata-root.img全文件SHA256仍为 `fd43ee70…`，与原USERDATA回执一致；
  SHNGROOT v1 manifest摘要通过。设备内容仍待读回，不据主机镜像断言写入完整。
- OS首块物理LUN0 LBA2969856、SystemOS首块LBA4453888；后续先比较manifest及
  两窗口首块hash，计划留在忽略目录 `out/step7/ufs-read-next-plan.json`。
- `startRoot`／`startWholeUserdataRoot`仍调用旧hostBringUp，不能在T970原样启用。
  实验路径的成功尚未迁移到持久驱动／映射生命周期。
- `NativeUfsBlock::configureVerification`明确拒绝policy_count=0，RootPublication还要求
  signedVolumeUuid；当前空策略仅使诊断链接，不意味着根窗口能发布。
  68MiB BOOT限制下的验证策略接入仍需解决，不能直接启用root参数绕过检查。

## 前轮：单次 UFS NOP（实机往返通过，尚未读盘）

- 参数 `t970-ufs-nop=1`；范围与阶段见 [单次NOP](ufs-nop.md)。
- 自有连续 DMA、实际 boot_args 范围核验，空 transfer/task 队列停用，两个精确 SID
  候选安装到槽55/56、CB0保持原配置；保护显示CB4，CB73不动。
- 仅尝试一次 NOP OUT/IN，复用已测试生产命令／200ms轮询。不发Query/SCSI，
  不改PHY／时钟，不读取分区。故障／超时不取消、不重试、不回收DMA、不回滚路由。
- 15项主机测试、配置检查、内核编译／链接／预链接通过，构建输入稳定；内核 SHA256
  `3a0881f9595ae54efae62b2884e311d1aee0934208d239fd93a385facf6303be`。仍使用 FD `515105d7…`。
- 代码提交 `3f47470`；独立封装核验及DT/ADT检查通过；BOOT
  `fb2be3f41f04fc4d89131818223a9f223245cd1273c17dfa3868ece17bc0b20b`，62,713,856字节。
- 检测Download Mode后仅刷BOOT，Heimdall exit0 / BOOT upload successful，`--no-reboot`。
  当前安装单次NOP镜像，机主已提供完整结束画面。
- 实测stage=6、submitted/success/protected=1、poisoned=0；result=0、OCS=0、
  response=20000001、protocol=0、polls=2。DMA=c47cd000、bytes=22000、ownedOK=1。
- HCE=1、HCS=10f、两类doorbell=0、IS=400、RSR=1；GFSR=0，CB0 FSR前后均400。
  两条候选映射已读回，显示槽及CB0保持预期，CB73未改。缓冲／路由保留到重启。
- 这证明一次NOP命令及响应的DMA往返；两SID同时安装，不能据此判断各自是否都使用。
  尚未测试SCSI数据、LUN容量、块读取或长期稳定性。下一步有界识别LUN及数据输入验证。
- 准备／上传／实测完整记录位于 `evidence/storage/ufs-nop/`。

## 前轮：UFS 零命令预检（实机通过，未执行 DMA）

- 参数 `t970-ufs-preflight=1`；见 [预检范围](ufs-preflight.md)。
- 读取实际 ARM64 boot_args physBase/memSize，分配连续 0x22000 字节缓冲并检查归属；
  不采用 DTS DRAM 包络。不写 MMIO，不切队列／stream／context，不提交 UFS 命令。
- 读取候选 CB0，要求保持已观测原配置、没有有效 NS stream 引用；保护显示 CB4，排除 CB73。
  e0/4e0 仍只是残留字段候选，预检通过不等于资源独占、DMA 或读盘通过。
- 14 项主机测试、配置检查及内核编译／预链接通过，构建输入稳定；内核 SHA256
  `af32f5a5f221fe01b94d404cc37861b024c09903e012b4b76031da737aeb9ece`。继续使用 FD `515105d7…`。
- 代码提交 `c0c13db`；独立 FAT／内核／参数／FD 核验及 DT/ADT 检查通过。
- BOOT `2eebaa44e3661f1370324d099a13324c63996eaca026242140d467de054ebf73`，
  62,713,856 字节，已检测 Download Mode 后仅刷 BOOT，Heimdall exit 0，`--no-reboot`。
- 机主照片确认 END、ownedOK=1、planOK=1。ownedBase=c007c000、ownedBytes=10000000，
  dma=c47d2000，bytes/contiguous=22000；缓冲完整落在实际交接范围内。
- CB0=100ff/1/e0，FSR=400；HC=1、HCE=1、HCS=10f、两类 doorbell=0。
  本轮没有 MMIO 写入或 DMA，不能将预检结果当成 NOP／读盘成功。
- 下一步准备有界命令传输，保护显示 CB4、保持候选 context 原配置，超时保留 DMA 缓冲。
  准备／上传／观察记录位于 `evidence/storage/ufs-preflight/`。

## 前轮：合并 SMMU 字段核查（实机写回及恢复通过）

- 上轮 ID 字段接受／恢复已通过；新参数 `t970-smmu-fields=1`，预期标题
  `T970 SMMU fields (no UFS commands)`，范围见 [合并核查](smmu-fields.md)。
- 复用 ID 守卫；VALID 只在 FAULT 和默认未匹配 fault 策略下测试；S2CR 仅在 SMR=0
  时测试及恢复，必要时尝试有界的 Qualcomm FAULT 恢复方式。全程不开放 DMA 路由。
- 成功恢复后只读 CB0/1/2/3/4/73 状态；不写 context、不改显示映射、不启动队列／命令。
- 13 项主机测试通过，内核 `53e9e68c0d64a73f12ddc7ccb2a316dc1661120fe6f114d975cff7b80c27e197`
  编译、链接、预链接通过，输入哈希稳定。继续使用 FD `515105d7…`。
- 代码提交 `7ee2918`，BOOT `cfbd84ba34fc03b50661b46c9e22fe59c43ba651bca6967da49f1df1ec373e75`，
  62,713,856 字节，独立封装和 DT/ADT 检查通过。2026-11-01 17:00（Asia/Shanghai）
  仅刷 BOOT，Heimdall exit 0，`--no-reboot`。机主已提供完整结束画面。
- 实测 stage4，ID/VALID/S2CR accepted 均为1；VALID=800000a5，S2CR=0，
  直接恢复200ff成功，fallbackUsed=0。allRestored/mappingsUnchanged=1，GFSR=0。
- CB0..3：CBAR=100ff、CBA2R=1、SCTLR=e0、FSR=400；显示CB4：CBAR=1f000，
  其余三项相同。CB73：CBAR/CBA2R=0、SCTLR=3ab3a706、FSR=0。
  CB73不可仅凭M=0当空闲bank；CB0..4已有配置，且FSR无操作前基线，不能归因于本次测试。
- 下一步核对独占 bypass context 的命令/DMA测试方案；保留显示CB4、排除未确认CB73，
  不再把本轮字段写回成功当作实际读盘通过。

## 前轮：单个无效 SMR 的 ID 字段测试（实机通过）

- 参数 `t970-smr-id-test=1`；范围见 [单槽测试](smr-id-test.md)。这是带两个临时 SMR
  字段写入的测试，不是只读快照。只写槽 56 的无效 ID 字段为 a5，再恢复零；
  不置 VALID、不改 S2CR／CB／队列，不提交 DMA。
- 固定核对当前 ID／几何、空队列、显示槽与目标槽；写前再检查全表，写后恢复并核对
  全部匹配状态。stage<5 表示拒绝，stage=5 后仍须检查恢复和保护字段。
- 内核 `d455be28e526ef9b6276e4347901d2551012e2c86632b3a30f2952cb19455431`
  编译、链接、预链接通过，输入稳定。12 项主机测试通过，含 18 个保护／恢复场景。
- 代码提交 `41d99e6`，继续使用 FD `515105d7…`。BOOT
  `ee45890ab4875987b0e3376b095a64a5d58f1b23177c96b9ea4a996cd8ba9031`，
  62,713,856 字节，独立封装核验、DT/ADT 检查通过。
- 2026-11-01 16:41（Asia/Shanghai），仅刷 BOOT，Heimdall exit 0，`--no-reboot`。
  机主照片确认 stage=5、observed=a5、restored=0，idAccepted/restoreOK/mappingsUnchanged 均为 1，
  GFSR 前后为零，S2CR 保持 200ff，显示槽仍为 84020820/4。
- 本次只证明无效 SMR 的 ID 字段可写且恢复检查通过，不能再笼统说 SMMU 整体只读。
  VALID、S2CR、context 和 DMA 尚未验证；下一轮合并核查剩余字段，保持显示映射不变。

## 上一轮：SM8250 只读交接快照（实机观察已完成）

- 参数为 `t970-ufs-handoff=1`，预期标题 `T970 UFS handoff RO (no writes)`。
- 修正内核时钟诊断表，删除 SM8550 独立 mem-PHY GDSC 读取；UEFI 原型保持原样且不执行。
- 显示完整、有界的原始 SMR/S2CR 表及正确的 SM8250 GCC 状态；只有 GDSC/AXI/AHB
  通过保守前提检查才只读 HCI／队列。未采样的 HCI 默认零值需结合 HCstate 解读。
- 内核 `147f8d3bc6b8c35990a83f304f5eab1b3654d69ba5b9a1ef1747a5d31602f34a`
  编译、链接、预链接通过，构建期间输入哈希不变。11 项主机测试通过，包括最大表格排版。
- 代码提交 `58bdac8`，仍使用 FD `515105d7…`。成品 BOOT
  `933a5d776edb2500be5c268b93e64f2cfec53fee6e12cebbb39869a8d7050deb`，
  62,713,856 字节，独立 FAT／参数／FD 核验和 DT/ADT 检查通过。
- 2026-11-01 16:24（Asia/Shanghai），检测 Download Mode 后仅刷 BOOT，
  Heimdall exit 0 / `BOOT upload successful`，`--no-reboot`；机主已给出完整画面。
  `evidence/storage/handoff-readonly/` 保存准备与回执，不得沿用旧快照的实机结论。
- 实机读数：GCC 检查通过、HCstate=1，HCE=1、HCS=0x10f、IS=0x400；
  UTRLBA=0x9b296000，两类队列 RSR=1、doorbell=0，END slots=87。
- 唯一有效槽 04：SMR=0x84020820、S2CR=4，与原厂显示 iommus SID 0x820／mask 0x402 对应；
  保留此槽与 CB4。02/03 的 0x4e0／0xe0 仅为无效字段，不能直接当作活动 UFS 路由。
- 本轮原始照片在对话可见，但本机给定路径不存在；已记录可见转录，照片文件哈希留空。
- 下一步拟核查单个无效 SMR 的 ID 字段写入并恢复，保持 VALID=0、S2CR 不变；
  目前尚未执行任何这样的写入，不把已有 HCI ready 状态当作 DMA／根卷通过。
- 范围、格式及复现：[交接快照](ufs-handoff.md)。本轮不进行 UFS 命令、DMA 或 USERDATA 写入。

## 当前接手核查（从 47b113f 继续）

- 当前任务是 UFS／SMMU，而非下面早期控制台定位的历史阶段；根卷挂载失败见
  `evidence/bring-up/runtime/pmgr-bridge/device-result.json`。
- 接手时 `board.toml`、`NativeUfs.cpp`、`SmmuTakeover.h` 有未提交改动，
  已原样保存在 `.cache/handoff-ufs-resume/`。机主确认这组实验尚未刷入。
- 接手的逐槽 SMR 写入探测已撤出新路径；旧参数被拒绝。bank 递增候选从
  ID1.NUMS2CB 的边界开始，不假定 bank 1 可用；该接管算法仍没有实机 DMA 通过证据。
- 本轮 `t970-smmu-report=1` 只读 SMMUv2 原始 ID／控制寄存器与有限候选匹配，
  主动 panic 显示后停止，不进入控制器和根卷路径。候选 SID 不是板级路由确认。
- 旧证据不能证明 SMMU 已永久被 TZ 锁定，也不能证明 SCM 所有路线不可用。
  尤其 SCM 结果标记发生在两个调用之后，不能由一个红块推出第二个调用没返回。
- 本轮固件复用精确哈希 `515105d7…` 的已测试 CPU0/initrd FD，不执行后来的 UFS PHY／SCM 原型。
  原型源码仍保留。复现与原始寄存器定义见 [只读核查](smmu-readonly.md)。
- USERDATA 已有 OS/SystemOS 实验镜像；本轮不再次写入。旧 BOOT 备份只恢复 BOOT，
  不代表恢复 Android 用户数据。最近实际刷入的镜像需以刷写回执和机主反馈为准。
- 以下各节保留不同阶段的交接历史；涉及“无路可走／安全世界掌管”等判断，
  以上述证据边界及新只读测量为准。

## 本轮已准备、刷写并确认只读诊断

- 代码提交：`23d54b9`。9 项主机测试通过，其中 SMMU 模型包含 11 个场景；
  配置检查、CPU0 DT/ADT 与 30 个静态保留区检查通过。
- 源内核 `cca9bbb8…`；加入色条与 panic 显示后的 payload 内核 `c89b24fd…`。
  成品 BOOT `7f729c2a6ee8ee11b6eb5d4ff7ec23171b261854151578e36737d866a62391e2`，
  62,713,856 字节。FAT 中内核及参数、BOOT 中 FD 均已独立提取核验。
- 2026-11-01 15:55（Asia/Shanghai），检测到 Download Mode 后，用本机补丁版 Heimdall
  仅刷 BOOT，exit 0 / `BOOT upload successful`，`--no-reboot`；未再次写 USERDATA。
- 机主已确认标题并提供 `IMG_20261101_155738.jpg`：sCR0=`002d0406`，
  ID0=`4c017e57`，ID1=`6000004a`，ID2=`00005111`，GFSR=0；扫描 87 组，
  74 个 CB，三个候选均未匹配。`0xffffffff` 是无匹配哨兵，不是实际槽号。
  只读路径成立，UFS、DMA 或根卷仍未通过。
- 准备记录、完整哈希、平台检查和刷写回执：`evidence/storage/readonly-smmu/`。
  未通过首次参数核对的打包产物留在忽略目录，未刷写；最终工具固定使用已审阅参数，
  不接受本机默认参数对诊断行的覆盖。

## 公开参考核查与后续方向

- 应机主要求核查 T733 与 SM8250 设备。T733 维护者有大量成功请求记录，
  同时源码保留早期 DMA 复位诊断；umi 报告根卷与 Hello 已运行，采用专门的双 stream 规划。
  这些是对方维护者记录，不是 T970 验证。
- T733 有公开配套固件 fork，不能继续沿用下方历史段落中的“固件不公开”判断。
  它接入厂商 Clock／HALIOMMU／SCM／UFS 依赖；本轮 T970 FD 的交接前提不同。
- 本地 `GccUfs.h` 仍含 SM8550 时钟诊断偏移；三星 `gcc-kona.c`、Linux 与 umi
  共同给出 SM8250 的 AXI=`0x77010`、AHB=`0x77018` 等参考。
  `BoardInit.c` 的旧宏也错位，但当前已经跳过 GCC 写入；不能据此宣称确定复位根因。
- 下一步先审阅并修正 SM8250 诊断输入，再一次采集有界 stream 表和受前提保护的
  电源／HCI／队列状态。不要直接套用 T733 的 `0x80` 或 umi 的双 SID。
- 精确来源与差异：[UFS 参考对照](ufs-reference-comparison.md)。本轮观察后未再刷写。

## 接手后的更新

- 本轮机主确认：最后的 `initialize_screen` 探针一直停留，没有复位。
  已核对代码：它是 **reset-before，立即复位**，不是等待 6 秒；因此不能据此认定
  `initialize_screen` 内部卡住。机主反馈与镜像哈希见
  `evidence/bring-up/runtime/handoff-observation.json`。
- SEC 补丁已在 `ac1ca14` 接入准备工具；固定补丁和四个文件的前／后像哈希，
  干净源码应用、重复执行及保留未知修改的检查均通过，不再依赖缓存的手工修改。
- 重置探针从默认 `board.toml` 移出，用 `scripts/build-entry-probe.py` 隔离生成。
  本项后续调用边界和状态结果属于旧内核 `4131d5b1…`，不能直接套到修复版。
  机主已确认 `idle_thread_create`、`sched_startup` 返回后探针均自动复位；
  `PE_init_iokit` 返回后探针（`9b0f8f68…`）仍停在色条，没有自动复位。
  每轮完整镜像哈希、刷写回执与观察见 `evidence/bring-up/runtime/`。
  `PE_init_iokit` 调用前探针（`458218bd…`）已由机主确认自动复位：
  未通过的路径缩到该调用内部。其内部 `InitIOKit` 调用前探针（`977fd90d…`）
  未复位，第一个调用 `PE_init_printf(TRUE)` 返回后探针（`f89deffa…`）也未复位。
  该二进制中它尾调用 `vcattach`；`vcattach` 中首个无条件调用
  `arm_usimple_lock_init` 返回后探针（`95ff2c91…`）已复位，确认进入并通过锁初始化。
  `vcattach` 内 `gc_enable` 返回后探针（`a914135d…`）未复位，调用前探针
  （`59dc0bb6…`）已复位，范围缩到 `gc_enable` 调用内部。
  `--console-state` 镜像（`670e78ee…`）由机主报告约 4 秒后复位，
  支持 `gc_initialized` 低位为 0、`PE_putc` 为 NULL，详见该轮 `device-result.json`。
  源码显示跳过 `PE_create_console` 也会跳过屏幕回调初始化；这可能影响后续 `gc_enable`，
  已有上述状态时序证据，但仍未确认具体失败指令。
  尚不确定具体失败指令或故障类型，也没有运行时加密 provider 失败证据。
- [相近设备案例](related-bring-up.md)记录了 Surface Duo 2 同阶段的加密 provider 问题，
  以及 SM8250 小米 10 至尊版的验证边界。均不是 T970 根因的证据。
- 修复准备：以 `t970-console-bootstrap.patch` 替换旧绕过补丁，恢复控制台建立，
  并在其前先调用 `PE_init_printf(FALSE)`。旧内核保存在本机忽略目录
  `out/step7/baseline-console-skip/`；新内核 `bfb50a1a…` 已编译、链接、预链接通过，
  最终机器码确认先装输出回调再无条件建立控制台。修复版 `PE_init_printf(TRUE)` 返回后
  镜像（`f759eb80…`）仍未复位。照片中的 UEFI 菜单、DarwinBoot 交接句及固件文字
  是保留像素，没有确认新的 XNU 文本输出；不能断定新内核仍停在旧卡点。
  旧状态探针固定到原内核哈希，更换内核后拒绝运行是预期行为。
- 已用 `--guard-early-faults` 检查更早的 `arm_init` 中 `PE_create_console` 返回：
  正常 6 秒，同步异常／SError／panic／BRK 分别 20／30／40／50 秒后请求复位。
  机主报告 `e18c6ca0…` 60 秒后仍未复位，既未确认正常检查点，也未确认异常分类路径。
  主机测试和活动向量选择核对通过；设备 BRK 正控制尚未完成，不复位仍有多种可能。
- 下一轮加 `--brk-control`：在 `0xfffffff0073f3370`（MMU 开启后、C 初始化前）
  用 `BRK #0` 替换已检查的 `mov x0, #0x300000`。预期约 50 秒后复位，
  控制台建立调用不修改、不执行；先验证诊断通道，再解释负结果。
- BOOT 最近刷入的是 `after-mmu-brk-control` 正控制镜像（`150ed5ff…`），机主确认约 50 秒复位；正控制成立，诊断通道可用。
  原始 BOOT 恢复待完成，后续镜像以 `evidence/bring-up/runtime/*/flash.json` 回执为准。
- 以下为 ds 交接当时的状态、命令和待办，保留作历史基线；当前进展以本节及适配记录为准。

## no-SMMU 实验

保持 SMMU 映射但不写寄存器（`t970-ufs-no-smmu=1`）可以越过 SMMU 相关 panic，但随后停在
magenta 条并自动复位、无控制台输出；与驱动里无超时的 UFS 完成等待一致，即**固件的 stream
映射不覆盖我们的 DMA 缓冲**。内核侧绕过 SMMU 不足以让 UFS 工作。

## SMMU 归属的结论

Linux `arm-smmu.h` 证实 IDR 在 `0x20/0x24/0x28`（原驱动偏移正确）。恢复该模型并扫描全部 128 个 slot 后：

- 固件的 128 条 stream 里没有一条符合“bypass + 单引用 + AArch64”的复用条件；
- 新建 bypass context 的 SMR 写入仍读回 0。

两者合起来说明 **secure world（ABL/TZ）掌握着 stream 寄存器**，非安全世界只能读 IDR。内核侧无法自行配置 SMMU；需要固件为 UFS 留下 bypass stream（alioth/T733 的固件正是这么做的）。

## SMMU 模型的最终判断

- `GFSR`（0x24）写入无效 → SMMU 寄存器**被锁**，不能新建 bypass context；
- 改用 vendored 驱动（IDR `0x0/0x4/0x8`）+ 自动复用所有 exact stream，仍在
  `IDR0 bit30` 的 AArch64 检查失败（`SM8550/alioth 模型 ≠ SM8250 apps_smmu`）；
- 结论：需要**针对 SM8250 的 SMMU 实现**（参考 Linux `arm-smmu-qcom`/SMMU-500 规范，
  重写 SmmuTakeover 的寄存器模型），或让固件按 SM8250 的方式预先配好 UFS stream。

## 下一步的根因（固件不给 UFS 上电）

- 固件 `gts7xlwifi.dsc` 仍写着 `no UFS driver yet. Excluded for bring-up`；
- alioth `ShengUfs` 的 `hostBringUp` 只做控制器映射，**不初始化 PHY/时钟/SMMU**，假设固件已完成；
- T970 上 SMMU 的 SMR 写入不生效（读回 0），IDR 读数在两次启动间变化，说明 **apps_smmu 未被固件上电/配置**；
- 已在 `package/ShengUfs/` 保留 vendor 副本（IDR 偏移改为 0x0/0x4/0x8）和 `zz-build-shengufs-local.py`，但默认 archive 仍只用 `component:ShengUfs`。
- 结论：要过 UFS，需要**固件侧 UFS/PHY/SMMU 上电**（T733 的固件做了这件事，但仓库不公开），或在驱动里补齐 T970 的 PHY/时钟/SMMU 初始化。

## SMMU 诊断（本轮）

`t970-smmu-dump` 在 `arm_init` 末尾转储 apps_smmu：IDR0 `0x002d0405`，固件共配置 **26 个 stream**，
没有 `0x0060`。驱动随后规划 **bank 73 / slot 86** 并写 SMR，写后读回 0（`act=0`）。
这更像 **SMMU 未开时钟/未上电或被 TZ 锁定**，而不是单纯少了 stream id。
下一步：在驱动里先使能 apps_smmu 的 GCC GDSC/时钟，或改用固件已配置的 stream（需从 26 条中确认 UFS 的那条）。

## UFS 进展（userdata 已写入）

- **userdata 已完整写入**：`scripts/encode-userdata-sparse.py` 把 8.7 GiB 镜像切成三段 sparse，
  用 DONT_CARE 跳过非本段内容，每段 <4 GiB，Heimdall 三次 `USERDATA upload successful`。
- 内核 `a981a22d…`（alioth ShengUfs + 空策略 VerifiedRoot，19 KB）能链接、能启动，单 stream
  `0x60` 时在 `NativeUfs.cpp:455` panic：`SMR write off=958 exp=80000060 act=0`，
  即 SMMU 的 stream 写入不生效（固件 SID 不同或 SMMU 被锁）。
- 下一步：确定 ABL 为 T970 配置的 UFS stream id（或确认 SMMU 只能由固件预配），
  再决定改 `native-ufs-stream` 还是做板级 SMMU/ICE 配置。

## UFS 的硬约束（本轮结论）

- 已生成 T970 的 `userdata-root.img`（OS `e5634d04…` @0x100000、SystemOS `b4908cde…` @0x16a600000，
  共 9,382,658,048 字节），并把 `[userdata]` 几何与根卷 UUID 写进 `board.toml`。
- verified-root 路线**装不下**：OS+SystemOS 的块哈希表约 47 MiB 嵌进内核后，`kernel.macho` 为
  125,374,464 字节，实测打包镜像 **138,211,328 字节**，而 BOOT 分区只有 **71,303,168 字节（68 MiB）**。
- 因此 `CONFIG_XNU_NATIVE_UFS` 与 `CONFIG_XNU_VERIFIED_ROOT_PROBE` 保持关闭；下一步需要
  **T970 板级 UFS 发布路径**：复用 alioth 驱动，但不嵌入 verified-root 哈希表，改为直接发布
  userdata 分区/根窗口，适配 68 MiB 启动分区。

## UFS 移植现状（已准备，未启用）

- 已把 `feeds.toml` 的 `ShengUfs` 指向 `FFT-infra/NativeUfs-alioth@ab54059`（SM8250、device-verified），
  驱动源码可编译；`scripts/build-storage-bindings.py` + `scripts/data/native-storage-original-bindings.S`
  解决 `IOBlockStorageDevice`/`IOMedia` 原始符号。
- 完整链接还缺 **VerifiedRoot `vr_*`**：`build-verified-root-probe.py` 需要 OS 卷验证产物
  （`build/verified-root-os/verification.json`），不只是 IPSW。
- 运行还需要 `findRootLayout` 接受的 **sheng userdata manifest**；T970 是 Android GPT，没有该布局。
- 因此 `board.toml` 的组件/archives、`sm-t970_defconfig` 的 `CONFIG_XNU_NATIVE_UFS` 都保持原样
  （可构建状态），接入内容作为后续工作保存。

## 启动链完成（最新）

PMGR 占位（`ShengPlatformPower.cpp` + `build-platform-power.py`，`CONFIG_XNU_SHENG_PMGR=y`、
`sheng-pmgr=2`）编译并通过 ABI 审计后，内核 `d4914c03…` 的实测结果为：

```
Failed to mount root device @IOKitBSDInit.cpp:984
frames fffffff007a13d5c fffffff007925b50 fffffff0076b1d58 fffffff00798d588 fffffff0073f34a4
```

即 **UEFI → 菜单 → DarwinBoot → arm_init → 引导线程 → bsd_init → AMFI/PMGR → IOKit 根卷挂载**
全部走通；失败原因是没有 UFS 驱动。下一步是第 6 步的存储移植（见 `docs/storage.md`），
不再属于启动链问题。设备 BOOT 仍是诊断镜像，原始 BOOT 待恢复。

## AMFI/PMGR 关卡

`bsd_init` 之后的真实失败（内核 `80cc00ad…`，镜像 `041fcf8c…`）：

```
"AMFI: No PMGR?\n" @ConfigurationSettings.cpp:235
```

即未修改的 AMFI 需要 **ApplePMGR provider**。参考 marble-milacy：用板级
`ShengPlatformPower.cpp`（`build-platform-power.py` 生成受保护的 ApplePMGR 占位 nub，
`CONFIG_XNU_SHENG_PMGR=y` + `sheng-pmgr=2`）即可越过；它依赖同一个 21H461
kernelcache（`f18b4df8…`），ABI 地址可复用。此前的“控制台卡死”实际是
`gc_enable` 对未初始化 ticket lock 的 panic（`gc_initialize` 被跳过），已修复。

## 最新里程碑（本轮）

`PE_init_printf(TRUE)` 内部就是 `vcattach()`，跳过 `initialize_screen` 挡不住。新增
`t970-skip-vcattach.patch`，在 `t970-novc` 下把 `PE_putc` 换成丢弃输出的空回调：

- 内核 `d862c992…`：`PE_init_iokit` 返回后探针 `f32a04c0…` 约 6 秒复位（旧内核
  `4131d5b1…` 的同点探针 `9b0f8f68…` 是不复位的）。
- 同一内核：`bsd_init` 调用前探针 `fa16c47d…` **立刻复位**。

结论：**UEFI→菜单→DarwinBoot→arm_init→引导线程→bsd_init 已全部走通**；
`vcattach`/`gc_enable` 自旋是控制台问题，已用诊断旁路绕过（不是正式修复）。
下一关是 `bsd_init` 内的根卷挂载：没有 UFS 驱动，预期 panic 或静默停住。
设备当前 BOOT 是诊断镜像，原始 BOOT 仍待恢复。

## 总体现状

- 第 1–5 步已完成并提交；第 6 步只完成存储（UFS）输入采集与实现判定，驱动未移植；
  第 7 步主机侧构建链全部打通，设备侧已从「UEFI 无法启动」推进到「内核已交接、
  卡在早期控制台/引导线程」。
- 设备现在**可以被刷写**：Heimdall 1.4.2 有握手 bug，已用 PR #478 补丁自建 CLI
  （`.cache/heimdall/build/bin/heimdall`）。SM-T970 没有 fastboot，只能刷 `boot` 分区。
- 恢复镜像：`out/step7/odin/boot-stock.tar`（当前 Magisk 25.2 boot dump）。
  测试镜像：`out/step7/odin/boot-unixnu.tar`（会按下面的构建步骤重新生成）。

## 已确认的设备进展（按时间顺序）

1. 初始固件在 XBL→UEFI 阶段断言：`TzDxe` 内 `QseeComDxe.c` TEE 初始化失败。
   已在 DSC/`Include/DXE.inc`/`Include/APRIORI.inc` 中禁用 `TzDxe`。
2. 下一个断言：`PILDxe`/`PILProxyDxe` 无 UFS 时读分区失败（`usfpil.cfg`）。
   已同样禁用这两个模块。之后进入 **UniXNU 菜单**。
3. 菜单无输入设备（FD 里没有 SimpleTextIn 生产者；`ButtonsDxe` 只发 Qualcomm 按键协议），
   3 秒倒计时自动启动默认项。
4. `UniXNURamDiskDxe` 最初找不到 initrd：上游 Mu-Silicium 的 SEC **没有保存 x0（ABT 传入的
   DTB 指针）**。已给 SEC 打补丁（见 `package/firmware/patches/0001-sec-entry-arg-hob.patch`），
   把 x0 存进 `gSecEntryArg0` 并以 `gSiliciumEntryArgHobGuid` HOB 发布。
   打上后菜单出现 4 项（xnu/Restart/Power off/Tools），payload FAT 正常挂载。
5. DarwinBoot 交接成功（`DARWINBOOT: hand-off to the kernel`，绿条），但内核在开 MMU 前卡住。
   - 蓝条=内核入口（MMU off），粉条=开 MMU 前。
   - 探针 stage 3（`entry_probe_reset_delay=6`）确认 **MMU 成功打开**（6 秒后 PSCI 复位）。
6. 逐点探针（reset after/before）确认以下函数都返回：
   `_arm_vm_init`、`_serial_init`、第一条 `_kprintf`。
7. 用 reset-before 探针定位到 `PE_create_console` **之前**（该调用在 arm_init 尾部），
   随后尝试重置到内核里进一步定位；`PE_create_console` 内 `ml_io_map_wcomb` 返回，
   之后的 `printf` 探针无法区分「未执行/内部卡住」。
8. 为绕过控制台，加了板级内核补丁 `patches/xnu/t970-skip-early-console.patch`：
   默认不调用 `PE_create_console()`/`PE_init_printf()`，只有 boot-arg `t970-console` 才建。
   重建内核后仍然只有三条阶段条、无 panic。
9. 继续在 `_kernel_bootstrap_thread` 内二分：确认到达 `_idle_thread_create`，
   `_bsd_init` **未到达**。
10. 刚刷入的探针是 `_initialize_screen` **之前**（`entry_probe_reset_after="_initialize_screen"`），
    **结果尚未确认**。注意：`initialize_screen` 在引导线程里还会再初始化一次视频控制台，
    与早先的 `PE_create_console` 属同一类路径，是最可疑的卡点。

## 未提交改动（重要）

设备仓库：

- `board.toml`：payload `size_mib=56`（boot 分区 68 MiB）、`panic_screen` 已按需开关、
  当前残留探针配置 `entry_probe_reset_*`（指向 `_initialize_screen`）。
- `dts/sm-t970.dts`：memory 改为低地址包络 `0x80000000+0x80000000`（T733 做法），
  以覆盖 DarwinBoot 实际分配的 `0xC0000000` 窗口。旧的高地址 `0x200000000` 版本不可用。
- `package/firmware/.../gts7xlwifi.dsc`、`Include/DXE.inc`、`Include/APRIORI.inc`：
  禁用 `TzDxe`、`PILDxe`、`PILProxyDxe`。
- `patches/xnu/series` + `patches/xnu/t970-skip-early-console.patch`：跳过早期 Apple 控制台。
- `package/firmware/patches/0001-sec-entry-arg-hob.patch`：SEC x0 HOB 补丁（**尚未接入
  `scripts/prepare-uefi.py`**，目前只存在于 Mu checkout 工作区里）。

Mu-Silicium checkout（`.cache/uefi-source/Mu-Silicium`，勿依赖其工作区状态）：

- 4 个文件被手改：`Silicon/Silicium/SiliciumPkg/Sec/{Sec.c,Sec.inf,AArch64/ModuleEntryPoint.S}`
  和 `SiliciumPkg.dec`。`package/firmware/patches/0001-sec-entry-arg-hob.patch` 是其 diff。
- 重新准备 checkout 后**必须重新应用**该补丁，否则 payload 卷不会挂载。

本机未提交文件：

- `../UniXNU/unixnu.local.toml`：device/uefi/dtb/ipsw/kernelcache/trust_cache/unique_chip_id，
  trust cache 指向 `build/original-static-system-trust/original-static-system.bundle`。
- `../ipsw/iPad_Pro_HFR_17.7.11_21H461_Restore.ipsw`（6.4 GB，仓库外）。
- `.cache/heimdall/`（带 reset 补丁的 Heimdall 源码与二进制）、`.cache/heimdall-plain/`。
- `out/`（kernel/payload/boot.img/odin tar/备份）。

## 构建与刷写命令（可复制）

```sh
# 1. 把 overlay 和 SEC 补丁送进 Mu checkout
python3.14 scripts/prepare-uefi.py --uefi .cache/uefi-source/Mu-Silicium --extract-dir .cache/stock-inputs/extracted

# 2. 固件（需要 LLVM/lld 在 PATH）
PATH=/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH \
python3.14 ../UniXNU/unixnu build firmware -D . \
  --uefi .cache/uefi-source/Mu-Silicium \
  --edk2 .cache/uefi-source/Mu-Silicium/Mu_Basecore \
  --local-module refer:edk2=.cache/uefi-source/Mu-Silicium/Mu_Basecore

# 3. 内核（归档脚本要 python3 带 tomllib；设备仓库里建了 .cache/bin/python3 -> python3.14）
PATH=$PWD/.cache/bin:/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH \
python3.14 ../UniXNU/unixnu build kernel -D .

# 4. payload（trust cache / seed 在 unixnu.local.toml）
PATH=$PWD/.cache/bin:$PATH python3.14 ../UniXNU/unixnu build payload -D .

# 5. 启动镜像（boot 分区上限 71303168 字节；当前镜像 62713856）
PATH=/opt/homebrew/opt/llvm/bin:/opt/homebrew/opt/lld/bin:$PATH \
python3.14 ../UniXNU/unixnu bootimg -D . --uefi .cache/uefi-source/Mu-Silicium \
  --fd .cache/uefi-source/Mu-Silicium/Build/gts7xlwifiPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd \
  --dtb out/firmware-inputs/firmware.dtb \
  --ramdisk ../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/payload/payload.img \
  --output out/step7/boot.img

# 6. 刷写（设备先进 Download Mode：关机后 Vol Down+Power 插 USB，警告后 Vol Up）
.cache/heimdall/build/bin/heimdall flash --BOOT out/step7/boot.img --no-reboot

# 7. 测试后刷回原状
.cache/heimdall/build/bin/heimdall flash --BOOT out/device-backup/boot.img --no-reboot
```

Odin tar 打包（备用）：`tar -cf boot.tar boot.img`，用 OdinMac 1.1.5 的 AP 槽位。

## 关键文件

- 内核镜像：`../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/kernel/kernel.macho`
- payload：`.../payload/payload.img`（56 MiB，含 kernel/ADT/trustcache）
- 固件 FD：`.cache/uefi-source/Mu-Silicium/Build/gts7xlwifiPkg/DEBUG_CLANGPDB/FV/SILICIUM_UEFI.fd`
- 固件 DTB：`out/firmware-inputs/firmware.dtb`（采集自 `/sys/firmware/fdt`）
- 设备备份：`out/device-backup/{boot,dtbo,vbmeta}.img`（boot sha256 `6f49af2f…`）

## 诊断工具

- 探针：`[payload] entry_probe_reset_delay = 6` + `entry_probe_reset_after/_in/_before`
  生成内核入口色条与定时复位；每次改探针要重建 payload + bootimg 再刷。
- panic 屏：`panic_screen = true`（需要 Mu 的 `FrameBufferSerialPortLib/Font.h`）；与探针
  同时开启会占满 kernel 尾部 padding，二选一。
- 已禁用的调试路径：`TzDxe`/PIL 是固件；`PE_create_console` 跳过是内核补丁。

## 待确认 / 下一步

1. **先确认刚刷的 `initialize_screen` 探针结果**（会/不会重启）。若到达，卡点在
   `vm_commpage_init`/`mac_policy_initmach`/`bsd_init` 之间；若不到达，卡在
   `PE_init_iokit`/`kernel_startup_initialize_upto` 或更早。
2. 控制台是目前最强嫌疑：T733 移植用自绘 framebuffer 控制台（`native-console-debug-output`）
   替代 Apple vc。建议给内核加一个极简的“屏幕 kprintf”（复用 panic 屏的绘制方式），
   或移植 T733 的早期入口/console 补丁，否则永远看不到内核日志。
3. 一旦越过控制台，预期下一个失败是根卷（没有 UFS 驱动），那时回到第 6 步的 UFS 移植，
   参考 umi/alioth 的 NativeUfs fork（双 stream `0x0e0`/`0x4e0`、固件状态接管）。
4. 把 SEC x0 HOB 补丁接入 `prepare-uefi.py`（应用 + 校验），否则干净 checkout 无法复现。
5. 清理 `board.toml` 的探针残留，并提交上面所有未提交改动（含 `docs/handoff.md` 本身），
   更新 `porting.toml` 对应 area 的 findings/evidence。
6. 设备当前 boot 分区被测试镜像占用；交付前刷回 `out/device-backup/boot.img`。

## 参考

- T733（同为三星平板，SM7325）：<https://github.com/RigoLigoRLC/unixnu-sm-t733>
  - `dts/board.dts` 低地址 memory 包络 + `owned_memory_size="auto"`；
  - `patches/t733-xnu/early-entry/*` 早期入口/MMU/framebuffer 映射与阶段标记；
  - `native-console-debug-output.patch` 自绘控制台。
- UniXNU 文档：`porting/uefi-firmware`、`porting/ufs`、`guide/debugging#green-bar`。
