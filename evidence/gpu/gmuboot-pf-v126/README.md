# v126 GMU 首启权限故障诊断

[v125 实测](../gmuboot-axi-v125/device-result.json)把 DDR AXI 从 `80100000`
开到 `00100001`，发布 SID5、装载固件并释放 CM3，但 `FW_INIT` 没有出现。
CB0 FSR 为 `0x40000408`：按
[Linux arm-smmu 的 SMMU-500 定义](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/tree/drivers/iommu/arm/arm-smmu/arm-smmu.h)，
`0x400` 是 AArch64 的 Format 字段，位 3 是 permission fault（PF），
位 30 是 stream stalled（SS）。GFSR 为 0，11 个配置回读一致，AO/CM3
致命位均为 0，因此首个 GMU 总线访问已被翻译但被叶权限拒绝。

v126 在新的 opt-in 模式 23 中保留 v125 的全部前提，只在首启轮询里处理
该故障：

1. 故障出现时读 CB0 FSR、FAR（64 位）、FSYNR0 和 CBFRSYNRA0，记下
   第几个轮询、读写或取指方向、特权级和 SID；
2. 仅当故障是 permission fault、不是页表走查故障（FSYNR0 位 10）时，
   用故障地址定位本探针建立的那张 4 KiB 叶，核对叶的物理地址与已审计
   的五个窗口一致后，只放宽故障所指的那一位：置 AF、清 AP[2]（可写）、
   按 PNU 设置 AP[1]、仅对取指清 XN；
3. 清理该页的 CPU 缓存行，按已拥有的 ASID 执行 TLBIASID 和 TLBSYNC，
   清除 stall 的 FSR，再用 CB0_RESUME 重试该事务；
4. 同一地址、页表走查故障、非权限故障、非叶描述符、窗口外的页和三次
   以上的故障都不再修补，只记录并终止 stall 的事务。

报告在 `GPU boot` 行后追加最多两行：

`GPU pf1 fsr=40000408 far=... syn=... sid=... pte=前/后 fix=方向特权 rs=1`

`fix` 的第一字符为 `r/w/x`（读/写/取指），第二字符为 `p/u`
（特权/非特权）；`rs=1` 表示已重试。若修补后 `FW_INIT` 到 `0x100`，
主行的 `fw` 变为 `100` 并继续 HFI 就绪轮询。所有失败路径仍保留
SID5 路由、页表和上游时钟到重启。

## 构建与刷写

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --gpu-soc .cache/git-sources/sm8250-166235ec2480 --arm-smmu4k ../UniXNU/kits/ArmSmmu4K --gmu-firmware .cache/firmware/gpu-candidates/linux-firmware-20260221-a650_gmu.bin --output out/data-bringup/gpu-gmuboot-pf-v126-build
python3.14 evidence/gpu/power-v104/prepare.py --gmu-boot-pf
python3.14 -m unittest discover -s tests
```

## 构建与刷写

[镜像清单](preparation.json)和[刷写回执](upload.json)对应 BOOT
`986ddf4bc7dfb188bc6048670079d0c0dedb9f9e1ccf2e0d622952205c9855e2`
（由 v125 BOOT `1cb79acc` 加模式 23 内核生成）。Heimdall 确认上传并请求重启。
[主机验证](host-validation.json)含 FSR 分类、叶走查边界、单属性修补模型、
封印固件回读和独立 DTS/ADT 检查；完整平台检查停在历史框架版本校验。
实机报告待取回。

`rs=1` 表示已重试该事务；若 `fw` 仍为 0，第二行 `GPU pf2` 会说明第二次
被拒的地址或 `fix=t-`（页表走查故障、非叶/范围外页或三次尝试用尽）。
