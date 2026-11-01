# SM8250 UEFI UFS 移植计划（路线 B）

目标：让 Mu-Silicium 固件在启动 XNU 前完成 UFS 控制器/PHY 初始化，并为 XNU 留下可用的
SMMU stream（或由固件直接发布块设备），使 `ShengUfs` 能读到 userdata。

## 已就绪

- `scripts/gen-ufs-phy-tables.py` 从 Linux `phy-qcom-qmp-ufs.c` 提取 SM8250 QMP UFS PHY 表：
  SM8150 基础表（serdes 24、tx 6、rx 34、pcs 7、hs_b 1）+ SM8250 HS-G4 覆盖（tx 1、rx 21、pcs 2）。
- 生成的表在
  `package/firmware/Platforms/Samsung/gts7xlwifiPkg/Library/PlatformUfsLib/Sm8250UfsPhyTables.h`。

## 待实现

1. `PlatformUfsLib`（SM8250）：
   - `UfsBoardInit`：GCC UFS PHY BCR (0x77000) / GDSC (0x77004) / 分支时钟使能；
     PHY 复位释放；按表回放 serdes/tx/rx/pcs；等待 PCS ready 与 PLL lock。
   - `UfsCal*` 返回成功（SM8250 无三星校准流程）。
2. DSC/FDF 接入 Samsung `UfsDxe` + `UfsCalAdapterLib` + 新 `PlatformUfsLib`；
   需要确认 `UfsDxe` 不依赖 Exynos 专属的 `EFIChipInfo` 分支。
3. SMMU：ABL/TZ 掌管 stream 寄存器；固件需要
   - 复用 ABL 已配置的 UFS stream（若为 bypass），或
   - 通过 SCM 调用请求 TZ 配置 bypass stream（需要 Qualcomm 安全接口）。
4. 验证：UEFI 无控制台；先用 XNU panic 屏读共享内存或由固件把状态写入固定物理地址，
   再由 `arm_init` 诊断打印。
