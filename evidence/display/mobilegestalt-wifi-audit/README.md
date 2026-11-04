# iPadOS 21H461 MobileGestalt Wi-Fi 路径静态核查

在 UUID `590d839a82d230f1a17d0cc053420f73` 的原始 arm64 共享缓存中，`libMobileGestalt.dylib` 的一段条件路径把 `IODeviceTree:/chosen` 和 CFString `mac-address-wifi0` 传给内部函数；返回非空时从该路径返回，否则依次尝试 `sdio`、`wlan`、`marconi-wifi`，最后在另一条件下进入带 `IONetworkController` 字符串的回退函数。这与 [Poco F1 参考记录](https://github.com/ry-diffusion/Bergamota/blob/37a7a7a917fc09945ed2f7d1ae68b84d4525b4cb/NOTES.md) 描述的结构相似。

命令：`.cache/probe-test-venv/bin/python scripts/audit-mobilegestalt-wifi.py --cache <原始21H461缓存目录> --output evidence/display/mobilegestalt-wifi-audit/audit.json`。脚本验证缓存 UUID、CFString 内容、地址字符串和关键分支指令；只输出地址和结论，不保存 Apple 二进制。静态流程存在前置条件，不能据此宣称每次一定执行，或断言本板已读取属性、数据类型被接受、发生网络等待或这就是 seeding 原因。

90 秒 Wi-Fi 地址对照仍显示数据库 seeding 等待；该快照早于本轮首帧，因此既未证明改善，也不能排除较晚差异。参考项目报告的 iOS 16 路径、OS 版本和本设备不同。
