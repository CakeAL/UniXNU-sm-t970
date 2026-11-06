# T970 Setup 进程与 LaunchServices 持锁线程取证 v79

v77 在最后一次 FTS 按下后呈现了三帧，随后停在语言切换附近。终止报告没有 `Setup` 进程行，SpringBoard 锁记录里的持有者也没有采到。v79 以 v77 普通写屏版为基线，加入 `t970-setup-life=1`。 [v77 实测](../setup-language-v77/README.md)

- `Setup life exec` 记录 launchd 对 `/Setup.app/Setup` 路径后缀的执行次数、最近 PID 和错误。
- `exit` 记录同名进程完成退出的次数、最近 PID 和原始 wait status。 `reason` 是内核的退出原因命名空间和代码。计数为零表示本探针未命中。
- SpringBoard 标题上的 `owner` 是开始采样前记录的最近持锁线程 ID，`seen=1` 表示读到了相同 ID 的寄存器。最多查看 64 个线程，仅输出第一条和匹配 ID 的行。历史持有者可能已释放锁或退出。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe \
  --output out/data-bringup/setup-lifecycle-v79-build
python3.14 evidence/display/hello-black-v64/prepare.py --setup-lifecycle
```

宿主 ASan/UBSan 覆盖 opt-in、路径筛选、退出原因、非阻塞读取和持有者位于首个线程之后的采样。仓库测试 54 项，44 项通过、10 项跳过。内核编译、预链接、原版 HID 绑定复核及最终 BOOT FAT 回读通过。BOOT 哈希为 `961828dab0de5cdc0deb17e9c66dbcf351bb189c2c2e389974252e416d553678`。实机结果待采集。
