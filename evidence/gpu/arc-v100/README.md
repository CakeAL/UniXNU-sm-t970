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
