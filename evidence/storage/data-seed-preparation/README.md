# 可写Data种子：主机准备，未接入设备

复用固定框架的prepare-owner-data-fixture.py，以原始21H461 launchd哈希为输入门禁，
从原OS的private/var复制39份文件、611715字节，保留符号链接及模式，排除staged_system_apps，
添加运行目录。新建32MiB APFS容器，仅操作忽略目录中的主机文件；没有写平板USERDATA。

命令：
```
python3.14 ../UniXNU/scripts/prepare-owner-data-fixture.py --output out/step7/data-seed-base
python3.14 ../UniXNU/drivers/DarwinBoot/Test/packed_ramdisk.py out/step7/data-seed-base/owner-data-32.cdr out/step7/data-seed-base/owner-data-32.dbr
```

seed.json记录新卷UUID和原始容器摘要；packed.json记录DBRDISK1摘要及1007696字节编码大小。
框架打包器校验完整解码逻辑内容SHA256等于原容器0bef4684，主机格式化后已正常卸载。
32MiB是最小挂载接入输入，不是满足完整iPadOS运行容量的声明。

尚须选择catalog RamBlock@25c57e0e、集成archive与personality、启用OWNER_DATA_MOUNT、
绑定这个Data卷UUID并将packed seed置入payload与ADT，随后验证实机APFS识别、挂载及读写。
现有正常和512MiB镜像都没有RamBlock/Data，不能仅复制种子文件就称已接入。
首次可用RAM Data的更改只在内存中生效，持久化要另行限定UFS写入窗口并核验范围。
大于2GiB逻辑种子在现有驱动中必须使用持久后端，因此不直接套用T733的96GiB配置。
seed不会创建机主keybag、Apple用户记录或宣称生产存储已验证。
