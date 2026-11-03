# 768MiB单因素对照与持续启动

`key-state-v10/prepare-memory768.py`从精确BOOTb9cc7afb只改ADT
`/chosen/darwinboot-memory-size`，512→768MiB。解码后只有该属性变化；
最终BOOT内FAT重新提取，内核、命令行、信任、种子逐字节相同。
原DTS低地址包络和全部保留区不变。现有DarwinBoot仅从EFI conventional memory调用AllocatePages；
这项请求不是将包络或保留洞声明为可用内存。BOOTf6fd6636上传成功。

机主target60照片确认main1/n69/cpu8/sec7，pages0x2b187（约689.5MiB），
KeyStore stage4/ready1/open1/call1，显示客户端与帧0。
扩容已生效，但free0x13b不能单独证明OOM或排除可回收页；没有观察到更早出画面。

`prepare-continuous.py`再仅移除定时报告、cache trace、spawn path诊断与UI非零退出陷阱参数；
BOOTec912b09的内核/ADT/信任/种子保持逐字节相同，独立FAT检查通过并上传成功。
机主报告持续仅有色条、未出新图形，未确认具体停止点或稳定性。
详细上传回执、照片和摘要随本目录保存；默认board仍为512MiB。
