# 根镜像部署修复准备

当前UFS实际读盘／GPT与一个非零128KiB系统样本匹配，14个调查读命令状态健康且重复一致。
但manifest、OS样本及其他区域为零，不能进入根卷挂载。原镜像内容不完整。

已修复分段编码器首个RAW块未seek的问题，保留全部原稀疏成品。
DONT_CARE跨多次刷写能否保留目标已有内容没有通过实机资格验证，故不再据此安排重刷。
Heimdall现有SendFile将文件大小存入unsigned int，直接传9.38GB原始镜像也不适用。

候选修复方式是独立的root ADB Recovery：不挂载userdata，通过ADB连续传输原始镜像，
写完同步，再从同一分区读回**整个镜像长度**并计算SHA256，与fd43ee70…核对。
这避开多段sparse内容保留假设。不是只检查上传回执或前几个块。

必须先确认Recovery确实提供root shell及dd／blockdev；三星原厂的sideload模式不能直接
当作支持任意root shell。当前电脑无ADB设备，尚不能完成运行时资格验证。

只读准备命令：

```sh
adb devices -l
python3.14 scripts/check-recovery-storage.py --serial <actual-serial> \
  --output out/step7/recovery-storage-readiness.json
```

若是原Android的已有Magisk shell，用`--su`，但数据分区必须未挂载才可能就绪。
检查限定SM-T970、原sda36、243668070400字节、4096块大小及无data／metadata挂载。
检查只读取信息，不会执行写入。通过检查也不等于获准覆写。
机主随后要求直接完成当前镜像刷写；现已启动BOOT临时root ADB并通过检查，按以下完整写回方案执行。

写回后仍需用现有UFS调查镜像验证manifest和系统样本，然后处理持久驱动与验证策略接入。
两份验证策略共73,287,008字节，主机zlib9测得68,794,405字节，压缩后仍不能与内核一起
放入68MiB BOOT。只压缩哈希表不能解决这一限制，后续不能直接启用空策略根发布。

## Odin 单包候选

机主希望用Odin写入。已准备单个`userdata.img.lz4`（LZ4 legacy）加入ustar，再追加MD5尾。
压缩只改变传输表示，不改变原始根镜像；打包脚本验证整份源SHA256、完整解压SHA256、
tar唯一成员及其字节摘要。它不使用分段sparse或DONT_CARE。

```sh
lz4 -l -1 <reviewed-userdata-root.img> out/step7/odin-userdata/userdata.img.lz4
python3.14 scripts/package-odin-userdata.py \
  --image ../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/userdata/userdata-root.img \
  --compressed out/step7/odin-userdata/userdata.img.lz4 \
  --output out/step7/odin-userdata/sm-t970-userdata-root.tar.md5
```

该包仅包含userdata.img.lz4，应选Odin的USERDATA栏；其余固件栏不填，不启用Re-Partition。
机主截图中ID:COM空，尚未有设备连接证据，不能据Odin窗口已经打开判断可刷。
推荐原生Windows的正常三星USB连接；Whisky下的大文件／USB支持没有资格验证。
即使Odin显示PASS，也必须完整读回或至少先运行既有UFS调查确认内容，不能沿用旧回执假设。
此处只准备包，没有通过Whisky／Odin写入设备。

## 连续写入与完整读回

```sh
python3.14 scripts/write-root-image-adb.py --serial <actual-serial> \
  --image ../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/userdata/userdata-root.img \
  --output out/step7/root-rewrite --write
```

源固定fd43ee70…、9,382,658,048字节。仅打开已核对的/dev/block/sda36，写后sync，
执行blockdev --flushbufs清理目标块缓存，再读取完整确切长度核对SHA256。
Recovery自带dd的iflag=direct会报EINVAL，已实际验证改用缓存清理＋count_bytes的通道。
任何写入、缓存清理、读取、长度或摘要错误都停止，不自动重试或挂载根卷。
