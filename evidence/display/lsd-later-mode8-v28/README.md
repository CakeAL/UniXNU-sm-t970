# 90 秒 lsd 后四线程采样

上次 `aeb13ffc…` 的 90 秒样本中 lsd 有 7 个线程，只读取前 4 个，其中一个等待数据库 seeding 完成。为了检查潜在的工作线程，新增 `t970-ui-stack=8`：仅选择 `lsd`，跳过队列前四个，采第 5–8 个线程各最多 16 级 FP 栈。仍是隔离 worker 中的有界读取，task/thread try-lock、map 引用和超时后隐藏未完成结果的机制不变；模式 1–7 保留。

线程队列顺序可跨启动改变，不能保证下一次的第 5–8 个与上次未采线程相同；若 lsd 不存在或不足 5 个线程，不能断言其后续状态。实时寄存器与栈不构成一致性快照，输出可能被屏幕截断。目标仍是报告线程启动后约 90 秒，然后主动 panic 显示诊断，机器启动到报告的墙钟时间可能略长。

BOOT `f69965a7eefcfe6213b3f0a65f63fa558b61389dcb39512aa5d197dfaf655a3a` 已经完成内核、payload 和打包；FAT 回读、mode8 的实际 helper ASan/UBSan、Mach-private 编译及内核链接/预链接通过。机主授权 BOOT 上传和重启，Heimdall 显示上传成功、退出码0并请求重启，未设备读回，见 `upload.json`、`flash.log`。平台 DT/ADT 总检查仍因主仓库 HEAD 与审阅 pin 不同，在读取 DT/ADT 前停止。上一轮内核和归档保存在忽略目录 `out/data-bringup/pre-lsd-later-mode8`，旧镜像保留。

## 实机结果

`screen-target90.jpg` 显示 lsd99 共7线程、visited7/busy0，完整采到队列第5–7线程，结束标记 processes1/clipped0。第5线程处理 XPC 并在 dispatch group 等待数据库 seeding；第6、7线程在工作队列入口。显示 open5/swap0，说明本次仍处于首帧前。两次启动线程队列顺序可能不同；这张图未捕获 seeding 的执行线程，也未观察到 Wi-Fi 地址查询，不能断定卡住或证明参考项目的原因。符号、图片哈希及其局限见 `symbols.json`、`device-result.json`。
