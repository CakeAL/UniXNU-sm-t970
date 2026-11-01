# 根镜像只读样本核对

`t970-ufs-image=1` 先执行已通过的NOP、LUN0容量和完整GPT核验，然后检查
已经刷入的userdata镜像内容。没有新的存储写入，不发布IOKit根设备，不挂载文件系统。

固定7个样本各读2次：4096字节manifest，以及OS／SystemOS各自首部、中部、
接近尾部的128KiB。共14条额外READ(10)，每条最多1秒；任何读失败、状态异常
或SHA256不符立即停止，不重试样本。DMA及路由保留到重启。
末尾样本向下按4KiB对齐，避免超出组件实际数据；并非整个镜像哈希验证。

预期值来自与原USERDATA回执完全一致的源镜像 `fd43ee70…`，
见 `evidence/storage/ufs-image/expectations.json`。Kernel内常量在T970ImageTest.h，
检查脚本重新计算源镜像全文件与各个样本hash，并核对内核常量，不仅比较生成器输出。

```sh
python3.14 scripts/check-ufs-image-inputs.py \
  --image ../UniXNU/out/sm-t970/ipados-17.7.11-21H461/sm-t970/userdata/userdata-root.img \
  --output out/step7/ufs-image-input-check.json
```

预期标题 `T970 UFS root image readback`，成功条件success=1、reads=14、healthy=1、
poisoned=0、manifestAndSamples=1。失败时sample/name指出当前样本，observedSHA是
最后一次计算值；读命令失败时它可能属于前一次成功样本，须结合result/reads解读。

成功仅证明manifest和这些样本与源镜像一致、有限次较大读取完成，不代表9.38GB全部
内容均正确，不代表所有者签名策略通过，也不等于根卷可挂载。后续仍需持续驱动接管、
验证策略／体积限制及块设备发布／文件系统接入。
