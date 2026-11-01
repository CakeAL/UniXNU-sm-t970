# BOOT临时USB root ADB环境

机主已要求直接完成根镜像刷写。现有Heimdall的32位文件大小不能传完整包，Whisky未显示ID:COM，
故先资格验证临时ADB通道。仅覆盖BOOT，原RECOVERY和其他分区保持原样。

来源：官方LineageOS gts7xlwifi 20261029 recovery，SHA256固定于构建脚本和image.json。
原图86,888,448字节超过BOOT，不直接刷入。压缩原AArch64内核为gzip，保留原DTB／recovery DTBO，
重建v2 header及镜像ID；所得BOOT42,930,176字节。原内核解压和ramdisk往返已核验。
Qualcomm参考BootLinux支持gzip，但三星目标上的这条压缩路径尚需实机验证。

只修改ramdisk两文件：prop.default开启调试USB root ADB，init.rc禁用recovery服务，
避免菜单程序处理misc/BCB命令；设置已观测平台USB控制器并启动ADB。没有自动dd／format／刷写脚本。
不运行Recovery菜单，不挂载userdata。屏幕可能停留启动画面；成功判断是电脑实际检测ADB并通过只读检查。

构建：

```sh
python3.14 scripts/build-adb-rescue.py \
  --recovery out/step7/recovery-candidate/recovery.img \
  --output out/step7/recovery-candidate/adb-rescue-boot.img
```

先只验证设备、root shell、实际块设备与挂载状态。只有运行时检查通过后才连续传输完整原始镜像，
写后同步并读回完整长度核验SHA256。不再使用DONT_CARE分段，也不把上传成功当作镜像正确。
实机已通过gzip内核启动与root ADB；型号、分区和挂载检查通过，原厂Recovery已读出备份。
见evidence/storage/adb-rescue/device-result.json。尚未由该环境写入USERDATA。
