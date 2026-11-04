# 禁止系统睡眠对照 v66

从 v65 仅在 ADT 增加 32 位 `/defaults/sleep-disabled=1`。XNU 在系统启动完成时通过 `PE_get_default` 读取该值，并在根域的睡眠许可判断拒绝系统睡眠。v65 的 `noidle=1` 保留，以隔离新增属性的效果。该设置是唤醒尚未适配时的 bring-up 对照。

参考 [SM-T733 固定配置](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/3bb0d6f7840f088db6a0ec88ecb841e12042422f/board.toml) 和 [小米 15 移植配置](https://github.com/7Night-kqx/UniXNU-dada/blob/main/board.toml)。这两份配置使用相同的 XNU 入口。它们没有证明 T970 的看门狗超时来自同一个子服务。

```sh
python3.14 evidence/display/owned-window-2g-v62/prepare.py --disable-system-sleep \
  --output out/data-bringup/sleep-disabled-v66
```

使用共享 UniXNU 编码器，验证原始 ADT 可逐字节往返，并对比实际 BOOT 内的完整 ADT。内核、参数、信任缓存和 Data 种子摘要与 v65 相同。BOOT 已上传并请求重启。Hello 持续显示、触控和主页仍待实测。

机主反馈 Hello 后约 10 秒再次黑屏。相同 ADT 默认值没有维持可见界面。没有新的 panic 证据来确认是否复现 v64 的根域看门狗超时。见 `device-result.json`。
