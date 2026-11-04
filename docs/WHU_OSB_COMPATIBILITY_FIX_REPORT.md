> 最新安装与真机状态：新版已成功安装，39历元留档和PC因果回放核验通过。见 [真机核验](ANDROID_VERIFIED_DEVICE_TEST.md)。以下未安装/安装被拒的说明为历史记录。

> 后续留档核验及安装状态见 [原始数据完整性核验](CAPTURE_DATA_COMPLETENESS_AUDIT.md)。当前APK已因收尾保护更新，USB已授权，但覆盖安装被手机拒绝。以下构建哈希/安装状态为本轮WHU修复时的历史记录。

# WHU 独立 OSB 接入修复与验证

日期：2026-10-24。仅修改 `PPP_NTRIP_PC` / `PPP_NTRIP` 副本；未提交、推送或改动原 `PPP_only` / `FTPGet`。

## 结论与当前状态

1. 修复一个**确定的时间解码错误**：本副本底层 RTKLIB 将标准 RTCM 北斗 SSR 的 BDT 周内秒当成 GPST，遗漏 14 秒转换。修复位于 NTRIP 接入边界，原始录流不改写。
2. 实现显式 `WHU_OSB_CONTINUITY_V1`，允许官方声明配套的 WHU 独立轨钟/OSB 使用各自来源与配置编号，分别管理估计时间和接收时间；不能把此策略理解为取消全部时效检查。
3. 360 秒真实 WHU 录流通过产品级验证：约 161.280 秒看到下一次估计并解除等待，最多 74 颗 G/E/C 卫星的改正集合通过该接入策略。**不是 74 颗手机可见/实际参与定位卫星，更不是定位精度验证。**
4. 安卓已完成四 ABI 构建及 JVM 回归。当前 ADB 重新显示 `unauthorized`，**本轮新 APK 尚未安装，未验证新的手机 PPP 出解**。此前手机仍是旧版本，不能说它已经使用本修复。

## 一、已证实的错误：RTCM 北斗时间尺度

底层来源：`core/rtcm3.c::decode_ssr_epoch()`（约 1442 行）对所有非 GLONASS 标准 RTCM SSR 直接 `adjweek(rtcm,tow)`。北斗 DF465 应为 BDT，而 IGS 4076 各星座使用 GPST。该差异也在 [BNC 官方说明的 SSR epoch times](https://software.rtcm-ntrip.org/export/HEAD/ntrip/trunk/BNC/src/bnchelp.html) 中说明。

现有原始帧证据（同一次更新）：

| 消息 | 原始周内秒 | 应解释为 GPST |
|---|---:|---:|
| GPS 1060 | 531550 | 531550 |
| 北斗 1261 | 531536（BDT） | 531550 |
| GPS 1059 码偏差 | 531000 | 531000 |
| 北斗 1260 码偏差 | 530986（BDT） | 531000 |

旧解码后北斗 t0 早 14 秒，会影响轨道漂移率/钟差多项式计算和时效判定。不能把这一差异当作真实网络延迟。

**修复**：`src/ntrip_ssr.cpp::feed()` 在 CRC 验证和解码后，仅对标准 RTCM 1258～1263 本帧刚写入的北斗分量调用 `bdt2gpst()`；同时统一 decoder 的已解码时刻。轨道/钟差/高率钟差/URA/码偏差按消息类型分别处理，不把旧 multipart 分量再次转换。IGS 4076 不进入此分支。Android 同步完全相同的 helper。

这是时间尺度转换，未更改原始字节、SSR 数值、IOD 或 provider，不是为了让过期产品变新而重打时间戳。底层 PPP core 文件保持原样，修复局限实时流适配器。单测覆盖标准北斗轨钟与码偏差、重复发送、IGS 北斗不重复转换，以及 BDT 周末到下一 GPS 周的边界。

## 二、独立 OSB 的处理依据与设计选择

[WHU/IGS 发布说明](https://lists.igs.org/pipermail/igsmail/2024/008420.html) 指明 `OSBC00WHU1` 基于 `SSRC00WHU0`、CoM、每 300 秒估计、5 秒播发。[IGS 产品说明](https://igs.org/rts/products/) 的正文也给出该配套关系；其表格另出现 `SSRC99WHU0`，本轮没有据此擅自更换挂载点。BNC 的 epoch 时间检查说明指出偏差可能携带最后更新时间，不能从其与轨钟的时间差直接推断网络断流。该说明**不等于偏差可以无限沿用**。

当前流实测轨钟 provider/solution 为 0/0、IOD 0；OSB 为 1/1、IOD 5。数字是实测证据，不作为所有时期都不变的官方编号。新策略根据明确产品配套关联两条流，分别锁定各自会话内来源和配置；不再要求独立流的编号逐数相等。

### 策略规则

| 项目 | 行为 |
|---|---|
| 启用入口 | 显式 WHU profile；配套挂载点为 SSRC00WHU0 / OSBC00WHU1，且使用 CoM |
| 轨钟 | 同源、同解、同 IOD；保留原 90 秒上限与未来时间保护 |
| 广播星历 | 原有 IODE、健康、轨钟幅值和 satpos 检查保留 |
| ANTEX / 信号 | 原有频率参考与天线检查保留；没有对应码偏差的信号仍不放行，零偏差必须有 valid 标志 |
| 偏差首次启动 | 至少观察到该卫星相邻两次、估计标签相差 300 秒的完整估计；同一旧版本重复发送不能解除等待 |
| 偏差接收中断 | 最近完整码偏差接收超过 90 秒，不放行；transport reset 清除连续性资格，重新启动核验 |
| 偏差不推进 | 允许最近已核验解在等待下一版期间保持；自上次估计推进的接收时刻超过 300+5 秒仍不推进，停止放行。反复收到旧字节不刷新此时钟 |
| 新解恢复 | 新的相邻估计到达、来源和接收连续性仍满足时，可恢复；不重置全部 PPP 状态 |
| 来源/配置变化 | 任一流 provider/solution 或配置 IOD 改变即停止本次解算，要求新会话；不把广播星历 IODE 正常变化误当配置改变 |
| 非法时间 | 偏差估计回退、未来偏差、接收 UTC 与 GNSS 明显不一致分别输出可追踪原因 |

**300+5 秒是依据公开估计/播发频率设计的工程更新看门狗，不是 WHU 官方承诺的绝对 OSB 有效期。** 本轮没有找到这样的绝对有效期声明，也没有伪称已找到。新策略采用“已观察到活跃的相邻估计、有限接收中断、停止推进即停用”的运行规则，仍信任所选服务正在提供当前解；它不能独立证明服务方所有偏差值的物理正确性。没有将 `90` 简单改为 `600/900`。

偏差估计标签、最近接收时刻、估计推进时刻分别保存，原始时间全部留档。接收时效仍要求手机 UTC 和 GNSS 时间基本一致；新 `WHU_RECEIPT_CLOCK_MISMATCH` 不做静默移时。V2 applied_seq / elapsed 回放链保持不变。

相位 OSB 未加入滤波，也未做 PPP-AR。原始 1265/1267/1270 继续留档。已见到一致性指示值，但不能据此声称已独立验证电离层物理基准/GIM 与所有相位模型完全一致；这些不在本轮调参或修改范围内。

## 三、真实录流结果

数据：`validation/whu_policy_20261024/continuity_capture/`，360 秒，有界录流；三路帧数 287 / 11812 / 496，CRC 错误均 0，广播流有一次断线并重连。此次录流专门验证偏差估计推进，不是重复验证账号是否能连接。没有同一时段新手机 TXT，未混用旧日期/旧时段观测。

| 指标 | 原通用策略 | WHU 策略＋北斗时间修复 |
|---|---:|---:|
| 首次通过接入检查的相对时刻 | 无 | 161.280129 s |
| 全段最多通过的 GPS/Galileo/北斗集合 | 0 | 74 |
| 包末通过的集合（含 GLONASS，仅 inventory） | 0 | 90 |
| 包末三组件均存在的卫星数 | 103 | 103 |
| GPS 码偏差版本数 | 2 | 2 |
| 会话被来源/配置变化阻断 | 否 | 否 |
| 包末偏差标签年龄范围 | 516.60～530.60 s（旧北斗解释） | 516.599986 s（统一 GPST） |

`matching_broadcast_satellites=55` 仅是 inventory 的广播匹配探测，未检查手机观测几何或 ANTEX；不是解算卫星数。B_VERIFIED 的 GLONASS 仍关闭。实际放行还需通过 ANTEX、信号映射及有效观测等检查，至少 4 颗并满足滤波条件后才可能出解。

输出：`continuity_whu_final.csv`、`verification.json`。没有定位真值、坐标收敛时间或定位误差结论。

## 四、回归与隔离

- 原生 **214 项断言通过**：159 SSR / 40 因果回放 / 15 filter 安全。覆盖正常路径、未完成预热、独立来源编号、旧版本重复、停止推进、断流、真实新估计恢复、来源/配置变化、未来偏差、时间回退，以及北斗标准/IGS/重复/周界。
- Python **28 项测试通过**，增加 profile 不能绑定其他挂载点/APC 的验证，保留 ZIP/哈希、Clock 锚和因果时序测试。
- Android `assembleDebug` 成功，四 ABI native 编译成功；129 JVM 中 **125 通过、4 跳过、0 失败**。
- 原通用策略回放旧手机 47 历元：`solution.csv`、`observations.csv`、`solution.stat`、`corrections.csv` **全部逐字节相同**。
- 用新策略显式重放相同 47 历元短包：仍为 47 个 Q0，原因 `WHU_OSB_WAIT_NEXT_ESTIMATE`，没有把一份重复旧偏差当作就绪，未出现假 Q6。
- `verify_isolation.py` 原工程 50 项来源检查无代码/配置变化；SSR 宏关闭时 PPP/SPP/RTCM 预处理与机器码一致。
- 两个副本的 PPP core 对此前源指纹均零修改；R/Q/P0、GIM、Joseph 和抗差保持不变。仅 live 四 ABI `.so` 改变，其他八个 `.so` 不变。

对历史上**已经使用标准 RTCM 北斗出解**的记录，时间修复可能改变实际坐标，这是确定时间错误修复的预期影响。本轮没有这样的同期新手机解，不能声称所有历史 SSR 北斗坐标都完全不变。

## 五、代码、复核命令与安装状态

主要修改：

- PC `src/ntrip_ssr.{h,cpp}`：独立配套策略、连续性状态与北斗时标转换。
- PC `src/pc_ssr_replay.{h,cpp}` / `src/gnss_replay.c`：显式 profile、独立实例与 inventory。
- PC `tools/replay_session.py` / `tools/ntrip_capture.py` / `tools/import_android_capture.py`、`config/caster_whu.json`：配置校验及留档/导入。未标 profile 的旧包仍默认 `GENERIC_STRICT`，不自动按新策略重解释。
- Android 同步 helper；`gnss_jni.cpp::nativeUseWhuProfile()`、`LivePppNative.kt`、`LiveSsrSession.kt`、`NtripCaptureStore.kt`：初始化前明确启用、记录实际 profile。增加预热提示资源。
- 新增/扩展针对性测试、`tools/verify_whu_policy.py`；原代码备份及 SHA 位于 `validation/whu_policy_20261024/before/` 和 `before.json`。

```powershell
# E:\GNSS\PPP_NTRIP_PC
.\build_pc.cmd --test
& 'E:\Program Files (x86)\python3\python.exe' -m unittest discover -s tests -p 'test_*.py'
.\bin\ppp_ssr_replay.exe --inspect-capture validation\whu_policy_20261024\continuity_capture --ssr-profile WHU_OSB_CONTINUITY_V1
.\bin\whu_policy_capture_test.exe validation\whu_policy_20261024\continuity_capture validation\whu_policy_20261024\continuity_whu_final.csv
& 'E:\Program Files (x86)\python3\python.exe' tools\verify_whu_policy.py
```

安卓 APK：`E:/android/test/PPP_NTRIP/app/build/outputs/apk/debug/app-debug.apk`。

SHA-256：`aad3e1e4d0bf62cb7c9ed5f7198ef2070d0ac8d58070868db5347a44be457a0c`。

**当前未安装**：ADB `10AFCP26FR007MJ unauthorized`，已经请求用户重新允许调试；未清除手机数据、未绕过授权。下一步仅需授权后覆盖安装并做同一时段户外 TXT＋三路流验证。启动后预热可能约 5 分钟；若连接/产品缺失会更久，不承诺固定秒数出解。Q6 只表示浮点 PPP，仍需导出 ZIP 对照独立参考评价完整收敛曲线。
