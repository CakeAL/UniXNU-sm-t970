# 持续运行对照（待实机验证）

由机主观察到 Apple logo 的 BOOT `bb4d847476d455c0a49d28ffea03492e8e0f2b5fd0f2480ed2eb34dc5604912e` 生成。仅从 XNU 入口参数移除 `t970-runtime-report=125`，避免 125 秒主动生成报告并 panic；`panic_on_error_exit=backboardd,SpringBoard` 仍保留，真实异常仍可能终止。其余参数、内核、ADT、trust cache、Data 种子、固件及 DTB 均保留原版。构建脚本从独立 FAT 回读逐项检查，并核对 BOOT 的非 payload 部分。没有改动设备默认配置或覆盖既有镜像。

执行 `python3.14 evidence/display/display-continuous-v25/prepare.py`，输出保存在忽略目录 `out/data-bringup/display-continuous-v25/`。`preparation.json` 是主机打包结果。机主授权仅写 BOOT 并重启；连接设备报告 Samsung SM8250，读取 PIT 的 87 项与既存记录一致，BOOT 是 17408 个 4096 字节块。下载 PIT 后以 `--resume` 写入时会话开始失败；重新握手的尝试也在初始化时失败，两次均未进入 BOOT 上传，日志分别保存在 `resume-failed.json`、`flash-resume-failed.log`、`handshake-failed.json`、`flash-handshake-failed.log`。机主重新进入 Download Mode 后，第三次仅上传 BOOT 达 100%、Heimdall exit 0 并请求重启，见 `upload.json`、`flash.log`；未做设备端读回。

机主反馈：重启后超过三分钟 Apple logo 一直未变化，期间未看到其他画面或自动重启。见 `device-result.json`。该画面不能证明后台停止或仍在推进，也不能证明是否继续提交帧，桌面尚未验证。补充对先前 v24 照片的 backboardd 栈符号化见 `v24-backboard-symbols.json`：当时采样位于 Objective-C 类名枚举及 NSBundle 加载路径，无法据单次采样断定其持续阻塞。

主机平台检查在读取 DT/ADT 前拒绝执行：当前 UniXNU HEAD 为 `2c834e313d25482c78d38d703eff1f8d190f2597`，而共享支持审阅记录固定 `194aae294c1107e791f4f74b2be371a391ac6bc4`。这不是 DT/ADT 通过；本次对照直接复用已打包 ADT 并核对其哈希。porting record 检查另行运行。
