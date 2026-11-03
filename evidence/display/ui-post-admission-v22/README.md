# 并发额度修正后的主线程等待（2026-11-04）

v21 BOOT5385b6ce照片03:00:42确认三组req0，累计完成MG134/BB161/SB75→78，
显示client enter/open6/fail0，但swap/transfer/copies/retire全部0。
所有Q头字段0表示该次没有受限请求，不代表再次测得cached parallelism0。
目前只确认队列推进，未证明桌面或首帧，也不能沿用修复前BB/SB的等待调用栈。

v22使用完全相同v21内核，唯一启动参数变化为t970-ui-stack=6改1；保留90秒、八核和768MiB请求。
既有mode1同时采BB/SB前4线程寄存器，各首线程最多8级FP链。
不更改代码，不增加工作线程强制唤醒、不禁用依赖服务。报告方仍隐藏未完成worker buffer。
主机核对内核哈希和规范化参数完全一致，重新build payload/bootimg，独立解包检查及FAT往返通过。
最终BOOT e44011cb29156ae60679de64d2fb9ca8f9e3dc36eb81845124c0801cfba53f01。

Heimdall上传结果见upload.json；实机结果待回报。照片应同时包含BB/SB的首线程FP行。
