# EDGE与SMP拓扑并发额度兼容修复

v20照片02:38:12：MG/BB/SB constrained cached cap=0，而active/busy=0/0，且idle>0、req>0。
MG done35→37、last-call age重置，说明不是所有工作队列回调停止。BB/SB受限请求无法通过额度判断。
原workq_open将qos_max_parallelism结果一次缓存；constrained_allowance要求cap>active+busy。

已核对最终v20 ADT：八核均缺cluster-type，machine_routines.c把这种节点登记为CLUSTER_TYPE_SMP。
已核对最终链接代码：qos_max_parallelism使用sched_edge_dispatch，EDGE只统计E/P CPU和cluster，忽略SMP。
由上述输入可解释cap0；不是从队列静止猜测。prior-adt-topology.json不包含身份种子。

patches/xnu/t970-edge-smp-parallelism.patch在BCM2837兼容构建下，仅在E/P CPU计数都0且SMP非0时，
返回实际SMP CPU数量；共享cluster选项返回实际SMP cluster数量。原E/P与非BCM路径保留。
板级patch先隔离验证，通用SMP兼容逻辑后续应随证据提交共享XNU补丁集；没有改共享SoC资源或CPU驱动。
这修正当前移植的同构拓扑计数，不是把SM8250真实异构核心伪装成E/P，也不宣称完成能效策略。

scripts/check-smp-parallelism.py提取官方prepare后实际函数，ASan/UBSan运行两种编译guard，
每种56个QoS/options组合，覆盖SMP1/8、E/P优先及不存在CPU时0。
真实内核编译/预链接通过，linked-width-disassembly.txt确认最终代码含调用SMP计数的分支；
prepared签名包含新patch摘要。独立payload检查、八核和768MiB变换及FAT往返通过。
旧BOOT/内核均保留。仅改变这条kernel逻辑；mode6/90秒、其余显示参数与v20相同。
平台总检查的旧review版本差异限制仍在；未额外声称全平台通过。

实机验证待回报：cap应从0变为实际拓扑CPU数；观察req/done、HID初始化及显示swap。
即使队列恢复也可能暴露下一层依赖，不能把此修复作为桌面已能显示的证据。

上传回执：Heimdall BOOT成功，exit0并请求重启，未做设备分区哈希读回；见upload.json。
