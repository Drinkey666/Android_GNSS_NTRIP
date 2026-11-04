> 最新安装与真机状态：新版已成功安装，39历元留档和PC因果回放核验通过。见 [真机核验](ANDROID_VERIFIED_DEVICE_TEST.md)。以下未安装/安装被拒的说明为历史记录。

# 原始采集留档核验（2026-10-24）

## 可以确认的范围

代码在 PPP 筛选之前保存每条已接收的 Android measurement，不因 CN0、ADR 状态、卫星是否参与滤波而删除 Raw 行。当前 PPP/JNI 所需的公共时钟、卫星/信号标识、接收时间、ADR、伪距率及其状态/不确定度均有记录。伪距 P、载波 L、Doppler 由这些原始量重建，不把滤波结果冒充原始观测。

| 输入/证据 | 文件 |
|---|---|
| Android 原始测量、Time/FullBias/Bias/HCDC、State/ADR、频率/CodeType、CN0 等 | `RawData_*.txt` |
| 已收到的轨钟、广播星历和偏差原字节（包括 CRC 不通过的字节） | `ssr.rtcm3`、`broadcast.rtcm3`、`bias.rtcm3` |
| 每个接收块的 seq、时间、offset/length、断流与 reset | `arrivals.csv` |
| GnssClock 与 callback/elapsed 锚 | `clock_anchors.csv` |
| 实际处理历元、已应用流序号、处理状态 | `epochs.csv` |
| 实际选择的 IONEX、两期 VMF3、orography、ATX | `product_*` 与 `products.json`（加载前冻结） |
| 算法配置及诊断/结果 | `profile.txt`、`live.trace`、`corrections.csv`、`observations.csv`、`solutions.csv` 等 |
| 文件长度、SHA-256、掉行/写盘错误、流统计、停止原因 | `capture.json` |
| 新版安装包身份 | 本轮新增 `software.json`，记录版本、APK SHA-256、设备和 Raw schema，不记录凭据 |

最新代码的停止顺序保证已接纳的 Raw 回调完成其 Raw 行、时钟锚和 native 事件提交后，再关闭队列/排空 JNI/打包。注册前先开放已准备好的队列，避免首次即时回调被遗漏。未改 PPP 算法或产品策略。

## 已有真实包检查

位置：`E:/GNSS/PPP_NTRIP_PC/validation/android_live_whu_20261024/`。

| 包 | Raw 行/列 | 时钟锚 | 核对哈希文件数 | 掉行/写盘错误 | 三路 CRC |
|---|---:|---:|---:|---|---|
| `Capture_20261024_115517_eed0bd3e.zip` | 420 / 54 | 56 | 19 | 0 / 无 | 全部 0 |
| `Capture_20261024_120102_40e5a9ec.zip` | 317 / 54 | 47 | 20 | 0 / 无 | 全部 0 |

两个包均为正常 USER_STOP、complete=true，全部列明文件的长度与 SHA 匹配，没有记录到断流/写盘错误。第二包当前手机上的 SHA-256 为 `e9a616ad0600e10804fa27a4ebc21ab3e65b7ab430800c2ecb5508feb09c4f18`，与 PC 副本一致。旧手机包已经有原始流、时间索引、时钟锚、产品快照；新增 `software.json` 只在之后使用新版采集时出现。

**这些证据说明已保存内容未变且未报告队列掉行，不能证明芯片从未漏报历元，也不能补回网络从未收到的数据。**

## 本轮发现并修复的收尾风险

原 `GnssDataLogger.stopRecording()` 注销回调后立即关闭队列；在途回调仍可能继续序列化测量。原 service 在停止请求后也会跳过这类回调的 clock/solver observer，导致 Raw 与处理 ledger 收尾不一致的风险。

- 新增 `RawEventDrain.kt`：已接纳 event 与关闭队列使用同一排空屏障；关闭后拒绝后续 event，避免半个历元与 END 标记交叉。
- `GnssDataLogger.kt`：注册前开门，停止时先排空在途 event，再关闭并排空 IO 队列，避免上次 writer 还在排空时重启。
- `NtripCaptureService.kt`：已接纳 Raw event 的 observer 完成后才关闭 JNI；不再仅因较早的 stop flag 丢弃其时钟锚/ledger。另存 `software.json`。
- PC ZIP 导入白名单新增 `software.json`，仍须与 manifest 哈希匹配。

新增并发测试：停止等待完整 event、停止后不再接纳 event、异常回调不阻塞最终关闭。Android **131 项中 127 通过、4 跳过、0 失败**；PC Python **28 通过**。本轮未改 native 数学实现，无须重复 PPP 精度消融。

## 不能称为“所有手机原始信息”的部分

- 54 列包含预留空列，`IsFullTracking`、卫星 PVT/Klobuchar 预留列未填，不是 54 项都已获取。
- 当前不保存原始 RF/IQ、IMU、全部 NMEA 或手机 GNSS navigation-message 回调；广播星历来自已保存的 NTRIP 原流。
- 部分可选 API 字段没有上报就为空，ISB 辅助列沿用历史 -1 哨兵；这不影响当前 JNI 使用的输入，但不能当成未来所有新方法的无损输入格式。
- 队列满、磁盘错误、芯片未上报或网络断线不可能被“完整 ZIP”自动补齐。每次须同时检查 complete、掉行数、write_error、流覆盖、哈希和 ledger，而非仅看 ZIP 是否存在。
- 未成功选择/加载大气产品时，不会虚构完整产品快照，也不能称为可正常解算的数据集。

## 安装与真机验证状态

本轮 ADB 已恢复授权，且确认没有活动录制。覆盖安装返回 `INSTALL_FAILED_ABORTED: User rejected permissions`，因此没有继续安装/启动新采集。**新增排空保护已构建和单元测试，尚未完成新版真机短测。**

手机当前仍是旧 APK `d0407f82c0436d2d47c62dc0c8dc3351c8bfbb48516635c3e7c60c65444ed187`，未装入 WHU 专用策略和本轮收尾更新。

新 APK：`E:/android/test/PPP_NTRIP/app/build/outputs/apk/debug/app-debug.apk`，SHA-256 `8761a1492c4e15132da9c642819b323cf81d7569e020b24469eebdd1f8863e47`。此前 `aad3...` 是仅完成 WHU 策略时的历史构建，当前路径已被本轮更新取代。

结构化证据：`validation/whu_policy_20261024/capture_completeness_audit.json`；只读复核脚本 `tools/audit_saved_capture.py`。两份原始 ZIP、手机原始文件均保留，未清数据。
