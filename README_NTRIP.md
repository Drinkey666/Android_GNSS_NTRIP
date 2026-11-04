# PPP NTRIP 安卓同步采集

当前用途：同步保存手机原始 TXT、SSR 改正数、广播星历与到达时间，导出 ZIP，在电脑模拟实时 PPP。

- 独立安装包：`app/build/outputs/apk/debug/app-debug.apk`，应用名 PPP NTRIP，包名 `com.example.pppntrip`。
- 完整操作说明：[安卓同步录制](docs/ANDROID_NTRIP_RECORDING.md)。
- 构建、测试及原生库一致性证据：`tools/recording_checks.json`。
- 默认 Caster：`ntrip.gnsslab.cn:2101`；SSR：`SSRA00BKG0`（APC）；广播星历：`BCEP00BKG0`。
- 在“记录”页点“同步录制 TXT＋双流”，结束点“停止并保存”，再导出最近录制包。
- 电脑导入：在 `E:\GNSS\PPP_NTRIP_PC` 运行 `import_android_capture.cmd ZIP路径 --out sessions\phone_01`。

不改原 PPP 模型、滤波参数和原生库。当前阶段不启用手机 SSR 实时解算。
安装包已编译、自动测试通过。2026-10-24 手机已授权，短录制、HOME后台采集、停止打包及公共目录导出通过；未测锁屏。
用户授权的默认账号密码仅通过被忽略的 `ntrip.local.properties` 注入个人 debug APK，release 默认空；不写入录制包。
PC严格导入发现系统UTC与GNSS UTC偏移约0.710秒，未改时间或放宽保护，不能宣称真实PPP回放已通过。见 [真机测试报告](docs/ANDROID_NTRIP_DEVICE_TEST.md)。
