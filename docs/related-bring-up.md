# 相近设备的早期启动记录

查询日期：2026-11-01。外部项目的实机结论由维护者报告，本仓库未复测。

## Surface Duo 2（zeta，SM8350）

[原始记录：Bounded kernel probes](https://github.com/none24smu/UniXNU-zeta#bounded-kernel-probes)
报告 `PE_init_iokit` 调用前可达，调用后进入异常路径。进一步探针通过 `InitIOKit`，
在 `generatePlatformUUID` 的 `SHA1Init` 处发现运行时 `g_crypto_funcs` 为 NULL。
其修复是在 `InitIOKit` 后、`ConfigureIOKit` 前初始化匹配的源码 provider，
并修正 POST 的完整性输入；修复后成对延时探针确认 `PE_init_iokit` 返回。

可借鉴的是逐层检查调用边界、区分异常与正常终止、再核对 provider 启动顺序。
其 XNU 为 12377／iOS 26，T970 为 10063／iPadOS 17，不能直接移植初始化补丁。

## 小米 10 至尊版（cas，SM8250）

[固定版本的 CPU0 观察](https://github.com/ht94911/UniXNU-cas/blob/15bc58bb060a1e3c3cd15d4220997e4e54953d0a/docs/cpu0-platform-clock.md)
记录 VM、早期 PE 和时基初始化通过，但该候选在 `machine_startup` 前停止，
且保持 IRQ/FIQ 屏蔽。它没有验证 IOKit、定时器 IRQ 或用户态，不能当作当前卡点的解决记录。
相同 SM8250 和 iPadOS 17 配置值得比较，但地址与内存布局仍须使用 T970 的实测输入。

## 对本设备的含义

- `sched_startup` 返回和 `PE_init_iokit` 调用前均已确认；后者返回尚未确认。
- 下一步测该函数中 `InitIOKit` 调用前，区分前段控制台／启动属性处理和后段 IOKit。
- 现有 OS profile 使用 `CONFIG_XNU_CRYPTO_BOOTSTRAP="prelinked"`；主机构建报告列出了
  `com.apple.kec.corecrypto`。这只证明构建纳入，不能证明运行时初始化成功。
- 不凭色条推断 `g_crypto_funcs` 状态，也不跳过加密自检。需要本机运行时证据后再决定修复。

本次查询没有找到可确认同一根因、可直接用于 SM-T970 的修复记录。
