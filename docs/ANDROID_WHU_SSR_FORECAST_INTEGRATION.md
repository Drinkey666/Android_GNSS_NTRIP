> 后续更新：WHU独立OSB适配和北斗时间转换已完成，见 [本轮修复报告](WHU_OSB_COMPATIBILITY_FIX_REPORT.md)。新版APK已编译，但本轮ADB未授权，尚未安装。以下为此前首次接入时的历史状态。

# Android：WHU 实时流＋预报大气＋PC 因果回放

更新：2026-10-24。活动副本 `E:/android/test/PPP_NTRIP`；PC 副本 `E:/GNSS/PPP_NTRIP_PC`。

## 1. 交付状态

接入、前台生命周期、同事件 TXT 留档、产品快照、处理顺序记录及 PC 复核接口已实现并真机验证。**当前没有获得实时 PPP 解，也没有精度/收敛验收结论。** 按用户要求，只使用 WHU 精密轨钟/偏差；现有 WHU 独立 OSB 尚未通过通用 SSR 配套与时效检查，不启用滤波，不混用 BKG 精密改正。

- 精密轨钟：`ntrip.gnsslab.cn:2101/SSRC00WHU0`，CoM。
- 独立码/相位偏差：同 caster 的 `OSBC00WHU1`。当前实际收到标准 RTCM 消息；不能只根据挂载点末位猜格式。
- 广播星历：`BCEP00BKG0`，转发卫星原始广播参数，**不是 BKG 精密轨钟或偏差**。GLONASS 在 B_VERIFIED 中仍关闭。
- 电离层：CODE `COD0OPSP0D`～`P4D` 预报 IONEX；对流层：TU Wien `VMF3_FC`；ATX/orography 使用内置静态表。这里“WHU only”针对精密轨钟/偏差；没有声称大气文件来自 WHU。
- 求解内核固定 `B_VERIFIED_v2_JOSEPH`。未启用 Huber/eta 新算法，未改 R、Q、P0、GIM/抗差参数。

## 2. 手机使用

1. 打开已安装的 **PPP NTRIP**。确认 WHU 轨钟、偏差及广播挂载点。
2. 点 **准备预报大气文件**。仅准备预报 IONEX、VMF3 和静态表，不下载 SP3/CLK/离线 BIA。UTC H18 以后额外准备次日格网。VMF 凭据来自被忽略的本地配置。
3. 下载完成后点 **启动实时解算并留档**。按第一个有效 GNSS 时钟选择并冻结实际文件，JNI 再检查实际覆盖。缺失/过期不绕过；跨越格网右边界需结束会话并刷新产品。
4. 原始观测与三路流在前台服务中同步采集；界面会显示等待原因。`Q=6` 才是浮点 PPP，Q5 是单点，网络 200 或 RTCM 有帧均不等于 PPP 成功。当前实测只得到等待，没有 Q6。
5. 点 **停止并保存**，等待队列排空及 ZIP 完成，再点 **导出最近录制包** 到已授权公共目录。
6. WGS84 度分秒及椭球高参考设置仍只用于解后误差展示/CSV，未传入 JNI、初始化或产品选择。

个人 Debug APK 保留用户授权的默认凭据；凭据不写进 Intent、采集清单或录制 ZIP。不要把该个人 APK 当作无凭据公开发行包。

## 3. 解算与留档顺序

`GnssDataLogger` 的同一 `GnssMeasurementsEvent` 同时产生 54 列 Raw TXT 和解算事件；未另注册第二条求解回调。

`NtripCaptureService` 先在 gateway 内完成录流并取得 receipt，再将事件入单线程、有界 JNI 队列。解算、三路 feed 和 transport reset 串行。收到流但尚未初始化时不无限缓存字节；初始化后只读取已经排在该历元之前的录制前缀。断流丢弃未完成帧/批次，各 transport 保存自己的已完成快照，避免独立偏差的 provider 混进轨钟 decoder。

停止顺序：关闭三条 socket 并等线程结束 → 注销/排空 TXT → 排空 JNI 队列及 release → 关闭诊断 → 哈希、清单、ZIP。队列溢出或写盘失败停止会话，不静默丢历元继续声称完整回放。参考坐标只在解算完成后使用。

### V2 包内容

- `RawData_*.txt`：原始 Android 观测。
- `ssr.rtcm3`、`broadcast.rtcm3`、`bias.rtcm3`：三路原字节。
- `arrivals.csv`：全局 seq、原始接收 UTC、相对 elapsed、channel、offset/length、连接/reset 边界。
- `clock_anchors.csv`：FullBias/Bias/Leap/硬件中断、GNSS elapsed 与回调 elapsed，不改原始时钟。
- `epochs.csv`：GPST、callback/decision elapsed、**实际已应用的最后一个 arrival seq**、处理状态。
- `products.json` 与 `product_*`：实际使用的 IONEX、两期 VMF3、orography、ATX 只读快照与 SHA-256；`forecast_download_receipt.json` 在最终版中同时留档。
- `profile.txt`、`live.trace`、`corrections.csv`、`observations.csv`、`solutions.csv`、`position_errors.csv`：配置指纹、诊断、成功进入的观测及解算结果；没有解时结果 CSV 只有表头，不能虚构坐标。
- `capture.json`：字节数、SHA-256、掉行/写盘错误、流统计和停止原因。快照/下载收据证明本会话用过哪些文件及本机下载时间，**不独立证明服务器最早发布时间**。

单个 ATX 快照约 37.4 MB，当前完整 ZIP 约 5.5 MB。保留自包含最终 ZIP；验证过哈希后可整理本轮重复解压目录，不删除原始用户数据。会话仍受 30 min、流 128 MiB、TXT 256 MiB 和队列上限限制。

## 4. PC 回放与时间处理

在 `E:/GNSS/PPP_NTRIP_PC` 运行：

```powershell
.\build_pc.cmd --test
.\import_android_capture.cmd "D:\your\Capture_xxx.zip" --out "E:\GNSS\PPP_NTRIP_PC\sessions\phone_xxx"
.\replay_txt.cmd "E:\GNSS\PPP_NTRIP_PC\sessions\phone_xxx\replay.local.json" --output "E:\GNSS\PPP_NTRIP_PC\output\phone_xxx"
```

输出目录必须不存在。导入自动填入包内冻结产品的路径。`--mode realtime` 可按原始观测节奏重放；默认 fast 的改正因果顺序相同。

导入验证 ZIP 白名单/路径/大小、所有文件哈希、TXT 掉行、GNSS 时钟锚、epoch ledger 顺序。V2 以 ledger 的 applied_seq 释放原始流，校验 receipt.elapsed ≤ decision.elapsed，且 GPST 与对应原始 Clock 锚一致。不会把未来到达的改正提前应用，也不依赖手机 UTC 与 GNSS UTC 恰好相等。

V1 仍使用原来的严格 UTC/区间保护。旧真机包 GNSS 比手机 UTC 快约 0.71 s 的失败证据未抹掉或平移；本轮通过显式记录设备实际处理顺序解决新 V2 的回放问题。V2 若从未加载产品、缺 ledger 或不能关联 Clock，不宣称可复现成功更新。

## 5. 真机与 PC 证据

最终 APK SHA-256：`d0407f82c0436d2d47c62dc0c8dc3351c8bfbb48516635c3e7c60c65444ed187`。

设备 vivo V2507A/API36，USB 已授权；覆盖安装，无清数据。下载当天 `COD0OPSP1D_20262970000...INX.gz`、`VMF3_20261024.H00/H06/H12/H18` 成功。最终会话：

`E:/GNSS/PPP_NTRIP_PC/validation/android_live_whu_20261024/Capture_20261024_120102_40e5a9ec.zip`

| 项目 | 最终真机/回放结果 |
|---|---|
| 时长/有效 TXT 时间历元 | 46.597 s / 47 |
| 轨钟/广播/偏差帧 | 35 / 1658 / 69 |
| 三路 CRC 错误 | 0 / 0 / 0 |
| 广播星历记录 | 131（不等于手机解算卫星数） |
| 手机/PC GPST、applied_seq、状态一致 | 各 47/47 |
| PC 更新调用 / Q6 | 0 / 0 |
| 时间戳平移、参考坐标入滤波 | 均无 |
| ZIP 含本地密码 | 未检出 |

较早接入验证会话 56 历元也逐条一致；保留其 ZIP 与摘要，不拿它当独立定位精度验证。最终 APK 的服务停止、ZIP 和 PC 回放均已复核。手机系统 UTC 与 GNSS UTC 的偏差仍作为诊断保留，未被修改。

### 为什么目前不能启用 PPP

最终包中有 85 颗卫星具备三类消息，但 85 颗均不满足当前通用 SSR 组件 IOD 和来源一致性条件。轨钟 provider/solution 为 0/0；独立偏差为 1/1；偏差在包末参考时刻的年龄约 427.126～441.126 s，超过现有保守 90 s 保护。末时刻 coherent satellites 为 0。

这**不是已经证明 WHU OSB 产品错误或不能配套**。[WHU 在 IGS 的发布说明](https://lists.igs.org/pipermail/igsmail/2024/008420.html) 明确提到 OSBC00WHU1 基于 SSRC00WHU0、每 5 min 估计并以 5 s 流播。独立 OSB 的 numeric provider/IOD 未必应被当作同一轨钟解的字段；该说明也没有给出足以覆盖本次接入方式的年龄上限/参考基准规则。

因此当前没有修改 provider/IOD、重打时间戳、扩大 90 s 或混入其他中心偏差。**剩余阻塞是核实 WHU 独立 OSB 的配套规则、时效与当前转发流延迟**，然后才能实现有文档依据的 WHU 专用兼容策略。不能把旧通用保护未通过直接当作真实物理不兼容的证明。

## 6. 修改范围及回归

Android 新增 `LiveSsrSession.kt`，修改 `GnssDataLogger.kt`、`NtripCaptureService.kt`、`NtripCaptureStore.kt`、`NtripClient.kt`、`LivePppNative.kt`、`MainActivity.kt`、`ui/MainUiState.kt`、`ui/NtripSection.kt`、资源字符串和采集测试。

原生只改 JNI 边界及 `ntrip_ssr.{h,cpp}`：三路输入、明确接收时刻、帧重同步和 transport 隔离。Android 复用已存在的 PC 解码/CRC/版本/90 s 保护，不沿用旧安卓 2×UDI 的较短时效推断。所有改动均局限 NTRIP 副本。

PC 修改 `src/pc_ssr_replay.cpp`、`src/ntrip_ssr.{h,cpp}`、导入/配置/回放工具；新增 `tools/android_ledger.py` 和测试。未改 `core/`、`gnss_replay.c` 或 PPP 物理/滤波公式。新的 live 4 ABI `.so` 因边界修改而变化；其余 8 个 `.so` 未变。不能再引用旧“12 个 .so 均未变”的录制阶段结论。

- Android `assembleDebug` 成功；129 JVM 测试中 **125 通过、4 跳过、0 失败**（原有跳过保留）。
- PC 原生 **120 断言通过**：65 SSR、40 因果回放、15 NaN/协方差安全。
- PC Python **27 测试通过**。含锚错配、未来 receipt、重复 epoch、缺 ledger、旧 V1 时钟保护、ZIP/哈希/路径验证，以及本地三路 socket 录制。
- `verify_isolation.py`：原项目 50 项来源检查无源码/配置变化；SSR 宏关闭的 PPP/SPP/RTCM 预处理与机器码对比保持一致。Android 与 PC 的 PPP core 文件对本轮前快照均零改动。
- 没有重跑无关的历史 1200 期精度消融；没有提交或推送。

结构化证据：`tools/live_ssr_verification.json`；PC `validation/android_live_whu_20261024/final_comparison.json`、`final_replay/replay.json`。原始 ZIP、最终解压产品及日志应保留。

PC 独立录流也支持第三路偏差，新增默认 `config/caster_whu.json`；原 BKG 示例保留为历史显式配置，不再作为命令行默认。三路录制有本地 socket 回归；本轮真实三路同期录流来自手机。测试 caster 的 backlog 从 2 改为 8，避免 Windows 下三条并发本地连接触发 SYN 重试导致的测试假缺流；没有改正式网络/滤波参数。
