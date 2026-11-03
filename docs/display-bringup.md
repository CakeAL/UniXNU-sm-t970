# T970显示接入

八核BOOT3da265b4已到launchd main，SpringBoard进程出现；尚无桌面证据。
当前两个显示后端CONFIG均关闭，GopFramebuffer未选入归档。

## 已完成的主机校验

`scripts/check-display-abi.py`使用原始iPad7,1 21H461 kernelcache和当前候选及其布局，
校验原始输入摘要、358个Legacy槽位的重定位/原生符号重绑定、9个抽象叶、7个完整IOSurface
getter及IOMobileGraphicsFamily完整代码段摘要。输出见evidence/display/abi21h461/audit.json。
不把宿主ABI检查当作服务发布或显示完成。

## 接入顺序

1. 生成经校验的Legacy头与原版符号绑定，用原XNU编译配方编译GopFramebuffer。
2. 提供T970注册与观测回调，检查真实PE_current_console几何2800×1752、stride11200、
   32bpp及既有scanout范围；正确清理失败路径，注册前确认IOSurface依赖。
3. 检查init/start、GOP映射与服务发布，再验证已知CPU帧、swap完成和IOSurface生命周期。
4. 最后验证用户态实际帧与桌面；面板亮度、触控、GPU单独推进。

## 对照来源

- [T733构建器](https://github.com/RigoLigoRLC/unixnu-sm-t733/blob/3bb0d6f7840f088db6a0ec88ecb841e12042422f/scripts/build-software-display.py)：
  原始Legacy构造函数定位与虚表绑定可参考；1600×2560几何、DPU和背光不可照搬。
- [共享显示组件](https://github.com/UniXNU/GopFramebuffer/tree/cf3b42979a9c44219e7bb149543e6fc3388b58ed)：
  本机隔离工作树.cache/gop-display，未修改默认组件或启用SM8550直接scanout。
- [显示适配指南](https://unixnu.com/porting/display)。

当前无新的显示BOOT产物或刷入；原八核诊断镜像仍保留。

## 实际对象编译

cf3b429的NativeLegacyDisplay.cpp已使用当前T970 XNU的IOPlatformExpert编译记录编译，
开启Wall/Wextra/Werror，通过；生成头采用上述sheng固定提交的头生成部分，抽象槽来自本机审计。
实际Mach-O重定位表确认恰好358槽、24个预期自有方法/抽象叶，无额外尾槽。
生成头、命令、来源摘要、对象摘要见evidence/display/abi21h461。
对象位于忽略输出out/data-bringup/display-object-cf3b429，尚未链接、未接注册回调、未刷入。
此结果只确认编译及静态虚表形状；运行时ABI调用、GOP映射与呈现待验证。

## T970注册回调

package/T970Display/DisplayRegistration.cpp基于固定T733注册流程，删除其DPU/密钥服务调用，
改为明确的t970-display-start=1启用；仅接受观测的0x9c000000、2800×1752、stride11200、
32bpp、rotation0。映射需具有有效VA、完全匹配PA及长度。继承原GOP CPU复制和完成逻辑，
板级回调负责登记观测与首帧交还控制台；未知后端接口仍会停止诊断。

scripts/build-display-registration.py用当前XNU配方编译并检查真实符号；固定已审计的GOP对象摘要，
板级native_legacy回调全部匹配，只留下9个需原版绑定的同前缀函数别名。
IOMobileFramebufferLegacy原版类方法和内核符号仍需最终绑定/链接核对，尚未生成归档或BOOT。
实际几何helper已通过2个有效断言和17个错误输入拒绝断言。失败清理代码尚未做API注入测试，
服务注册/映射/帧完成尚无实机结果。证据见evidence/display/registration-v1。

## 首次内核集成与检查镜像

link-display-archive.py生成经对象摘要绑定的late归档，移除GOP静态构造表、显式导出构造入口，
绑定原版Legacy方法与9个native_legacy别名。首次链接发现板级重复定义early_retires/failures，
删除板级定义后，内核链接与预链接成功：源0adf72f3，payload1f9ea7ae。

仅在忽略的sm-t970_data/.config启用LEGACY_DISPLAY，默认配置不动；之前内核/配置保存于
out/data-bringup/pre-display-v1。完整BOOT5e318d75为8核、目标60秒、显式显示加载/GOP/PM检查。
独立打包检查通过，原始信任/Data种子/FD/DTB保留。CPU-present/transfer未启用。
此轮runtime报告尚无专用显示发布计数，所以普通main1不单独证明显示注册成功。
下一步读取实际错误并加入显示状态采样，然后验证CPU帧传输和swap完成。
准备/上传与实机结果见evidence/display/integration-v2。

17:09:08实机：main1/n69/cpu8/sec7、SpringBoard27/runningboardd26、IOMFB_bics_daemon86；
未观察到backboardd。无专用显示计数，尚不能确认发布或呈现，下一版增加状态采样。

## 持续CPU呈现尝试（2026-11-03）

按机主要求，BOOTc39efc0f沿用0adf72f3/1f9ea7ae内核，八核，移除runtime终止参数，
启用transfer/validate/cpu-present/retire与sheng-vsync=60。该60Hz是软件通知请求，非面板实测。
原始信任、种子与固件保持，独立打包检查通过；具体上传结果见continuous-v1/upload.json。
运行到自然错误或持续呈现，未证明桌面成功。原有未实现抽象接口仍可能触发保护性panic。
显示状态报告草稿保存.cache/display-state-draft.patch，未编译进本镜像。

## 显示发布已实测（status-v3）

BOOT0854aff6的18:12:19照片确认stage8/meta0/surface0/mapped1/published1，
main1/n69/cpu8/sec7。这证明原版显示实例启动、IOSurface依赖、GOP映射和服务发布已通过。
状态行是尽力诊断快照，不把它当作CPU帧提交/复制/完成或桌面呈现证据。
backboardd此次未观察到，下一步采样客户端打开、swap验证、transfer/retirement。

对照[umi显示代码](https://github.com/reAAAq/UniXNU-umi/blob/3eb72578597d2ca16471b172d45eddc096a34a04/package/legacy-display/LegacyDisplayProbe.cpp)：
按真实IOBSD/IOSurface边界延后启动、分开记录init/probe/start，与当前T970注册顺序一致。
[umi说明](https://github.com/reAAAq/UniXNU-umi/blob/3eb72578597d2ca16471b172d45eddc096a34a04/README.md)
报告CPU复制到继承scanout可显示Hello；其板级内存、面板、触控参数不能直接移植。

## 客户端/帧链路采样（client-v4）

新增只读报告：client enter/open/fail、最后type/status、swap ok/bad及reason、
transfer次数/最后status、copies、retire和vsync通知次数。计数使用relaxed原子操作，
多字段为尽力快照，不是同步事务；不改变原返回、授权、提交或完成逻辑。
实际计数/格式化代码通过ASan主机测试：0/1/16/384长度、空指针、计数和关键字段。

同八核/60秒/CPU呈现配置，新源b81e0783已构建/预链接与独立打包校验通过，
证据见evidence/display/client-v4，具体BOOT摘要及上传见其preparation/upload。

- enter=0：尚未观察到显示客户端打开，不能直接归因于帧复制或面板。
- enter>0且fail>0：按status定位原版客户端创建失败。
- open>0但swap=0：继续查用户态合成、backboardd和提交链路。
- bad>0或transfer失败：按reason/status定位表面格式/尺寸/映射或复制。
- retire>0仍无正确画面：再检查实际像素、scanout布局与所有权。
