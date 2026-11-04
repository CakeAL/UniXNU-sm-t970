# 21H461 软件显示路径对照

T733 的 48f 实机记录报告 CPU 显示帧持续输出。其 NativeLegacyDisplay 接收 IOSurface，校验格式、尺寸和 stride，再通过 CPU 复制到固件留下的 framebuffer，报告帧完成。T970 已接入相同 MobileFramebuffer ABI 的 GOP 路径，实机已观察到 6 次成功打开，swap 仍为 0。

- [T733 48f 实机记录](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/3bb0d6f7840f088db6a0ec88ecb841e12042422f/docs/archive/FORMAT2_2026-10-25.md)
- [T733 NativeLegacyDisplay](https://github.com/RigoLigoRLC/unixnu-nativemobiledisplay/blob/31833aa2ad8b1faae9c3fa9752830d4271d46979/NativeLegacyDisplay.cpp)
- [T733 21H461 显示格式策略](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/3bb0d6f7840f088db6a0ec88ecb841e12042422f/docs/DISPLAY_FORMAT_POLICY_2026-10-28.md)

BOOT e44011cb 的 03:08:38 照片显示 BB 进入 QuartzCore AccelServer::renderer → CAMetalContextCreate。缓存 UUID 与符号文件匹配，slide 0xf974000 由 mach_msg2_trap 交叉核对。原版块 0x189595afc 在 0x189595b7c 匹配 IOAcceleratorES，枚举结果为空时在 0x189595bd4 调用 usleep(100000)，最多睡眠 300 次。拍到的返回地址 0x189595bd8 正是循环回边。轮询完成后调用 MTLCreateSystemDefaultDevice。QuartzCore 内可定位 SWContext 与 Server::sw_renderer，实机选择路径待验证。SB 仍在 BKSDisplayGetMainScreenInfo 等待 Mach 回复。详见 v22 的 device-result、symbols 和 ca-wait-targets。

本轮使用同一内核，以 125 秒采样对照 90 秒。逐项比较最终 FAT 的内核、信任缓存、Data seed、配置和 ADT。配置仅变更报告期限，ADT 仅有重建生成的 random-seed 差异。检查项和镜像 SHA256 见 checks.json，上传见 upload.json。实机重点看 BB 首线程是否离开轮询，及 swap、copy、retire 是否增加。
