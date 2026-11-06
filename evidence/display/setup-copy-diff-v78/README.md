# T970 差分写屏对照 v78

v77 的最后一次完整像素复制用时 265.972 毫秒，最大 292.623 毫秒。v78 从同一个 BOOT 加入一个参数 `sheng-fb-diff=1`，以测试当前页面里未变更的像素块能否省去写屏。沿用组件已有的 64 字节比较与缓存影子帧，首帧仍完整复制。

```sh
python3.14 evidence/display/hello-black-v64/prepare.py --setup-copy-diff
```

最终 FAT 回读确认原 v77 内核、ADT、信任缓存和 RAM Data 种子哈希一致。360 秒报告和触控配置沿用 v77。BOOT 哈希为 `eaa25d24b04aa16f4acf7c7c0ea3c59f13f4bfd57b18787b6853d0fc16dddf8f`。Heimdall 已确认 BOOT 上传并请求重启。

机主点击语言后看到内核退出报告。SpringBoard PID 27 的原始 wait status 为 `0x9`，即 SIGKILL。用镜像中的确切内核符号化后，栈为 `exit_with_reason ← postsig_locked ← bsd_ast`，符合收到信号后退出的路径。已有 `panic_on_error_exit` 在 360 秒取样前主动打印了这条退出报告。照片没有复制耗时，差分复制的收益和信号发起方仍未知。 [实测及符号](device-result.json)
