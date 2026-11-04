# 根域电源看门狗取证 v67

v65 和 v66 都在 Hello 约 10 秒后转黑。v64 的回栈确认根域看门狗，但后两轮未采到 panic 文字。v67 保留 v66 的 2 GiB、ADT 睡眠策略和 Data 输入，重新加入 240 秒报告，并在根域电源看门狗超时时打印 PM 机器状态、等待原因、电源状态和首个排队服务的类名。类名只在等待数组非空时可用。状态字段为即时快照，不能据此断言哪个回调导致超时。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py \
  --cached-headers --output out/data-bringup/pm-watchdog-v67-build
python3.14 evidence/display/hello-black-v64/prepare.py --pm-watchdog
```

首次构建的公开 XNU 头文件下载遇到 TLS EOF，重试用已有缓存并逐文件校验原始 Git blob 摘要。新 panic 仅由 `t970-pm-watchdog-detail=1` 开启。若先到 240 秒报告，则用 v64 增加的帧时刻判断有无黑帧或停帧。

内核及 prelink 成功，最终 BOOT 回读核对了内核、启动项与未变更的 ADT、Data 种子和信任缓存。BOOT 上传成功并请求重启，见 `preparation.json` 和 `upload.json`。

## 实机结果

机主观察到 Hello 约 10 秒后转黑，之后诊断页出现。照片确认 `target=240`，无 PM 超时报告。成功 swap 11、传输 11、退役 11、普通帧复制 9。最后正常复制 158.554 秒，驱动明确将 GOP 填黑 158.582 秒，差 28 ms。`dark=0` 表示本轮未记录源图全黑；驱动的 `blank` 路径处理无 surface 的请求。触发该请求的客户端和策略仍未确认。

可对照 [Sirius 的 Setup 显示记录](https://unixnu.com/devices/sirius-dddqmmx#display) 中 SpringBoard 禁止自动调暗与空闲睡眠偏好。该记录同时包含画布尺寸修复，不能单独证明偏好设置能解决 T970。
