# 手机实时 NTRIP PPP 问题报告

本文记录 11/16 的诊断基线。11/17 的 WHU OSB 正式修复、回归和三轮诊断见 [后续归档](../ntrip-ppp-closure-20261117/README.md)。

2026-11-16 · Android 分析基线 [`1932fda`](https://github.com/Drinkey666/Android_GNSS_NTRIP/commit/1932fdabb607412d89fe60615032320a14278e57)

使用安卓 GNSS Raw 观测做实时 WHU NTRIP PPP。轨钟来自 `SSRC00WHU0`（CoM），偏差来自 `OSBC00WHU1`，广播星历来自 `BCEP00BKG0`，大气产品为同期预报 IONEX 和 VMF3。当前估计器是 B_VERIFIED 非组合浮点 PPP，显式估计逐星电离层，使用 Joseph 协方差更新。文中 Q6 指本项目接受的浮点 PPP 结果，Q0 指无解。

**需要协助的问题**是手机码观测的方向性偏差如何形成、为何在不同时间和设备上产生米级定位误差，以及如何隔离 WHU 轨钟流与独立码偏差缓存以减少间歇无解。

## 1. 米级位置误差随设备和时段变化

- **10/31 小米**。旧启动规则下，末 60 秒水平/高程 RMS 为 **1.822/0.460 m**。首次成功更新中，真实码观测对北向增量合计贡献 **−1.93 m**。固定参考的码空间拟合在 84 个有效解中呈现东向 **+1.05 m**、北向 **−1.75 m** 的中位分量。该拟合用于判断残差方向。
- **11/14 双机**。仅统计两机同一 GPST 秒都为 Q6 的历元，10:04 vivo/小米水平 RMS 为 **1.294/2.204 m**，11:20 为 **1.165/0.607 m**。11:20 vivo 高程由首次更新前 **+6.05 m** 到首 Q6 的 **+1.38 m**，第 20 个 Q6 为 **−3.21 m**。首期高程的码更新贡献 **−4.67 m**，相位直接贡献约 **+0.003 m**。
- **伪距互换**。在匹配同星同信号、广播星历、轨钟、码偏差及天线参考后，互换两机去除星座/信号组公共项后的相对伪距差。保留各机载波、多普勒、时标、实时流到达前缀和滤波设置。11:20 vivo 高程 RMS **2.142 → 0.974 m**，小米 **0.550 → 1.114 m**。只互换 GPS `1C` 和 Galileo `1C/5Q`，高程 RMS 分别到 **0.905 m** 和 **1.081 m**。只互换北斗 `2I` 时，vivo 高程 RMS 为 **2.151 m**。10:04 的部分误差也会随伪距转移。 [互换数值、控制及核验](evidence/pseudorange-swap.json)
- **状态耦合**。11:20 vivo 首期高程与 GPS 公共接收机钟差验后相关系数为 **+0.877**，与北斗系统间偏差为 **+0.592**。两机共同的 19 颗星，首期逐星电离层初值最大只差 **0.016 mm**，更新后才出现明显差异。相关系数表示估计状态的耦合。 [首期状态与可辨识性](evidence/state-separation.json) · [184 个 Q6 的相对 ENU 和状态相关性](evidence/relative-enu-and-state-coupling.csv)
- **Raw 复算**。独立重算了 **19,770** 条配对 GPS/Galileo 伪距，与正式连续回放最大差 **3.73×10⁻⁹ m**。这些样本的 `TimeOffsetNanos` 和硬件钟不连续计数均为零。四条极端 Galileo 码差可从 Raw 重算，旧滤波均已拒绝。复算范围覆盖这些样本的公式和时钟段引用。物理发送时标、非零 offset、钟跳及已知 100 ms 反例仍需各自验证。 [按设备和信号的 Raw 汇总](evidence/raw-clock-audit.json)

目前可以确定，相对码输入会转移两机间很大一部分高程误差，滤波会把它分配到位置、系统钟差和逐星电离层。手机跟踪、多路径、真实发送时刻和模型余差各占多少仍未确定。采集者回忆 11:20 人在 vivo 附近，记录里缺少靠近、离开与站位时刻，现有两时段无法识别其影响。

**希望协作者优先核对**前三层的米、秒、纳秒和参考约定：Android 回调字段到 P/L/D、码与卫星钟改正进入残差、非组合滤波中误差如何在位置与接收机状态间分配。优先针对首批 20 个成功 Q6 找可区分的检验。 [Raw 时钟与信号适配](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/gnss_adapter.c#L278) · [观测改正](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/ppp.c#L1221) · [电离层初始化](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/ppp.c#L2532) · [残差方程](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/ppp.c#L3476) · [最终滤波提交](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/ppp.c#L4953)

## 2. 间歇无解与首解等待

**已复现的 WHU 缓存覆盖。** `NtripSsr::feed()` 处理通道 0 时先将解码结果赋给 `committed[sat]`。只有轨钟侧解码结果没有码偏差历元时，才恢复旧码偏差字段。若同一解码器此前收到轨钟流自带码偏差，这些字段会覆盖独立偏差流的已提交数据，随后被 `usable()` 判为 `WHU_CODE_BIAS_COMPONENT_MISMATCH`。

在 11/14 10:01 反例中，轨钟流携带的码偏差估计历元比独立流新 **450 s**。一次出解中断中有 **28 颗星**被该原因拒绝。PC 实验从独立偏差流缓存取码偏差分量，保留原始到达前缀和现有准入检查。四包 Q6 数量从 **55/852/45/488** 到 **119/1466/63/587**。共有末 60 个 Q6 中，10:04 高程 RMS **2.42 → 3.00 m**，11:20 水平 RMS **0.63 → 0.72 m**。该实验修正尚待正式回归。 [合并分支](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ntrip_ssr.cpp#L248) · [组件身份和时标检查](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ntrip_ssr.cpp#L288) · [PC 实验补丁](evidence/isolated-whu-code-source-experiment.patch) · [四包数据](evidence/startup-and-osb.json)

建议用“先提交独立偏差 → 再输入含码偏差的轨钟流 → 下一历元检查仍使用独立偏差”的消息序列写回归，覆盖重连后重新等完整偏差、有效零与缺失偏差、来源/IOD/时效保护。用相同到达前缀比较 Q6 覆盖、连续掉解时长和共有时窗 E/N/U。 [现有 SSR 测试文件](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/tests/ntrip_ssr_test.cpp)

**首解和断流。** 安卓源码已采用 `WHU_OSB_FIRST_COMPLETE_V2`。在 10/31 同一到达前缀回放中，首 Q6 从 **585 s 到 5 s**，末 60 秒水平/高程 RMS 从 **1.822/0.460 m 到 1.691/0.407 m**。新版真机首解和首份 OSB 的绝对有效期仍待验证。另有 11/14 小米 10:04 三路同时停止收到字节的记录，开录约 **23:51** 后无新字节，约 **25:09** 后无 Q6，断流起点需要查通道日志。 [启动与重连](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ntrip_ssr.cpp#L64) · [NTRIP 客户端](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/java/com/example/ftpget/NtripClient.kt#L127) · [采集留档](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/java/com/example/ftpget/NtripCaptureStore.kt#L240)

## 3. 文件与复核方法

| 范围 | 阅读入口 |
|---|---|
| Android Raw 到在线解算 | [GnssDataLogger.kt](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/java/com/example/ftpget/GnssDataLogger.kt#L86) · [LiveSsrSession.kt](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/java/com/example/ftpget/LiveSsrSession.kt#L93) · [gnss_jni.cpp](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/gnss_jni.cpp#L398) · [gnss_clock_reference.h](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/gnss_clock_reference.h#L27) · [gnss_adapter.c](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/gnss_adapter.c#L21) |
| 安卓在线估计与诊断 | [ppp.c](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/ppp.c#L2958) · [ppp_filter_diagnostic.c](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/ppp_filter_diagnostic.c) · [smartphone_ppp_config.c](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/smartphone_ppp_config.c) |
| 改正流与产品 | [ntrip_ssr.cpp](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ntrip_ssr.cpp#L141) · [rtcm3.c](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/cpp/ppp_live/rtklib/rtcm3.c) · [LivePppProducts.kt](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/1932fdabb607412d89fe60615032320a14278e57/app/src/main/java/com/example/ftpget/LivePppProducts.kt) |
| PC 到达前缀回放及解算 | [pc_ssr_replay.cpp](pc-source/src/pc_ssr_replay.cpp) · [gnss_replay.c](pc-source/src/gnss_replay.c) · [ntrip_ssr.cpp](pc-source/src/ntrip_ssr.cpp) · [gnss_adapter.c](pc-source/core/gnss_adapter.c) · [ppp.c](pc-source/core/ppp.c) · [ppp_filter_diagnostic.c](pc-source/core/ppp_filter_diagnostic.c) · [源码 SHA-256](pc-source/SHA256-LF.txt) |
| 回放实验与分析脚本 | [Raw 复算](diagnostics/validation/ntrip_raw_clock_audit_20261116/analyze.py) · [互换计划](diagnostics/validation/ntrip_code_swap_20261114/build_tables.py) · [PC 注入钩子](diagnostics/validation/ntrip_code_swap_20261114/swap.inc) · [互换核验](diagnostics/validation/ntrip_code_swap_20261114/verify.py) · [滤波状态分析](diagnostics/validation/ntrip_state_separation_20261114/analyze.py) |

PC 源码为供审阅的相关文件快照。完整回放需原 PC 工程、对应 Raw/TXT、三个 RTCM 流、`arrivals.csv`、`epochs.csv`、时钟锚点、`capture.json` 及冻结产品。此处公开的是相对误差、汇总和代码。状态分析脚本需要调用方提供 JSON，键为 `vivo_1120`、`xiaomi_1120`、`xiaomi_1004`、`xiaomi_1031`，值为各采集包的 `[纬度, 经度, 椭球高]`，并使用 NumPy 和原有矩阵目录。参考坐标仅用于离线评价。

此前已核对 DOP、单星删减、初始化协方差和码权、平滑与降权候选。相位 OSB 已接入浮点观测链，10/31 开关对比应用到 1385 条最终相位行，末 60 秒水平 RMS 均为 **1.822 m**。CODE/GFZ 实际解算配对未找到水平和高程均优于正式基线的方案。后续维持实时 WHU NTRIP、非组合模型及显式电离层，排除双频无电离层组合和模糊度固定。原始流严格按到达顺序使用，保留现有时间、来源、IOD 及失效保护。
