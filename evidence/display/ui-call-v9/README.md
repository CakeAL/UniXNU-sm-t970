# UI spawn系统调用返回与参考实现审阅

原有工作区已构建并上传v9，`flash.log`记录BOOT upload successful与重启请求，
但没有上传命令或设备读回。`preparation.json`对应最后准备的45531047镜像。
本轮用户照片包含v9独有的ui-call-return字段，因此按该准备/上传顺序关联；
屏幕不含镜像摘要，不能声称已从设备独立验证镜像哈希。

照片确认target60、main1、69进程、cpu8/sec7、SB27、BB0，display stage8/mapped1/published1。
SB匹配spawn返回1/e0，BB0/e-1，path-copy-errors0；两者job-lookups均0/e-1。
所有显示client、swap、transfer、copy、retire与vsync计数为0。
该画面是配置的60秒终止报告，不是由这些字段证明的意外崩溃。

`job-input-audit.json`记录只读原版plist及签名缓存内容；两者都有backboardd，
ProgramArguments为`/usr/libexec/backboardd`且RunAtLoad/KeepAlive为true。
这只排除了主机原始输入缺项，不证明实机导入、策略或依赖等待。

命令与结果：

- `python3.14 -m unittest discover -s tests -p test_ui_spawn_calls.py -v`：通过，ASan路径读取/错误/边界替身。
- 同上，`-p test_ui_spawn_state.py`：通过。
- `scripts/check-cache-syscall-trace.py --source <work>/tree/.cache/xnu-work/bsd/dev/arm/systemcalls.c`：通过，ASan。
- `scripts/check-runtime-report.py --source <work>/tree/.cache/xnu-work/bsd/kern/kern_exec.c --output out/data-bringup/ui-call-runtime-host-check-final`：补齐显示/UI API替身后通过ASan/UBSan。API为主机替身，不是设备验证。
- `scripts/check-platform.py --unixnu ../UniXNU --output out/data-bringup/ui-call-platform-check`：拒绝，框架HEAD2c834e3不同于旧审阅快照；没有绕过版本保护。
- `python3.14 ../UniXNU/scripts/porting-record.py check --device .`：13个area通过。

参考项目通过GitHub连接重新读取，固定提交/blob见`reference-sources.json`，结论见
`docs/ui-reference-comparison.md`。优先审阅目录AppleKeyStoreState接入与本板内存预算，
不将其他设备的地址或服务禁用列表作为本板事实。

`python3.14 evidence/display/ui-call-v9/prepare-runtime120.py`已生成独立120秒对照，
输出`out/data-bringup/ui-call-runtime120/boot-partition.img`，摘要db0121c9。
最终BOOT内FAT重新提取核对；只有终止参数变化，内核/ADT/信任/种子不变。
源60秒镜像和board默认保留；120秒版未上传、未启动。
