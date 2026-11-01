# 根镜像内容调查（只读）

同一参数 `t970-ufs-image=1` 的调查版，仍先核对NOP与GPT。其源码与镜像hash区别于
此前严格首个不符即停的版本；旧结果不改变。

对原7个样本各读2次，内容与源镜像不同仍继续，传输失败、保护状态变化或两次内容不同立即停。
显示实际SHA256及3个mask：matchMask表示两次均匹配预期，repeatMask表示两次内容摘要一致，
zeroMask表示两次返回的所有字节均零。bit0=manifest，bit1..3=OS首／中／尾，bit4..6=SystemOS首／中／尾。
`completed=1 reads=14`只表示调查完毕；只有matched=1且matchMask=7f才表示所有样本匹配。

调查仍不写存储、不发布根设备。不把全零／不符直接归因于SMMU／DMA；此前GPT与命令状态均通过。
历史分段编码错误已单独修复并保留旧成品与审计，新版不能证明旧USERDATA已经正确。
