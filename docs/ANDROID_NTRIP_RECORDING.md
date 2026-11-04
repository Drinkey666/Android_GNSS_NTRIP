# 安卓同步保存 TXT、SSR 与广播星历

更新：2026-10-24。独立工程 `E:/android/test/PPP_NTRIP`，包名 `com.example.pppntrip`，应用名 **PPP NTRIP**。

最新真机进度见 [默认凭据与真机测试](ANDROID_NTRIP_DEVICE_TEST.md)：用户授权的默认凭据已加入个人 debug APK，双流、TXT、后台、打包和导出已实测通过；PC 严格导入发现手机系统 UTC 与 GNSS UTC 相差约 0.710 秒，尚未通过回放时间检查。下文初始的“未授权/未真机验证”记录是前一版本的历史状态，以最新测试报告为准。

## 直接填写这两个挂载点

|设置|内容|
|---|---|
|Caster|`ntrip.gnsslab.cn`|
|端口|`2101`|
|改正数流|`SSRA00BKG0`|
|广播星历流|`BCEP00BKG0`|
|轨道参考点|**APC**|
|TLS|本次 2101 配置关闭|
|账号、密码|本机个人 debug APK 已按用户要求预填，仍可在 App 修改；不写录制包|

**改正数流**提供相对广播轨道的精密轨道、钟差和各信号码偏差。
**广播星历流**提供基础卫星星历。两条流配合手机自己的原始观测 TXT，才能在电脑形成完整 PPP 输入。
它们不是基站观测流，也不是手机定位坐标流。

上述两流在 2026-10-23 已由 PC 真实短录制、CRC 扫描与 RTKLIB 解码核验；这是已有证据，不等于已经做完本 APK 真机连续录制。
原 `SSRA00WHU0` 短样本没有码偏差；BKG1 的实际 IGS 版本 3 尚不在当前 PC 受保护解码器的支持范围，故不设为本轮默认。

## 手机怎么操作

1. 安装本工程 `app/build/outputs/apk/debug/app-debug.apk`。它与旧 FTPGet 使用不同包名，可共存。
2. 打开“记录”页顶部 **TXT＋NTRIP 同步录制**，进入“NTRIP 设置”，核对上表并输入账号密码。
3. 点击 **同步录制 TXT＋双流**，授予精确定位权限；允许通知后可在通知栏查看和停止。
4. 看两条流是否显示已连接、SSR 与广播 CRC 有效帧数是否持续增加。刚连接尚未齐备星历，采集时留出启动预热时间；完整 TXT 都会保留，不裁掉启动数据。
5. 测量完成点 **停止并保存**，等待 TXT 队列写完、两条网络线程退出和 ZIP 生成。
6. 点 **选择公共保存目录**，例如新建“内部存储 / PPP_Capture”文件夹；再点 **导出最近录制包（ZIP）**，把该 ZIP 拷到电脑。

不要只用旧的“开始采集”按钮：旧入口只录 TXT，不含本次双流包。
同步录制开启时会禁用旧单独采集、转换和 PPP 按钮，避免混淆会话。
本阶段手机的实时 PPP 按钮暂不启用：用户要求先在 PC 验证精度，而不是现在移植 SSR 解算算法。

录制不加载 JNI 求解器，不要求先下载 SP3、CLK、BIA、IONEX、VMF3。
大气与天线产品由电脑回放阶段准备；手机只采集和保存。

## 保存内容

应用内部：`Android/data/com.example.pppntrip/files/GNSS_NTRIP/Capture_日期时间_随机ID/`。
对应同名 ZIP 位于它的上一层。界面显示最近 ZIP 文件名，导出不会覆盖公共目录已有文件。

|文件|用途|
|---|---|
|`RawData_*.txt`|原有 54 列原始手机观测，不做信号筛除、不计算 PPP|
|`ssr.rtcm3`|改正数流原始字节，已去 HTTP 分块外壳|
|`broadcast.rtcm3`|广播星历流原始字节|
|`arrivals.csv`|每块数据的到达 UTC、开机单调时间、通道、偏移、长度、连接重置边界|
|`clock_anchors.csv`|GNSS Clock 与 elapsedRealtime 的原始对应关系，用于核对手机系统时钟|
|`capture.json`|配置、帧数、哈希、TXT 质量、结束原因；不含账号密码|

记录器保留原始数据，包括残帧和 CRC 不通过的字节；统计不会将这些字节伪装成有效帧。PC 解码时再做原有帧有效性检查。
不是只保存一个裸 RTCM 文件：到达时间索引是以后模拟实时、禁止提前使用未来改正所必需的。

## 电脑导入及回放

在 `E:/GNSS/PPP_NTRIP_PC` 中：

```powershell
.\import_android_capture.cmd E:\你的导出位置\Capture_某次录制.zip --out sessions\phone_01
```

导入目录必须不存在。工具先检查 ZIP 路径／容量、文件 SHA、TXT 丢行与写盘错误，再让 RTKLIB 原生 TXT 入口检查时段。
校验失败时不擅自修补记录；已解出的诊断文件和原 ZIP 保留，不覆盖旧会话。

成功后会生成 `sessions/phone_01/replay.local.json`，已自动填好本次 TXT 与双流目录。
在它的 products 中填入匹配时段的 IONEX、两个 VMF3 格网、orography、ANTEX 路径，再运行：

```powershell
.\replay_txt.cmd sessions\phone_01\replay.local.json --output output\phone_01_fast --mode fast
.\replay_txt.cmd sessions\phone_01\replay.local.json --output output\phone_01_1x --mode realtime
```

轨道、钟差、码偏差、广播星历取自这次录制，不填 SP3/CLK/BIA。
PC 仍按到达时间释放流，不全量预加载未来改正。参考坐标只用于后续误差曲线，不进入滤波。

## 时间与连续性边界

- 到达时间为手机系统 UTC 初值＋`elapsedRealtimeNanos` 差值；该单调时间包括休眠，不能使用休眠期间停止的 CPU uptime。
- 同时保存 GNSS Clock 原始时间锚。导入报告给出 GNSS 与手机系统时钟的偏移诊断，**不会静默移动时间轴**。
- 手机采集前应启用自动日期和时间。系统 UTC 是否准确仍需核对；单靠成功生成 ZIP 不能宣称严格实时精度已认证。
- 系统时间相对单调时钟跳变超过 0.5 秒会使包标为未完成；回放不会接受它为完整采集。
- 文件名按本地时间命名，观测历元由 GnssClock 确定。不要手动加 8 小时改动数据或索引。
- 当前限制为最多 30 分钟、双流 128 MiB、TXT 256 MiB；不会无限录制。
- 使用显式前台 location＋dataSync 服务和有超时的 WakeLock；进程被系统强杀时不自动用旧凭据续写。未完成文件留作诊断，不冒充完整包。
- 前台服务提升持续运行能力，但不同手机的后台／锁屏 GNSS 行为仍需现场验收，不保证所有 OEM 永不杀进程或每秒必有 Raw 回调。

## 实现与验证范围

- `NtripCaptureService.kt`：前台服务、通知停止、同步启动 TXT＋两个 NtripClient、容量／时长保护、排空及打包。
- `NtripCaptureStore.kt`：独立录流文件格式、CRC 统计、时间索引、哈希、ZIP；与 Android 求解器无耦合。
- `GnssDataLogger.kt`：增加可选输出目录和时钟观察回调，保留 Raw 字段、单位和转换规则；补充写盘错误／失败启动清理。
- `NtripClient.kt`：默认换为已验明的标准 RTCM APC 流，增加等待工作线程退出接口，防止关闭文件后仍有数据回调。
- `MainActivity.kt` 与 Material 3 界面：录制、停止、导出、CRC 帧数、两条流状态；账号密码仍只在进程内。
- `tools/import_android_capture.py`：PC 安全导入，使用已有 RTKLIB TXT 预检，无坐标调参或静默时间平移。

新增 5 个 JVM 录制器测试及 6 个跨语言 PC 导入测试；详见 `tools/recording_checks.json` 与 PC `validation/android_import_tests.log`。
JVM 样本 ZIP 是**合成传输夹具**，用于验证 Kotlin→ZIP→Python→RTKLIB TXT 入口，不能当真实 GNSS 数据或定位精度证据。
原生 `.so` 与修改前逐个哈希对照，不修改 R、Q、P0、Joseph、抗差、物理模型或 PC 解算内核。

初版交付时 USB 未授权，未进行真机验收。随后用户授权，已完成本机短录制、HOME后台、打包和公共目录导出；锁屏/长期连续性未验收，PC时间覆盖检查尚未通过。最新事实和证据见本文开头链接的真机报告。

依据：[Android 前台服务类型](https://developer.android.com/develop/background-work/services/fgs/service-types)、[GnssClock elapsedRealtime](https://developer.android.com/reference/android/location/GnssClock#getElapsedRealtimeNanos())。
