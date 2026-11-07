# v100：1280 字节报告缓冲下的 GPU ARC 探针

BOOT `1e1b1936adebdc9f1fe1b4407ce54958aeebf7c85f4a7c03790db19d86852a2c`。v99 的 `GPU arc` 行没有出现，原因是共享的
`display_state[896]` 被 display/UI/Data-space 文本和新增的 battery 行占满，
`Keys` 行在 `pon=1` 处截断；探测代码本身已链接。v100 只把
`display_state` 扩到 1280 字节（`patches/xnu/t970-report-buffer.patch`），
ARC 探测、启动参数和其余内容不变。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/gpu-arc-v100-build
python3.14 evidence/gpu/arc-v100/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/gpu-arc-v100/boot-partition.img
```

## 待观察

三指报告应同时包含完整的 `Keys` 行和 `GPU arc db= cx= lv= min= mx= lv= min=`
行。若 `GPU arc` 是 `refused`，把该行发来；若正常，下一步对照 T970 DT 的
GPU OPP/电源域，然后做 GPUCC/GDSC 只读资格确认。

## 实机结果

14:33:00 照片确认缓冲修复生效：完整 `Keys` 行和
`GPU arc db=1 cx=30000 lv=9 min=2 mx=30010 lv=9 min=2` 同时出现。

- 解析器找到 CX/MX 两个资源，各有 9 个电压档，最低 SVS 档索引都是 2；
  `0x30000/0x30010` 是 RPMh ARC 资源选择符，不是内存地址。
- 行里还没有档位数值本身；下一步把 9 个 level 码打出来，再与 T970 DT 的
  GPU OPP/电源域对照，之后才做 GPUCC/GDSC 资格确认。
- 电池服务正常：64.16%、3960312 µV、+17968 µA（充电）、`charge=kicked`、
  56 样本零错误；本次电流符号与 CHG_DTLS=1 一致，但幅度偏小，仍需单独核对。
