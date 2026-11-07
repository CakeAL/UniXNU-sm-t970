# v101：ARC 档位码

BOOT `12bf03ae172b38511c3d22ecab4acd2d5adbd13daaad07d8be31f6345fb45b88`。v100 已证明 `GPU arc` 行可打印（`cx=30000 lv=9 min=2
mx=30010 lv=9 min=2`），但没给出 9 个档位值。v101 只把档位码放进同一行：

```
GPU arc db=1 cx=30000 lv=9 [0,16,...] min=2 mx=30010 lv=9 [0,...] min=2
```

仍为只读：只解析 ARC cmd-db，不请求 RPMh、不碰 GPU/GMU 窗口。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork --keys --refresh-hid --output out/data-bringup/gpu-arc-v101-build
python3.14 evidence/gpu/arc-v101/prepare.py
python3.14 -m unittest discover -s tests -v
.cache/heimdall/build/bin/heimdall flash --BOOT out/data-bringup/gpu-arc-v101/boot-partition.img
```

## 待观察

三指报告里的 `GPU arc ... [档位列表] ...` 两段。拿到 9 个 CX/MX 档位码后，
与 T970 DT 的 GPU OPP（305–670 MHz，7 档）和电源域对照，制定 GPUCC/GDSC
只读资格确认的下一步。

## 实机结果

14:41:46 照片确认档位码：

```
GPU arc db=1 cx=30000 lv=9 [0,16,64,128,192,256,320,384,416] min=2
          mx=30010 lv=9 [0,16,128,192,224,256,320,384,416] min=2
```

CX/MX 各 9 个 RPMh 电压档位码；两者在索引 2 不同（64/128），MX 多一个
224；最低 SVS 索引都是 2。电池服务仍正常（`charge=kicked`、49 样本零错误），
但电流符号在 v100/v101 两次照片间从 +17968 µA 变成 -277343 µA，仍不稳定。
