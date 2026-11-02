# 副核 bring-up 证据

- cpu2：BOOT3c72017f，实机仅1核，CPU1 step4/PSCI0，无副核timer/SGI。
- reset-context：BOOT9d4dc888，23:28照片验证表、CPU1编号、handler匹配，仍仅1核。
- cpu8：仅主机准备，未刷入。
- entry-trace：BOOT95accf53，10秒目标等待，四段入口记录，实机CPU1入口3（common_start前），C入口未见。

每轮preparation/upload中的pending反映生成该记录时的状态；后续device-result覆盖观察结论，
不改写早期回执。上传成功不等于读回校验或副核启动成功。
linked-instruction-check仅验证模拟MPIDR/CPU数据下实际链接指令，不能验证缓存一致性和硬件启动。
总体平台checker仍因历史框架版本断言失败，未记作通过；独立打包/CPU拓扑检查通过。

- mmu-trace：BOOTb44e4108，实机CPU1标记9，尚未观察到高地址标记10。

- trampoline-trace：BOOT36c2f602，高地址入口沿用物理记录指针，捕获实际跳转/返回/基址/TTBR/TCR；实机结果待回报。

- reset-publish：BOOT6fe3e519，实测cpu2/sec1、CPU1 step7/C4、两核计时器及匹配TTBR1。

后续二进制检查确认前3版的C入口标记被C宏条件编译掉；不能以C4未见单独判断入口。
reset-publish已修正并模拟验证实际C标记；汇编阶段记录和ArmCpu计数不受影响。

- ipi-check：BOOT7e60f7c9，首次UFS NOP stage0拒绝，机主重启同镜像恢复；两核重现，显式SGI0发送后recv0/cpu1=0>0。IPI与8核仍待验证。
