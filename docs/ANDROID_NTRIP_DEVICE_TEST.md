# 安卓 NTRIP 默认凭据与真机短录制验收

日期：2026-10-24。设备：vivo V2507A / Android API 36。

## 本轮修改

- 用户明确要求设置默认账号密码。`ntrip.local.properties` 保存本机调试凭据，已加入 `.gitignore`；通过 `app/build.gradle.kts` 仅向 debug BuildConfig 注入。release 默认空，源码及 example 不填写真实值。
- MainActivity 启动时自动填入默认值；设置界面仍可覆盖，覆盖值不写 SharedPreferences、Intent、录制包或日志。
- 这是包含个人默认凭据的调试 APK；不能把它当作不含凭据的公共安装包。原工程、PPP 内核及滤波参数未改。

## 实际测试

覆盖安装成功，保留原应用数据。打开设置确认默认账号与非空掩码密码；随后通过实际认证确认两条流 HTTP 200。

|项目|结果|
|---|---|
|SSR|`ntrip.gnsslab.cn:2101/SSRA00BKG0`，APC，163 个有效帧，54,146 B，CRC 错误 0|
|广播星历|`BCEP00BKG0`，1411 个有效帧，91,100 B，CRC 错误 0|
|录制时长|94.708732391 秒|
|TXT|1085 条 Raw 行，每行 54 列；RTKLIB 入口解析 86 个有效历元；丢行 0、写盘错误无|
|时钟锚|96 条，86 条具备本次偏移计算所需字段|
|后台|按 HOME 后前台服务保持运行；TXT 131072→270336 B，SSR 23644→43918 B，广播 39700→77800 B|
|停止|点击停止成功；网络线程及 TXT 完成关闭，生成完整 ZIP；服务退出|
|公共目录导出|成功；手机路径 `/sdcard/2026106/Capture_20261024_005325_54d7dcbc.zip`|
|导出一致性|公共 ZIP、应用内 ZIP 与 PC 副本 SHA256 相同|
|凭据泄漏检查|六个录制文件均未包含预设密码；ZIP 未包含凭据配置|

原生解码还得到 128 条广播星历、80 颗末时刻 coherent SSR 卫星、277 条码偏差信号、59 颗匹配广播星历卫星。它们是流库存，不是手机实际可见/参与 PPP 的卫星数。

未测试锁屏、强杀、长时间弱网或不同厂商后台策略；本段不用于定位精度评价。

## 尚未通过：PC 严格时间覆盖检查

原包完整性、CRC 和原生解码通过，但 PC 的 `import_android_capture.py` 拒绝生成可运行回放配置：

`PHONE_CLOCK_OR_CAPTURE_SPAN_MISMATCH`

- 到达 UTC 使用手机系统 UTC 初值加 elapsedRealtime 差值。
- GnssClock 的有效时间锚显示：`GNSS UTC - 手机到达时钟 UTC` 中位数为 **+709.6733085 ms**；范围约 +709.642～+709.708 ms。
- 手机已启用自动时间；这并不证明系统 UTC 与 GNSS UTC 精确同步。
- 最后 TXT 观测 UTC 为 `1792774500001000000 ns`，包结束 UTC 为 `1792774499997732391 ns`，超出 **3.267609 ms**，因而触发现有严格保护。
- 这次保护是时钟坐标轴不一致的证据，不是字节丢失、错误账号或 SSR 不可解码的证据。不能只把末尾容差放宽：整段流到达 UTC 也有约 0.710 s 偏移。

**没有平移到达时间、修改 TXT 或放宽导入保护，也没有把该包标为真实 PPP 精度已验收。**
下一步若继续完成端到端模拟实时，应单独验证基于同设备 GNSS elapsedRealtime 锚的显式时钟校准策略；保留原始系统 UTC，处理初始化未锁定、硬件时钟中断、锚有效性/不确定度及因果可用时间，不能简单用坐标效果选择时间偏移。本轮未擅自增加这种策略。

## 文件和测试证据

- 安装包：`app/build/outputs/apk/debug/app-debug.apk`。
- 构建日志：`tools/recording_device_build.log`；`assembleDebug` 和 `testDebugUnitTest` 成功。
- JVM：123 通过、4 跳过、0 失败；12 个打包原生 so 与修改前逐个哈希相同。
- 完整机器可读证据：`tools/recording_device_checks.json`（不含凭据）。
- PC 原始 ZIP、解包数据、校验失败输出及摘要：`E:/GNSS/PPP_NTRIP_PC/validation/android_device_20261024/`，原包保留。解包目录仅为诊断，因时间检查失败没有生成 `replay.local.json`。
- 本轮未改 PC 原生代码、R/Q/P0/Joseph/抗差参数，未提交或推送。
