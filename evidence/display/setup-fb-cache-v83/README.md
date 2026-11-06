# T970 扫描输出写合并与源表面缓存 v83

v82 的手动报告显示，传输页每帧仍拷贝整帧 19.6 MB：最后一次 `326897` us、最大 `331681` us，而改动区域只有 `366x176`。 v78 的差分拷贝只写变化的 64 字节块、仍要读整帧，实测与普通拷贝同速（143–285 ms），瓶颈在源表面读取。 v83 在 GopFramebuffer `cf3b429` 上应用 [补丁](../../../patches/gop/t970-fb-cache.patch)，用两个启动参数分别打开两条路径。 [v82 报告](../setup-transfer-v82/README.md) · [对象审计](../gop-fb-cache/object-check.json)

- `t970-fb-wc=1`：扫描输出映射由 `kIOMapInhibitCache` 改为 `kIOMapWriteCombineCache`。
- `t970-fb-cached=1`：源表面映射加 `kIOMapCopybackCache`，每次读取前对源执行 `flush_dcache64`，清理并失效到 PoC。
- 两个参数都不加时，对象行为与 `cf3b429` 相同，只多一个 `_flush_dcache64` 导入。

```sh
python3.14 evidence/display/hello-black-v64/build-kernel.py --cached-headers --setup-probe --gop-fork \
  --output out/data-bringup/setup-fb-cache-v83-build
python3.14 evidence/display/hello-black-v64/prepare.py --setup-fb-cache
```

宿主 54 项测试，44 项通过、10 项跳过。对象审计：全局符号 22 个且顺序不变，导入仅新增 `_flush_dcache64`；late 对象用 `llvm-objcopy` 去掉 `__mod_init_func` 并全局化静态初始化符号。内核预链接、原版 HID 绑定复核及最终 BOOT FAT 回读通过。BOOT 哈希为 `b739e1ca32ac6a6359611f5b85564048ce96d5804b3a35eb3716c251a52ea9bc`。Heimdall 确认上传并请求重启。实机结果待采集。

实机步骤与 v82 相同：走到「传输 App 与数据」并选择「不传输任何内容」，再按住三指约 2.5 秒；报告仍会打印 `copy us last/max` 与 `FB` 行。若拷贝降到几十毫秒以内，说明两条缓存路径都已生效。
