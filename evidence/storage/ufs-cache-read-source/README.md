# 读取错误来源诊断候选（未刷写）

机主对 BOOT6b04878c 的照片确认 csig stage171、.03 文件偏移0x2200000，
CDHash 与主机原件一致。见 `device-6b04878c.json`／`.jpg`。
候选加入 MAC-read201／VNOP_READ202 边界与首个 UFS 拒绝块的 index/LBA/hash-prefix，
仍返回原错误，不重读或重试放行。原始拒绝快照的诊断 helper 经 ASan/UBSan 检查，
9项现有状态测试通过，范围见 `design.json`／`verify-helper.py`。

内核88f716b0、BOOT097c4f8c 的稳定输入构建与 FAT/FD/容量检查通过。
该候选没有刷写：随后独立主机全表比较发现，旧策略签的是早先已知错误的 sparse 分段，
而平板已重写为正确完整根镜像。故停止此诊断刷写，先修复实际策略输入。
根因、完整验证与载体修复准备见 `../policy-carrier-repair/README.md`。
候选可作为修复后返回 XNU 的镜像，但实际启动结果仍待设备观察。
