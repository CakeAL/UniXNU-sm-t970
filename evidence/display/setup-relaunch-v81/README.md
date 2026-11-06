# T970 语言切换后继续启动 v81

v80 的终止原因是 SpringBoard 域 10、代码 `0x5BC1EA44`。在 21H461 原版共享缓存中，该常量由 `SBRestartManager _doRestartForTransition:` 使用。Sirius 的实机记录也显示同码后 SpringBoard 和 Setup 重启。 [v80 实测及原版符号](../setup-exit-v80/README.md) · [Sirius 实测](https://unixnu.com/devices/sirius-huajifruit#input)

v81 从 v80 加入 `t970-allow-sb-relaunch=1`，仅当进程名为 SpringBoard、原始状态为 SIGKILL、且原因域和代码精确匹配时，跳过诊断 panic，让原版退出和重新启动继续。它移除了 360 秒终止报告，可持续运行。其他异常仍可从 `T970 UI exit` 读出原因。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe \
  --output out/data-bringup/setup-relaunch-v81-build
python3.14 evidence/display/hello-black-v64/prepare.py --setup-relaunch
```

宿主 ASan/UBSan 验证了开关、精确匹配、错误原因域和代码、非 SIGKILL、缺失原因及其他进程。内核预链接、原版 HID 绑定复核和最终 BOOT FAT 回读通过。BOOT 哈希为 `9c03ea76ef377b04e7c76ac9ebc58c4d32b9f826afe2339c2fee1499b34d96f0`。Heimdall 确认 BOOT 上传并请求重启。机主已设置语言，并进入「传输 App 与数据」。选择不传输后，右上角持续转圈，交互仍慢。下一页和转圈时长待确认。 [机主反馈](device-result.json)
