# T970 3840 MiB EFI-owned window v88

v87 停在品红条，之后已回滚。仅从该现象不能确定具体故障指令；但其补丁把
`dram-size` 当成实际已分配内存，违反 Loader 的所有权约定。现已从补丁序列撤下，
补丁文件和旧镜像保留。[v87 历史](../8g-v87/README.md)

v88 基于 v85（没有 managed-range 补丁）的精确镜像，只把 ADT 的
`/chosen/darwinboot-memory-size` 从 `0x80000000` 改为 `0xf0000000`。
内核、Data 种子、信任缓存、配置、固件、固件 DTB 和分区尾部均逐字节核对未变。
`dram-size=0x200000000` 是物理地址包络，不能作为空闲页列表。

```sh
python3.14 evidence/memory/owned-window-v88/prepare.py
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/owned-window-v88/boot-partition.img
```

BOOT SHA256：`0c94056eca35b7734fb1fe7c08a9d26c7b2e10c49193b8344b3b0967f3906b34`。
上传成功并请求重启，未进行分区读回；详见 `preparation.json`、`upload.json`、`flash.log`。

## 实机结果

2026-11-07 12:08:46（UTC+8）机主确认进桌面，三指报告照片已保存。

- `main=1`，257 个进程，SpringBoard 27、backboardd 57。
- `cpu=8 sec=7`。
- `pages=0xe81dc`，4 KiB 页，共 **3713.859375 MiB** 受管理内存。
- `free=0x1443` 是这一时刻的空闲页，不能视为全部可回收内存。
- 52 次拷贝和退役、0 swap 拒绝；最近／最大复制约 42.46／44.807 ms。

来源和照片哈希见 `device-result.json`。报告由三指手势主动进入终止诊断，
不能把末尾的 `kern_exec.c` 位置当成自然发生的启动崩溃。

这验证了单个 3.75 GiB 申请能启动及到达桌面。尚未采集实际物理基址和运行时 EFI
内存图，未做页面压力／保留区完整性检查，也未验证完整 8 GB。
单靠 stock 三段内存描述不能得出实际 EFI 连续块的大小。下一步需要 Loader 导出
实际拥有的区间和保留区，再实现、检查 XNU 的多区间页枚举、有效页判断、启动分配
和 DMA 地址约束。不能再直接扩大 `arm_vm_init` 的连续范围。
