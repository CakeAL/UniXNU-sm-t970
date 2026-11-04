# 2 GiB owned window 对照

从 120 秒报告的 v60 BOOT `33abac1d…` 重新打包。v60 内嵌 ADT 的请求实际为 768 MiB。直接解包 v57–v59 得到的值仍是 768 MiB，且三份 ADT 均未通过结构解码。v61 的 ADT 能解码出 4 GiB，但该镜像的启动配置缺少原对照的显示、KeyStore 等参数，无法用来隔离内存变量。

```sh
python3.14 evidence/display/owned-window-2g-v62/prepare.py \
  --output out/data-bringup/owned-window-2g-v62
```

脚本验证基线 BOOT 哈希，按树结构定位 64 位属性，并独立比较解码前后的完整 ADT。再从最终 BOOT 提取 FAT，复核实际打包的 ADT、内核、启动参数、信任缓存及 Data 种子。Android v2 头、FD、固件 DTB 和分区尾部保持逐字节一致。生成文件留在忽略目录。证据见 `preparation.json` 和 `upload.json`。

## 120 秒参考截图

机主提供的 22:32:33 截图 SHA-256 为 `6841ca67384e9ad92e4c7605ac020d419a3924143d646fcdd475425559029cc2`。本轮没有该截图对应的上传回执，单列为参考。

- 启动：`main=1 cpu=8 sec=7 n=165 sb=27 bb=57 rb=26`。
- 内存：`pages=0x2b187 free=0x3cb`，约 689.5 MiB 受管理，与已实测的 768 MiB 档页数相同。free 是瞬时空闲页数。
- 存储：`blocks=1292955`。持久 Data 报告 `rc=0 bsize=4096 blocks=131072 free=26369`，可用约 103 MiB。
- 显示：GOP 已发布，成功交换、复制和退役各三次。发布时刻 20.367 秒，首个 CPU 复制时刻 114.231 秒，两者相差 93.864 秒。软件 vsync `start=1 arm=0`。未确认桌面。
- LaunchServices：采样时 `waits=0`，lsd 有三线程。一次采样无法判定后续是否发生锁争用。

v62 仍在 120 秒主动进入报告。首先用 `pages` 和启动阶段判断新窗口是否实际生效，再用首帧时间、UFS 计数和进程数作对照。Data 内容跨启动变化，单次结果只能给出趋势。持续进入锁屏或桌面需要随后单独测量。

## v62 实测

22:39:59 的 `screen-target120.jpg` 在上传 v62 后拍摄，报告的 `pages=0x79e30` 对应约 1,950.2 MiB 受管理内存。相比前一张参考图，进程 165→220，SpringBoard 线程 11→31，不可中断线程 169→4，UFS 验证块数 1,292,955→1,115,551，成功复制 3→4。首帧绝对时刻 114.231→126.532 秒，GOP 发布到首帧 93.864→93.587 秒。没有测得首帧提速。Data 可用 103.0→60.2 MiB，内容跨启动有变化；一次对照不足以把每项变化归因于内存。

LS 锁在本次有一次等待，仍是去滑移地址 `0x1f4884878`，等待方和持有方均非本页 SpringBoard S1/S2。软件 vsync 仍只启动，未见订阅触发定时器。机主确认 Apple 标志约 10 分钟后转黑发生于旧镜像。v62 在诊断时点主动停止，无法观察这段过程。持续启动接力见 [v63](../owned-window-2g-continuous-v63/README.md)。

同 build 的 dyld cache/local symbols UUID 校验通过。SpringBoard S1 和 lsd l1 的栈落在 CoreFoundation 的 Mach 端口运行循环；BackBoard b3 落在 QuartzCore 渲染服务线程，b4 在 IOMobileFramebuffer 的 `kern_SwapEnd` 经 IOKit 同步调用。快照无法确认 b4 等待时长或哪一帧卡住。完整地址见 `symbols.json`。
