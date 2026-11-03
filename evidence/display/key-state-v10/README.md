# 目录KeyStore状态服务接入

来源为`AppleKeyStoreState@42ff83e08b2265fe741d4adaf084bebe003452ba`，未修改组件源码；
板级注册依据T733 3bb0d6f和umi 3eb7257。仅显式`offline-key-events=1 sheng-aks=1`且
ADT ephemeral-storage=1时注册；已有原版类、错误环境、初始化/挂接/启动失败均拒绝或清理。
该目录组件只提供当前RAM fixture的状态/通知接口，不提供密钥、口令或数据保护操作。

通过`build-keystore-registration.py`在独立树运行目录命令
`build-arm-driver.py AppleKeyStoreState`；构建记录的依赖副文件重定向，原内核配方保持。
类初始化转为显式late调用；与T970显示回调、原版ABI绑定一起归档。
`component.json`、`archive.json`、`validation.json`和`preparation.json`记录输入及摘要。

主机检查：目录原有`test_closed_boundary.py`通过；实际板级注册ASan/UBSan检查覆盖
禁用参数、RAM属性缺失/大小/值错误、已有类、无provider、pre/post失败、分配/init/attach/start失败、
清理、重复初始化、计数和输出边界。`test_display_state.py`检查带新状态行的边界。
内核b1f7106a编译/预链接及独立FAT/FD/DTB/种子/命令行/八核准备通过。

BOOTb9cc7afb上传成功；机主target60照片确认stage4/meta0/ready1、open/refused/calls=1/0/1、
selector0返回0，main1/n69/cpu8/sec7；显示客户端与帧仍0。
这是接口接入成功，不是出画面证明。原版60秒镜像与内核保存在ignored输出，默认配置不变。
