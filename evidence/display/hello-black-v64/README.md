# Hello 后黑屏诊断 v64

机主在 v63 看到 Hello，动画明显卡顿，约 4 秒后黑屏。短按电源键未恢复画面。沿用 2 GiB 窗口及同一份 Data 种子，加入只读显示观测和 240 秒终止报告。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py
python3.14 evidence/display/hello-black-v64/prepare.py
```

在 v55 已核对的显示归档中只替换板级 DisplayRegistration.o，逐成员比较。原归档和 prelink 输入内核已备份并恢复。使用现有解析配置重新构建与 prelink，最终 BOOT FAT 验证 ADT、信任缓存和 Data 种子摘要不变。Android v2 头、固件、DTB 和分区尾部逐字节一致。设备已接收 BOOT 上传，240 秒画面待机主确认。

- `pub/first/last` 为发布、首次成功 CPU 复制及最近一次成功 CPU 复制的毫秒数。
- `blank/dark` 为最近一次明确的 GOP 黑色填充及最近一次源图扫描全黑的时刻。0 表示未记录。源图扫描有次数上限，且先于复制；黑色源图不等同于成功写屏。
- 若诊断页能重新点亮并显示这些计数，说明 XNU 在报告时仍可运行、GOP 可写入。单凭这些值不能证明面板休眠或触控状态。

宿主显示单测 2 项通过。完整 `check-platform.py` 在主仓库版本比对处停止，当前 `2c834e3` 与该检查器要求的 `194aae2` 不同。打包 ADT 仍由 v62/v63/v64 各轮 FAT 回读验证。

## 实机结果

机主更正后的 22:55:43 截图显示 `Sleep/Wake hang detected @IOPMrootDomain.cpp:12812`。没有到预定的 240 秒报告，所以上述帧计数没有采到。用实际链接的 v64 内核符号定位回地址 `0xfffffff0078c6b18` 到 `IOService::watchdog_timer_expired + 0x60`；选定 XNU 源码中该路径调用 `sleepWakeDebugTrig(true)`。照片无法识别触发的 IOService，也无法区分空闲睡眠、其他电源请求或某个驱动的状态转换。下一步用 [v65](../no-idle-v65/README.md) 隔离内核空闲睡眠计时器。
