# v127 首启报告的栈修复

[v126 实测](../gmuboot-pf-v126/device-result.json)在报告线程里溢出内核栈：
故障链从 `native_t970_display_timing` 一直到 `A650GmuBuildRegions`，
帧合计约 12.8 KiB，叠加报告线程自身的 3.4 KiB 和线程入口后超过 16 KiB。
`far` 落在栈底保护页，`esr=0x96000047`（第 3 级翻译故障、写），
因此是真实的栈溢出而不是 SMMU 故障。

v127 保持模式 23 与 v126 相同的探测语义，只压缩这条链的栈：

- `pulseXoClocks`、`sampleGmu`、`sampleRsc`、`pulseGmuRate`、`pulseSmmuBus`
  改为把结果写入调用者持有的对象，不再各自保留一份快照；
- `stageGmuFirmware` 的 16 项 region/block/target 数组移到 BSS，
  每次进入显式清零 `targets`；
- 报告线程、`A650GmuBuildRegions`（UniXNU kit 固定提交）和其余结构不变。

按 v127 内核逐函数统计的帧和为 8,288 字节（v126 为 12,768），
释放约 4.4 KiB；报告线程仍保有约 4 KiB 余量。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-gmuboot-pf-v127-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-boot-pf-fix
python3.14 -m unittest discover -s tests
```

[镜像清单](preparation.json)和[刷写回执](upload.json)对应 BOOT
`9b6513f4350264f534e3157afe62260fa8d27fabf5fa060b8a77a5460f7a94e3`，
由 v125 BOOT `1cb79acc` 加模式 23 内核生成。Heimdall 确认上传并请求重启。
开机后三指报告应出现 `GPU boot` 行，随后是最多两行 `GPU pf` 故障记录。
