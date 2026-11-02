# 副核 bring-up 证据

- cpu2：BOOT3c72017f，实机仅1核，CPU1 step4/PSCI0，无副核timer/SGI。
- reset-context：BOOT9d4dc888，23:28照片验证表、CPU1编号、handler匹配，仍仅1核。
- cpu8：仅主机准备，未刷入。
- entry-trace：BOOT95accf53，10秒目标等待，四段入口记录，实机CPU1入口3（common_start前），C入口未见。

每轮preparation/upload中的pending反映生成该记录时的状态；后续device-result覆盖观察结论，
不改写早期回执。上传成功不等于读回校验或副核启动成功。
linked-instruction-check仅验证模拟MPIDR/CPU数据下实际链接指令，不能验证缓存一致性和硬件启动。
总体平台checker仍因历史框架版本断言失败，未记作通过；独立打包/CPU拓扑检查通过。

- mmu-trace：BOOTb44e4108，新增6处副核MMU标记，10秒目标等待，实机结果待回报。
