# BackBoard bundle 加载 150 秒对照

v32 的 125 秒机主照片显示 timer start1/arm0/notify0、3 次帧退役。backboardd 栈与 v31 同在 Objective-C bundle 加载路径。原始主程序的符合栈形态的调用候选是 BackBoard.axbundle 的 NSBundle load，主程序 slide 未实测。v33 延后采样 25 秒，用 BB/SB 栈和帧计数观察这一阶段是否仍可见。独立启动的时序会变化。

执行 `python3.14 evidence/display/bundle-late-v33/prepare.py`，以已核对的 v32 BOOT 仅替换 `t970-runtime-report=125` 为 `t970-runtime-report=150`。最终 FAT 回读确认内核、ADT、trust cache 和 Data 种子相同，固件及 payload 外部字节相同。仍为主动终止报告。输出 `out/data-bringup/bundle-late-v33/boot-partition.img`，完整摘要见 `preparation.json`。

BOOT `2a6e95a22aa95421a9e34d84b20f06c763d355165b748d577245ecab06111ead` 已仅刷写 BOOT，Heimdall 退出码 0 并请求重启。设备读回和屏幕结果待采，见 `upload.json`、`flash.log`。

补核原始 SystemOS 与 UUID 匹配的 Cryptex cache。bundle 的 Info.plist 指向 BackBoard，cache 镜像表含完整路径的 BackBoard 映像。只查 SystemOS 独立文件无法判断映像缺失。更早的 v24 也曾采到 NSBundle 内的 Objective-C 类枚举，主程序帧低位同样为 b44，对应同一调用候选。见 `cache-bundle-audit.json`。
原始主程序的 chained rebase 显示加载函数是 `dispatch_once` block 的 invoke，v24 帧链也含 `dispatch_once_callout`。这进一步支持调用点归属，尚缺实机独立主程序 slide。

## 实机观察

机主反馈紫条后约两分钟出现 Apple logo。诊断页可见不到 0.5 秒，随后被 logo 替代，来不及读计数或线程栈。logo 目测略扁。见 `device-result.json`。本轮无法用 150 秒报告判定 BB 是否越过 bundle 加载。

当前 panic-screen 补丁在常规 XNU panic 协调前直接接管入口。绘屏只屏蔽本核中断并最终 park 本核，其他核心上的 GOP 复制仍可能写同一块 framebuffer。显示覆盖符合这条路径，具体写入者和是否发生复位未采到。下一版先让终止报告独占板级 GOP 写入，等待正在进行的复制结束，再绘屏，并记录能否取得独占。启动耗时需要另采 launchd、显示发布和首次成功复制的时间。板级 GOP 配置为原生 2800×1752，CPU 路径按行搬像素，logo 比例需通过原始帧与正面实拍对照。
