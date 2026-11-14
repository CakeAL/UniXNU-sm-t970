# 双系统 RECOVERY GPU 路由槽调查

模式 34 从[已实测的模式 33](../dual-cb1-20261111/device-result.json)继续。CB1 的启停和两次 ASID 2 同步完成后，检查原有 GMU SID5，读取 SMR1–5 与 S2CR1–5。候选槽要求 SMR 为零且 S2CR TYPE 为 FAULT，第二轮读取和 live 守卫一致才报告 `ok`。三指报告新增 `GPU streams` 行，给出槽位位图、GMU 的 SMR0 和五个原始 S2CR 值。调查阶段只读候选槽，CP 保持空闲。

以设备提交 `a14a093` 工作树、框架 `404572cfc431f0b259cd190a99ad5b2c881a074a` 构建。在 `out/dual-system/gpu-streams-20261111` 用模式 33 保存的编译命令重编 `DisplayRegistration.o`。原 archive 只替换这个成员并逐项回读，然后按双系统现有配置链接 XNU。dSYM 步骤仍受沙箱 `/dev/fd` 限制。使用先前已通过的 21H461 prelink 命令，输出到隔离目录，再加 `--panic-screen --no-reset`。

```sh
python3.14 scripts/pack-dual-data-recovery.py \
  --base out/dual-system/boot-candidate/recovery-stock-dtbo.img \
  --kernel out/dual-system/gpu-streams-20261111/kernel.macho \
  --mode 2 --gpu-streams \
  --output out/dual-system/gpu-streams-20261111/recovery-gpu-streams.img
```

| 输出 | SHA-256 |
| --- | --- |
| `DisplayRegistration.o` | `9d250b1c575006880a440e4e296c7711f09a7b8f15fa631de8a0c117c6d7c2b7` |
| `kernel.raw` | `572198b088683a24f1b4a813f539f508bf8600d4a68b31cb160fe4ae9149975a` |
| `kernel.macho`（panic screen） | `62743963516784d790a3de82f920dfe5d097e0f30e3e41cc09d20b1ca1e00e67` |
| `recovery-gpu-streams.img` | `05e003312a45ab0b0e5745c6a53797776d4a784abd2271ac9be0777fb310a6e9` |

主机 ASan/UBSan 模型核对 CB1 守卫、带原厂高位的 FAULT 候选、寄存器漂移和空候选。设备仓库单测共 76 项，跳过 11 项。回读对比确认固件、DTB/DTBO、ADT、trust cache 和 Data 种子一致，保留 `t970-ufs-unixnu=1` 与 `sheng-data-persist=2`。

`.cache/heimdall/build/bin/heimdall flash --RECOVERY out/dual-system/gpu-streams-20261111/recovery-gpu-streams.img --no-reboot` 仅上传 `RECOVERY`，退出 0。回执在同目录的 `upload.log`，SHA-256 为 `494b1ad8b8e791d7ace23b484e57a4cb4a9ee977b61cafd0b47f5e1e13272ac0`。2026-11-14 [实机照片转录](device-result.json)确认槽 1–5 都是稳定的 FAULT 候选，GMU 保持槽 0，CP 空闲。
