# 2 GiB 持续启动 v63

以机主已确认到达 120 秒报告的 v62 BOOT 为基线，从 XNU 启动项移除 `t970-runtime-report=120`，允许 iPadOS 继续运行。最终 BOOT FAT 回读确认 ADT、内核、信任缓存、Data 种子相同。启动头、固件 FD、DTB 和分区尾部逐字节相同。

```sh
python3.14 evidence/display/owned-window-2g-v62/prepare.py --continuous \
  --output out/data-bringup/owned-window-2g-continuous-v63
```

BOOT `4ba79c66…` 已上传，Heimdall 已请求重启。机主报告先显示 Apple 标志，随后出现 iPadOS 的 Hello 设置界面。Hello 动画明显卡顿，约 4 秒后黑屏，短按电源键未点亮。启动已到 Setup；稳定显示、主屏幕、触控和 GPU 仍待实测。见 `device-result.json`。黑屏取证使用 [v64](../hello-black-v64/README.md)。
