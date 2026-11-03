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
