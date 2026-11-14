# 清除 MISC 中的 boot-recovery，恢复 One UI 启动（2026-11-11）

## 现象与定位

机主反馈只能进入 iPadOS，无法回到 One UI。两个槽位的内容如下：

| 分区 | 内容 | 最后写入 |
| --- | --- | --- |
| BOOT | MinsOS 1.2.3 Android `boot.img`，52,170,768 字节，SHA-256 `5e206cde…` | 2026-11-08 20:11，TWRP sideload 安装 |
| RECOVERY | 双系统 UniXNU 镜像（GPU stream 路由模式 34，`05e00331…`） | 2026-11-11 15:3x |

BOOT 仍是 Android 引导，One UI 与其 F2FS `userdata` 未被破坏（`unixnu` 分区
37292800–62458623 单独存放 iPadOS 根镜像）。问题在 `misc`：2026-11-08 用
`adb reboot recovery` 测试 iPadOS 时写入了 `boot command: boot-recovery`
（见 `out/dual-system/clear-bcb/twrp-recovery.log`）。当年 20:56 清一次 MISC 后，
21:1x 的正常启动立即回到 One UI；此后再次 `adb reboot recovery` 又写回该命令，
而 RECOVERY 现在是 UniXNU 镜像，不会像 Android recovery 那样消费并清除 BCB，
所以每次开机都被引导到 RECOVERY＝iPadOS。

## 本次操作

只写 `MISC`，镜像取安装 MinsOS 前的备份 `out/dual-system/pre-minsos-20261108/misc.img`，
其 BCB 区为零；1,048,576 字节正好等于 PIT 中 `MISC` 的 256×4096 块。

```sh
.cache/heimdall/build/bin/heimdall flash --MISC \
  out/dual-system/clear-bcb/misc-clean.img --no-reboot
```

Heimdall 报告 `MISC upload successful`，随后仍出现本机既有的
`Failed to receive session end confirmation`（exit 1，2026-11-08 同样出现），
按上传结果判定成功。未读回，未改动 BOOT、RECOVERY、userdata、unixnu、vbmeta、DTBO。
回执见 [receipt.json](receipt.json)，传输日志 `flash.log`。

## 观察与后续

- 下次正常开机应进入 One UI；iPadOS 仍通过按键进入 RECOVERY 启动，两条路径互不影响。
- `adb reboot recovery` 会再次写入 `boot-recovery`；在 RECOVERY 为 UniXNU 镜像期间，
  切 iPadOS 应使用物理按键组合，避免把 BCB 留在 `misc`。
- 若清 MISC 后仍停在 iPadOS，下一步用 `MinsOS_v1.2.3_20261024_gts7xlwifi.zip` 内的
  `boot.img`（SHA-256 `5e206cde…`，与安装时读回一致）重刷 BOOT 后再判定。
