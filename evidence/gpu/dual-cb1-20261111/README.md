# 双系统 RECOVERY CB1 探针

沿用已实测的持久化 Recovery `33efcec0915129321995cd4de57a3223f7fd41e36c8f73205f07fa97e7aeaeba` 及其内核 `27580df10046882d3015915eda2549ac1ff475435c0c7beeb0f6c51feb45364b`。该内核已包含 v137 模式 33。以设备 `346f4c7` 和框架 `404572cfc431f0b259cd190a99ad5b2c881a074a` 为基线，重新打包后核对全部 FAT 文件和 FAT 之外的镜像字节。保留 `t970-ufs-unixnu=1` 和 `sheng-data-persist=2`，将 `t970-data-space=1` 换成 `t970-gpu-p=33`，更新 Android boot ID。

```sh
python3.14 scripts/pack-dual-data-recovery.py \
  --base out/dual-system/boot-candidate/recovery-stock-dtbo.img \
  --kernel out/dual-system/data-persistence-20261111/kernel.macho \
  --mode 2 --gpu-cb1 \
  --output out/dual-system/gpu-cb1-20261111/recovery-gpu-cb1.img
.cache/heimdall/build/bin/heimdall flash --RECOVERY \
  out/dual-system/gpu-cb1-20261111/recovery-gpu-cb1.img --no-reboot
```

镜像 SHA-256 为 `3413470c351a19e728e8d050dfe47055b826af1f2f9e5e691b312b8343e7f674`。Heimdall 退出 0，`RECOVERY upload successful`，仅上传 `RECOVERY`。本机回执 `out/dual-system/gpu-cb1-20261111/upload.log` 的 SHA-256 为 `494b1ad8b8e791d7ace23b484e57a4cb4a9ee977b61cafd0b47f5e1e13272ac0`。

v137 的 ASan/UBSan MMIO 测试通过，覆盖 ASID 2 同步、SID5 守卫、撤销和不确定状态。设备仓库单测共 76 项，跳过 11 项。按固定 AdrenoPM4 源码 `282606b528b2595bc4274ea7490b62b323f35a5f` 重跑 PM4 结构测试，ASan/UBSan 通过，iOS 17 交叉编译的对象无未定义导入。AdrenoMetal `ce5e19e33e05e1873d38d818e23cabfe0ac708c3` 的 `NativeBridgeMetalFrontend.mm` 以 `arm64-apple-ios17.0` 编译通过。主机输出均位于 `out/dual-system/gpu-cb1-20261111`。

以只读方式挂载 21H461 的 OS 和 SystemOS 镜像，使用现有 `audit-target-metal-discovery.py` 审计对应内核、AGX 插件描述和真实 dyld 缓存。仅替换脚本输入输出路径。检查通过，见 [静态发现接口记录](metal-discovery.json)。

实机三指报告显示 `GPU cb1ctx ok/ok tlb=3/2 ctl=a7/a6 f=400/400 leaf=17 held=1`。CB1 启停回读和两次 ASID 2 同步通过。CP 保持空闲，GPU streams 保持未发布。见[照片转录](device-result.json)。
