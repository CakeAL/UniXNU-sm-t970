# T970 托管内存扩到 8 GiB v85

设备实际有 8 GB（`MemTotal: 7806144 kB`），但端口只把 2 GiB 交给 XNU。应用能开、切换却慢，托管内存是第一个要排除的限制。 [内存记录](../..) · [v84 桌面](../../display/setup-skip-v84/README.md)

实机 DT 的 DRAM 是三段，合计 7.94 GiB：

| 起始 | 大小 | 说明 |
| --- | --- | --- |
| `0x80000000` | `0x3BB00000` | 低 958.7 MiB |
| `0xC0000000` | `0xC0000000` | 3 GiB |
| `0x180000000` | `0x100000000` | 4 GiB |

`0xBBB00000`–`0xC0000000`（69 MiB）不在任何一段里，是固件保留的空洞；它在现有 2 GiB 包络内已经存在，本次不改变这部分行为。

## 改动

- ADT 只有一段 `dram-size`，且加载器（DarwinBoot）不读它，只有 XNU 用。因此直接改引导镜像里的 `/chosen/dram-size`：`0x80000000` → `0x200000000`，其余字节逐字节不变，保留现有 8 CPU、PSCI、身份和 memory-map 节点。
- 4K 引导页表：框架补丁按 6 GiB 预留 16 页；8 GiB 需要每侧 1 个 L1 + 9 个 L2，两侧共 20 页。新增设备补丁 `t970-8g-bootstrap-tables.patch` 把 `BOOTSTRAP_TABLE_SIZE` 提到 32 页，留出余量。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork \
  --output out/data-bringup/setup-8g-v85-build
python3.14 evidence/memory/8g-v85/prepare.py
```

宿主测试新增 `tests/test_adt_patch.py`（只改一个属性、旧值不符、未对齐、尾部多余字节）。BOOT 哈希 `1436f2f1`，内核 `6e8b011b`，ADT `be41464a`；数据种子、配置、信任缓存、固件和分区尾部均未变，Heimdall 确认上传并请求重启。

实机待确认：能进桌面，并且三指报告里的 `pages=` 从 `0x79dbe`（约 1.95 GiB）升到约 7.9 GiB。
