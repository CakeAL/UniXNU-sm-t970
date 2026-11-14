# 再次清除 MISC 中的 boot-recovery，恢复 One UI 启动（2026-11-15）

## 现象与定位

机主反馈「又进不去 One UI」。上一次同类现象见
[misc-bcb-clear-20261111](../misc-bcb-clear-20261111/README.md)：`misc` 中的 BCB 留下
`boot command: boot-recovery`，而 RECOVERY 现在是 UniXNU 镜像，不会像 Android recovery
那样消费并清除该命令，于是每次开机都被引导到 RECOVERY 而不是 BOOT（One UI）。

本轮追加的旁证：

- 2026-11-15 01:57–02:16 连续四次只刷 `RECOVERY`（`cbbf85d7…` 与三个 MMU/控制台复位探针），
  刷写均带 `--no-reboot`。机主随后报告正常开机看到的是 RECOVERY 的品红条，随后按探针
  计时复位；从未进入 One UI。若 BOOT 正常被选中，开机不会先出现该品红条。
- 2026-11-15 02:22 设备已枚举在下载模式（`heimdall detect` → `Device detected`），
  ADB 无连接，无法从系统侧改写 BCB，只能在下载模式写 `MISC`。
- BOOT 自 2026-11-08 起一直是 MinsOS 1.2.3 `boot.img`（52,170,768 字节，
  SHA-256 `5e206cde…`），本轮操作没有写过 BOOT。

## 本次操作

只写 `MISC`，镜像沿用 2026-11-11 已验证成功的
`out/dual-system/clear-bcb/misc-clean.img`：1,048,576 字节，SHA-256
`64c814d07a23c8274521bc650e11895cffd3d036831429c4e22748ba79db579c`，
等于 PIT 中 `MISC` 的 256×4096 块，两个 BCB 槽位（0–2048、2048–4096）全零。
镜像来源为安装 MinsOS 前的本机备份 `out/dual-system/pre-minsos-20261108/misc.img`。

```sh
.cache/heimdall/build/bin/heimdall flash --MISC \
  out/dual-system/clear-bcb/misc-clean.img --no-reboot
```

Heimdall 报告 `MISC upload successful`，随后仍出现本机既有的
`Failed to receive session end confirmation`（exit 1）。这与 2026-11-08、2026-11-11
两次成功写入的结束特征一致，按上传结果判定成功。未读回；未改动
BOOT、RECOVERY、DTBO、userdata、unixnu、GPT。传输日志
[flash.log](flash.log) 的 SHA-256 为 `e067af3a…`。

## 当前设备状态

| 分区 | 内容 |
| --- | --- |
| BOOT | MinsOS 1.2.3（未改动） |
| RECOVERY | `b3cb8c54…`，`PE_create_console` 返回探针，复位计时 16 秒 |
| MISC | 已写为 BCB 全零 |

写完后设备仍停在下载模式（`--no-reboot`），需要人工长按电源键（必要时
Power + Vol Down 约 10 秒）退出下载模式并正常开机。

## 待观察

- 正常开机应直接进入 One UI；iPadOS 仍只能在 RECOVERY 中启动，且当前 RECOVERY
  是会在 16 秒后自动复位的探针，不适合日常使用。
- `adb reboot recovery` 会再次写入 `boot-recovery`。在 RECOVERY 为 UniXNU 镜像期间，
  切 iPadOS 后如果设备自行复位，会按 BCB 回到 RECOVERY 形成复位循环；此时应重新清
  `MISC`，而不是重刷 BOOT。
- 若清 MISC 后仍停在 RECOVERY 或无法进入 One UI，下一步是核对 BOOT 摘要并考虑
  TWRP/ADB 读取 `misc` 实际内容，再决定是否重刷 BOOT。
