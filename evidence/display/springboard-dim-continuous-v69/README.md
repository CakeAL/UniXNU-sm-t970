# 防调暗持续启动 v69

v68 实验版实测未转黑。v69 从该镜像仅移除 `t970-runtime-report=360`，让 Setup 继续运行。

```sh
python3.14 evidence/display/springboard-dim-v68/prepare.py --continuous \
  --output out/data-bringup/springboard-dim-continuous-v69
```

最终 BOOT FAT 回读确认内核、ADT、信任缓存及防调暗 Data 种子摘要与 v68 实验版一致。固件、Android v2 头、固件 DTB 和尾部逐字节相同。设备已接收 BOOT 上传并请求重启。持续亮屏、物理触控和进入主屏幕待分别验证。
