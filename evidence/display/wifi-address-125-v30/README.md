# Wi-Fi 地址 125 秒单因素对照

90 秒的 Wi-Fi 地址对照和基线均在首帧前，尚未显示阶段改善。为比较已知首帧后的状态，从实机 BOOT `bb4d847476d455c0a49d28ffea03492e8e0f2b5fd0f2480ed2eb34dc5604912e` 制备本镜像 `c96f86d777d472b5e5905b9128bbd24945398129fc8698179fd6522cf0ec5af4`：只在独立 ADT 的 `/chosen` 增加一项随机6字节本地管理单播 Wi-Fi 测试地址，其他 ADT 属性、内核、trust cache、Data 种子、启动参数和非 payload 的 BOOT 字节保持一致。地址不是真实硬件身份，不表示已启用 Wi-Fi，也不写入板级默认配置；地址及二进制镜像仅保存在忽略目录。

它继承基线的八核、768 MiB 内存请求、`t970-ui-stack=1` 和 125 秒主动终止报告。基线照片在125秒有2次成功 swap/copy/retire，SpringBoard 处于 LaunchServices 调用链；本镜像可在相同诊断配置下比较，但独立启动的调度和状态仍可能不同，单次差异不能单独证明因果，且未直接测量测试地址的运行时读取。125秒从报告线程启动开始，不是上电计时。

运行 `python3.14 evidence/display/wifi-address-125-v30/prepare.py`，输出 `out/data-bringup/wifi-address-125-v30/`；最终 FAT 和独立解析比较确认仅新增一个六字节属性。详情见 `preparation.json`。机主授权后仅上传 BOOT，Heimdall 报告成功并请求重启，未设备读回；见 `upload.json` 和 `flash.log`。上次平台 DT/ADT 总检查因主仓库 HEAD 与历史审阅 pin 不同，在读取 DT/ADT 前退出。

## 实机结果

机主照片显示 main1、CPU8、SB27/BB57，open7、swap2/0、copy2、retire2，和无测试地址的125秒基线计数相同。原始缓存 UUID 匹配的 SpringBoard 符号显示，该次采样落在读取控制中心默认模块列表的 property list 路径；基线采样处于同一组件的 LaunchServices 应用查询路径。两个瞬时栈不同，但不能据此推断哪一次进度更靠后或证明地址导致变化；两次均没有主屏幕证据。90秒对照亦无明显阶段改善，因此不继续重复地址对照。照片哈希和边界见 `device-result.json`、`symbols.json`。
