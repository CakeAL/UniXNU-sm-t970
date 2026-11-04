# Wi-Fi 地址单因素对照

参考 [Poco F1 实机诊断](https://github.com/ry-diffusion/Bergamota/blob/37a7a7a917fc09945ed2f7d1ae68b84d4525b4cb/NOTES.md) 和其 [ADT 构造](https://github.com/ry-diffusion/Bergamota/blob/37a7a7a917fc09945ed2f7d1ae68b84d4525b4cb/tools/mkadt.py)：对已实测的 90 秒 BOOT `aeb13ffc…` 单独增加 `/chosen/mac-address-wifi0`，值为随机生成的6字节本地管理单播地址。此值是临时诊断输入，不是真实硬件地址，不启用或证明 Wi-Fi 功能；它与生成镜像仅存在忽略目录，不进入板级默认配置。只加 Wi-Fi 属性，不加蓝牙属性，以保持单变量。

`python3.14 evidence/display/wifi-address-control-v29/prepare.py` 直接从已实测基线的最终 BOOT 重新打包 FAT 内的 ADT；最终回读后逐节点核对只有该属性新增，内核、其他 ADT 属性、启动参数、trust cache、Data 种子以及非 payload 的 BOOT 字节不变。独立回读再次核对属性长度、地址类型和其他全部 ADT 属性，哈希见 `preparation.json`。私有输入、二进制 ADT 和镜像位于 `out/data-bringup/wifi-address-control-v29/`。

新 BOOT `fec656ec985544578036d2e7cc15c7a7a843191d6fa32920303f3b9b01e2c7eb` 继承相同8核/768 MiB、mode7 和90秒终止报告。比较 `aeb13ffc` 的 lsd/SpringBoard 栈及计数；每次都是全新启动，线程顺序和启动时间本来就可变化，单次正负结果都不能单独证明或排除具体 Wi-Fi 等待机制，也不证明桌面或联网可用。90秒可能仍早于首帧。机主授权 BOOT 上传及重启，Heimdall 显示上传成功、退出码0并请求重启，未设备读回；见 `upload.json` 和 `flash.log`。

## 实机对照

`screen-target90.jpg` 显示 main1、CPU8、SB27、BB57、lsd98，显示 open5、swap0；两个目标和结束标记完整。原始缓存 UUID 匹配的 `symbols.json` 显示：lsd 首线程仍在安装日志恢复的 dispatch 队列等待，lsd 第4线程经 XPC 等待数据库 seeding，SB 首线程等 BackBoard 主屏幕信息，均与无测试地址的 `aeb13ffc` 样本具有相同调用链（等待 seeding 的线程在基线是第3个）。这次 90 秒没有可见的阶段改善，两次均早于首帧。

这只是各一次、不同启动的快照；线程顺序和执行时机可变。属性在最终 FAT/ADT 中经回读确认，但未直接测量运行时是否读取；未观察到具体 Wi-Fi 查询，不能单独证明该路径已被测试地址改变，也不能完全排除后续效果。照片哈希和具体数值见 `device-result.json`。

主机通过 FAT 回读和独立 ADT 比较，`porting-record.py check` 另行执行；`check-platform.py` 因 UniXNU HEAD 与历史审阅 pin 不同，在 DT/ADT 检查前停止。实际固件、设备观察和持久 Data 不由这些检查证明。
