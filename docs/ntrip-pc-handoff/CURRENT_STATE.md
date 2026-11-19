# 当前项目状态

核验日期 2026-11-19（Asia/Shanghai）。本文件用于跨会话接手。长期约束见 [AGENTS.md](AGENTS.md)。

## 当前目标和停点

11/19 已验证匿名广播星历 `ntrip.use-snip.com:2101/RTCM3EPH` 与原 WHU 轨钟、偏差分服并发。vivo 蜂窝网约 118 秒收到 3,856／93／97 帧（广播／轨钟／偏差），CRC 错误均为零。21:45 已在 vivo V2507A 保留数据覆盖安装新版，已启动 App 并保存「使用 SNIP 独立广播星历」设置，两条 WHU 挂载已核对；PC 使用 `config/caster_whu_snip.json`。本轮只核验收流和产品期号，未评估定位精度。 [实测与切换](../ntrip-broadcast-mounts-20261119/REPORT.md)

Step 13（E41）已完成 24 组 PC 私有因果回放。只关闭原 A2 的 CMC 附加倍率，10/31 小米 V2 末 60 秒 U RMS 从 0.9902 降到 0.9443 m，仅挽回原反退的 7.9%，U 均值仍为 −0.9438 m。10:04 小米保留原 A2 全段水平／高程收益的 76.4%／64.4%。在原 A1 或原 A1 加纯 EMA 上，电离层 Q 减半的最大单历元垂向影响分别为 0.583／0.415 mm。 四方案均为 PARTIAL_TRADEOFF。 [报告](../ntrip-ppp-step13-20261119/REPORT.md) · [逐包限幅效应](../ntrip-ppp-step13-20261119/partB_ionq_effects.csv)

用 Android 手机原始 GNSS 观测与实时 NTRIP 产品实现非组合浮点 PPP，缩短首解并降低不同会话的水平偏差；PC 按原三流到达顺序因果回放，复现 Android 并评估候选。当前重点是首解前的系统性东偏和部分会话的码更新偏差。

此前 E40 完成 Step 12 参考坐标框架与历元审计，归属判定为 PARTIAL。复用 Step 5 的六组坐标，正式估计器与既有参考保持原样。 [Step 12 报告](../ntrip-ppp-step12-20261117/REPORT.md)

## 工程与 Git

以下为本次审查时、文档镜像发布前的快照。接手时重新核对，尤其要区分仓库 HEAD、最后业务版本和实际手机安装版本。

|工程|根目录|核验版本与工作区|
|---|---|---|
|PC 因果回放| `E:/GNSS/PPP_NTRIP_PC` | 当前无 `.git`，`git rev-parse` 无仓库，分支、HEAD 和相对 HEAD 的修改列表均不适用。|
|Android 在线采集和 PPP| `E:/android/test/PPP_NTRIP` | E41 归档前本地及远端 `main` 为 `bc878141b479be8f4e485b7859be7375dadeb2b3`。接手时暂存区为空，两份交接文档有在先未暂存编辑。|

Android 当时未跟踪项为 `.agents/`、`.idea/`、`AGENTS.pre_live_ssr_20261024.md`、`docs/Android_GNSS原始数据采集学习手册.docx`、`docs/CODEX_HANDOFF_SNAPSHOT_20261018.json`、`docs/PPP_INVESTIGATION_LEDGER.json`、`docs/ntrip/`。这些属于已有本地内容。

- 此前的共享估计器修复提交是 `18be1550a3df422654c82d7f6af9b971c5e30eec`，同步两端 WHU OSB 来源隔离和回归。此前的 `1932fdabb607412d89fe60615032320a14278e57` 包含启动提速、相位 OSB、定时采集与地图。 [正式修复提交](https://github.com/Drinkey666/Android_GNSS_NTRIP/commit/18be1550a3df422654c82d7f6af9b971c5e30eec)
- Step 4–10 的 Android 提交 `1c62f47`、`691dcea`、`9acd4a7`、`7b1574c`、`d2eb9c0`、`e28c9e0`、`98b681f` 归档 PC 隔离实验与交接。 [Step 10 归档](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/98b681fdbb84644a3754d644c13c1dd087dd63f3/docs/ntrip-ppp-step10-20261117/README.md)
- `E:/GNSS/rtklib_only/rtklib_only/rtklib_Project2` 是旧工程。原 PPP_only、FTPGet 仅供参考。PC 根目录 README 和首次集成设计中关于 BKG 默认、仅采集或尚无 PPP 解的叙述属于历史。 `docs/ANDROID_WHU_SSR_FORECAST_INTEGRATION.md`

## 模块与运行入口

|范围|按任务读取的入口|
|---|---|
|PC 观测、SPP、PPP| `core/` 负责共享 C 内核、观测生成、RTCM 和产品检查。重点是 `core/pntpos.c`、`core/rtkpos.c`、`core/ppp.c`，正式配置入口为 `src/verified_profile.h`。|
|PC 流与回放| `src/ntrip_ssr.cpp/.h` 管理 SSR 解码、缓存、来源、IOD 和时效。 `src/pc_ssr_replay.cpp` 管理到达前缀和应用顺序，`src/gnss_replay.c` 接入复放观测和解算。用 `import_android_capture.cmd` 导入、`replay_txt.cmd` 回放，输出目录须为新目录。|
|Android 正式路径| `app/src/main/cpp/ppp_live/rtklib/` 为共享内核，`app/src/main/cpp/ntrip_ssr.cpp` 管理 SSR。Kotlin 入口位于 `app/src/main/java/com/example/ftpget/`，实时 PPP 与采集看 `LiveSsrSession.kt`、`NtripCaptureService.kt`、`NtripCaptureStore.kt`，地图看 `MapPosition.kt`、`ui/MapScreen.kt`、`ui/AmapMap.kt`。|
|构建、测试、证据| PC 用 `tools/build.py` 加 `build_pc.cmd`，已使用 VS2022 Professional / MSVC x64。 `tests/` 为回归，`validation/` 为证据，`CMakeLists.txt` 是备用构建入口。Android 用 `gradlew.bat` 和 `app/src/main/cpp/CMakeLists.txt`。 |

- PC 原生回归用 `./build_pc.cmd --test`，会重建产物和写 `validation/build.json`。Python 用 `./tools/plot_venv/Scripts/python.exe -X utf8 tools/run_ntrip_python_regressions.py`，四项历史 IF 诊断按约束排除。真实 V1 录包夹具另需按正式报告提供输入。
- Android JVM 用 `./gradlew.bat :app:testDebugUnitTest --offline --console=plain`，构建用 `./gradlew.bat :app:assembleDebug --offline --console=plain`。Native 测试、模拟器运行及 ABI 检查见正式修复报告。共享布局为 `NFREQ=4`、`ENAGLO`、无 `ENAQZS`，PC 构建带 `PPP_NTRIP_SSR` 和 `TRACE`。 [正式测试记录](../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/REPORT.md)

## 已实现、已验证

11/18 当前真机安装核验。2026-11-18 实查 vivo V2507A，com.example.pppntrip 最后更新 2026-11-18 15:09:06。手机 arm64 版与本地最新多 ABI APK 的全部 DEX、资源、资产和 arm64 原生库逐项一致。整体 APK SHA 不同，手机 Manifest 额外设置 testOnly=true，本地额外包含其他三种 ABI 共九个库。安装内容与当前最新本地程序内容一致，实时 PPP 采集验收待执行。 [核验报告](../ntrip-device-apk-check-20261118/REPORT.md)


|工作|证据与边界|
|---|---|
|正式产品与估计器| WHU `SSRC00WHU0` CoM 轨钟 + `OSBC00WHU1` 独立偏差 + `BCEP00BKG0` 广播星历，配套预报 IONEX/VMF3。沿用 `B_VERIFIED` 非组合联合估计、Joseph 更新及现有 R/Q/P0。采集包保存时序、流、产品和参考高程类型。参考坐标只用于解后评估。 `config/caster_whu.json` · `src/verified_profile.h`|
|独立 WHU OSB 缓存隔离| PC/Android 的 `NtripSsr::feed()` 将通道 0 轨钟的身份与写入限制为其分量；通道 2 独立管理码及相位偏差。合法零值、缺失、时效与 IOD 检查保留。四个小米包 V2 正式重放的 2,623 历元 × 17 列和第三轮准入对照逐字节一致，10:01/10:04/10:41/11:20 分别有 119/1466/63/587 个 Q6。第三轮匹配的 45,946 条共有信号 OSB 数值一致，部分共有窗口误差变化可追到新增准入和此前滤波状态历史。 [回放与测试](../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/REPORT.md) · [对应 Android 源码](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/18be1550a3df422654c82d7f6af9b971c5e30eec/app/src/main/cpp/ntrip_ssr.cpp)|
|首解门控| Android 现行源码采用 `WHU_OSB_FIRST_COMPLETE_V2`，旧包保留 `WHU_OSB_CONTINUITY_V1`。10/31 小米固定三流到达前缀，首个 Q6 为旧 585 秒、新 5 秒，Q6 为 84/663，末 60 秒 H/U RMS 为旧 1.822/0.460 m、新 1.691/0.407 m。 `validation/whu_first_complete_20261114/verification.json`|
|相位 OSB 浮点处理| 两端已接入。10/31 的 2,186 条最终提交相位中，1,385 条 GPS/GAL 应用，剩余 801 条北斗保持原浮点参考。该对照中末 60 秒 H RMS 仍为 1.822 m。 `docs/NTRIP_PHASE_OSB_FLOAT_CHAIN_20261108.md`|
|实录复现和 Android 功能| 11/14 两机旧版实录已按应用顺序复现，分别有小米 2,623 期、vivo 2,629 期状态验证。采集定时、自动收尾、即使没有 Q6 也留档参考及失败摘要已通过构建、JVM 和 PC 导入夹具。11/11 vivo 实测高德内嵌底图的设备标点、拖动、放大；实时 PPP 来源切换待届时真机验证。 `validation/android_capture_20261114/REPORT.md` · `validation/vivo_capture_20261114/REPORT.md` · [Android 状态](../CURRENT_STATE.md)|

## 已证实的精度现象与未解决的问题

- **共同东偏归属判定为 PARTIAL（Step 12／E40）。** CGCS2000@2000.0 给出两点 +0.924/+0.922 m 的东向参考改正，使六包末 60 s E 等权均值由 +1.178 降至 +0.255 m。两个点位和两种机型的分组均值仍为正。10/31 V1/V2 为同一份采集，以 V2 为代表的两点等权残余 +0.389 m，速度敏感区间 +0.351～+0.427 m。现历元 ITRF2014/G2139 的毫米级改正保留米级东偏。参考由用户确认经 RTK/CORS 测得，网络基准与历元无法取得，原参考继续保留。 共享产品与观测历史仍需考虑。 [Step 12 报告](../ntrip-ppp-step12-20261117/REPORT.md)
- **首个 Q6 前东偏已完成 SPP 方程归因与物理项拆解（Step 9 / Step 10 Part A）。** 六组无损复现 6,202 历元、4,703 个 Q6；SPP 接纳坐标原样进入首个 Q6 验前。Step 10 双机同秒配对拆解证实：卫星钟、SSR OSB 与大气相对差完全相消（`0.000 m`），`11:20` 双机 `+3.635 m` 东向差中，共视测量差占 `+4.904 m`（其中纯手机原始测码相对差 `+4.252 m`，`G25 1C` 相对差 `−21.311 m` 贡献 `+3.300 m`），权阵差占 `+0.376 m`，vivo 独有 `E07` 抵消 `−1.644 m`。`Saastamoinen vs VMF3` 东推力 `≤0.017 m`；`SPP 广播电离层 vs GIM` 仅在 `11:20` 产生约 `+0.56 m` 净东推，扣除后各包主推星座仍留存米级东偏。`startup_fde`（最大 `11.15 m / z=3.24`）与 `STARTQC`（最大比值 `0.625`）均未触及 `30 m` 门槛。 [Step 9 报告](../ntrip-ppp-step9-20261117/README.md) · [Step 10 报告](../ntrip-ppp-step10-20261117/README.md)
- **末段东偏与收敛平衡已完成 `tail60` 全段切片（Step 11 Part A）。** 六组 Step 5 基线的末 60 秒 E 均值约 +0.63～+1.62 m；只读 `K·v` 切片证实 5 组长序列末 60 秒几乎冻结（净ΔE `−0.013 ~ +0.089 m`、步均 Code `≤0.0011 m/ep`、累计 Phase `≤0.002 m`），全段相位净推力仅 `−0.042 ~ +0.184 m`、`VMF3_ZWD ≤ 0.005 m`、`5Q/5P` 码偏已入 `$RCB`（`GPS_C5Q +0.614~+3.856 m`、`GAL_C5Q +1.150~+2.999 m`、`BDS_C5P +0.200~+2.646 m`），稳态水平基准主要由收敛期首频伪距（`1C/2I`）与 IONEX 平衡锁定。另见 10:04 小米 GPS 1C 屏蔽对照（全段 H/U 2.342/2.977→1.424/1.893 m，末段 E 仍 +1.108 m）。 [Step 11 切片](../ntrip-ppp-step11-20261117/README.md) · [Step 5 消融](../ntrip-ppp-step5-20261117/README.md) · [GPS 逐星明细](../ntrip-ppp-step6-20261117/gps1c_first60_satellites.csv)
- **11:20 vivo 的单频码质控盲区已有证据。** 前 20 个 Q6 的 G03 1C、G10 1C、E27 1C 各累计下拉 U 4.1955、1.0219、1.2554 m；G25 1C 首期双机去均值码差 +21.335 m，已有 12 倍码方差档，累计净上推 +0.799 m。部分单频参考码的误差由逐星垂直电离层、高程和公共钟差分摊，验后组偏差最大约 1.11 倍物理 σ₀，低于现有质控门限。双机互换已拆分锚点静态项、随后时变项及 E07 等无首期锚点的差异，组中心口径也影响结果。单频标志、MAD、CMC 和相位弧状态在这两机样本中存在重叠，尚无稳定的单机观测判据。 [Step 2 排行与互换](../ntrip-ppp-closure-20261117/validation/brain_step2_closure_20261116/REPORT.md) · [Step 3 核查](../ntrip-ppp-closure-20261117/validation/brain_step3_final_audit_20261116/REPORT.md)
- **部署与观测风险。** 11/18 已核验 vivo 的当前安装内容与最新本地构建一致。arm64 真机首解、定时收尾和真实 PPP 地图来源切换尚待验证。首份完整 OSB 的绝对时效尚未获得独立认证。Native 零值哨兵、异步表示、100 ms 发送时标冲突、GAL7Q ADR/PRR 不一致仍是已知限制。已有用户确认无同期测量型接收机数据。旧报告的 ADB 状态只代表原核验时点。 [原生与真机边界](../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/REPORT.md) · [历史索引](../ntrip-ppp-step12-20261117/pc-docs/PPP_INVESTIGATION_INDEX.md)
- **非实时旁支。** 文件 CLK3.04 列偏移及产品预检的 CLK 天线头解析还有已记录问题，实时 SSR 不走这些入口。 `docs/NTRIP_FULL_PRODUCT_COMPARISON_20261110.md`

以上误差以各包绑定的参考位置与高程类型评估。E/N/U 为米，H 为水平误差，末 60 秒为按相应报告定义的有效坐标时间窗。原版实录、正式来源修复基线和私有互换有不同准入窗口；比较时以同一包、启动策略和共同 Q6 口径为准。

## 已排除或仅保留为诊断

- 已完成 P0/R、DOP、删星、平滑、启动延迟、相位 OSB 开关及最终/实时产品配对。给定样本未证实东偏可由东向几何劣化、SPP 位置锁死或相位常量 OSB 单独解释。CODE/GFZ 对照已实际解算，其覆盖与参考不同，各方案未全面优于正式基线。 [历史索引 E20–E26](../ntrip-ppp-step12-20261117/pc-docs/PPP_INVESTIGATION_INDEX.md)
- Step 4 M2 单频普降与 M3 弧起点 CMC 降权已淘汰。STATMOD 7 是定位证据，连续弧码降权 `1+N_lock` 为负结果。Step 5 M1_v2 与 Step 7 M1_v4 跨包取舍明显，Step 6 B/C 淘汰，A 只作隔离对照。 [索引 E28–E35](../ntrip-ppp-step12-20261117/pc-docs/PPP_INVESTIGATION_INDEX.md)
- Step 8 新跑 12 组、复用 12 组，P 与伪观测核对一致。A 加定锚后，10/31 V2 与 10:04 小米首期 U 分别从 +3.120 到 +1.785 m、从 −3.163 到 −2.815 m，末 60 秒 U RMS 仅改善 3 mm、2 mm。11:20 小米前 20 期 U RMS 从 0.486 到 0.560 m，持续东偏仍存在。作为启动诊断保留。 [Step 8 报告与数据入口](../ntrip-ppp-step8-20261117/README.md)
- Step 10 Part B（`O1`、`O2`、`O3_joint`，18 组）与 Step 11 Part B（`S1_O1_robust` 放宽至 `0.90 m`/`0.7×`/保留 `ION_CONSTR_ROBUST`、`S2_Q0_presmooth`、`S3_presmooth_cmd`、`S4_joint`，24 组）全部归档为 `NEGATIVE_NOT_FIX`。`S1` 仍使 `10/31 V1/V2` 末 60s U 反退（`0.460→0.896 m`、`0.407→1.007 m`）；`S2` 真实运行于各等待期（`5~585` 历元），对 `first20` 呈双向敏感（`10:04 vivo` H `3.432→2.202 m` 但 U `1.473→2.395 m`；`11:20 小米` H `0.681→1.099 m`）；`S3` 在 124,363 条码行上 `f_cmd > 1` 仅触发 `0.0%~0.3%`，证实 1s 高频 CMD 噪声已小于现有 C/N0+高度角 `base_obs_var`（`5~160 m²`）。 [Step 10 报告](../ntrip-ppp-step10-20261117/README.md) · [Step 11 报告](../ntrip-ppp-step11-20261117/README.md)
- 后续固定使用非组合浮点模型。历史 IF/IFLC、AR 以及私有 B1C/零状态/取消等待的结果保留原范围，禁止以诊断对照名义重新执行 IF/AR。

## 下一步及验收（待用户启动）

E41 后续优先复用 10/31 V2 与 10:04 小米的同历元对照，定位纯 EMA 持续降低哪些卫星／频槽的权重，以及这些行对 U 更新的贡献。验收需保持现有准入和观测／改正守卫，并在独立采集上复核全段与末窗 H/U。

1. 优先向原 RTK/CORS 服务商核实两次实测的网络产品、基站实现、坐标历元及速度场／地方转换。取得书面证据后，分别评估与现历元 ITRF2020 的偏移，保留原参考与可复核并列口径。两个参考点的相对差和双机互差均无法单独辨认绝对公共框架平移。
2. 在参考归属未认证前，同时报告原参考和 Step 12 候选口径。针对两点去重后仍在的 +0.389 m 东向量、10:04 两机的互差及高度退化，优先复用 Step 10/11 的观测/产品证据分析低频或准静态码残差与连续相位弧历史。跨包评价使用首解、前 20/60、全段、末窗及共有 Q6，保持原回放准入，参考值仅用于解后评价。

## 核验记录与最小阅读索引

- **Step 13 固定参数消融 E41**。六组 Step 5 基线和十二组 Step 12 A1/A2 对照复算一致。24 组新回放的时标、Q 和双 CSV 哈希逐包一致。18,812 个 Q6 的最大三维闭合差 5.267×10⁻¹⁰ m。9/251/89/24 项分组守卫均通过。 [核验清单](../ntrip-ppp-step13-20261119/verification.json)

- **自适应实验 E40-A**。前后 9/9 正式二进制、248/248 扩展守卫、89/89 补充依赖匹配。18,812 个最终 Q6 的最大单轴／三维闭合差为 4.657/5.295×10⁻¹⁰ m。本轮只运行私有构建、回放和针对性验收。 [核验清单](../ntrip-ppp-step12-20261119/verification.json)

- **参考框架审计 E40 核验**：前后 9/9 正式二进制、245/245 Step 11 守卫和 62/62 本轮依赖匹配。原参考统计复算最大差 1.78×10⁻¹⁵ m，对 4,703 条 Q6 仅做解后评价；旧回放和生产源码未写入。 [核验清单](../ntrip-ppp-step12-20261117/verification.json)
- **上一轮 Step 11 核验**：私有重编译 `ppp.c`、`rtkcmn.c` 与 `src/gnss_replay.c`，完成 24 组隔离回放（`S1_O1_robust`、`S2_Q0_presmooth`、`S3_presmooth_cmd`、`S4_joint` × 6 包）并只读切片 6 组 Step 5 基线。24 组全部保持同历元 Q 序列、`observations.csv` 和 `corrections.csv` 逐字节一致；`K·v` ECEF 最大闭合差 `4.66e-10 m`。正式二进制 9/9、两端共享内核 33/33 及 245 项守卫哈希全部匹配。详见 [验证清单](../ntrip-ppp-step11-20261117/verification.json)。本轮未重跑正式原生、Python 或 Android 全套回归。
- **沿用的正式修复测试证据**：PC 原生 963 项计数断言，另通过诊断窗口和 V1 实录夹具。Python 59 通过，4 项 IF 未执行。Android x86_64 模拟器 Native 617 项通过，arm64 Native 已编译，App 四 ABI 已构建。JVM 165 通过、3 项外网冒烟跳过、0 失败。正式报告的“未提交”是报告生成时状态，之后的 Git 记录确认 Android 正式源码已发布。 [测试明细](../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/verification.json) · [发布提交](https://github.com/Drinkey666/Android_GNSS_NTRIP/commit/18be1550a3df422654c82d7f6af9b971c5e30eec)
- 启动/SPP 优先读 Step 9 与四组 Step 6 旧先验表；末段和星座消融读 Step 5；判断是否重做定权或定锚先看 Step 7、8；WHU 可用性先看正式修复及第三轮准入表。其余历史按编号查 [实验索引](../ntrip-ppp-step12-20261117/pc-docs/PPP_INVESTIGATION_INDEX.md)、[证据台账](../ntrip-ppp-step12-20261117/pc-docs/PPP_INVESTIGATION_LEDGER.json)。旧规则快照在 `docs/handoff_archive/20261107`。
- 当前可复核范围以链接到的本地源码、Git、产物和保存日志为准。历史聊天未保存的细节或缺失的 SPP 数据不补写为事实。交接不依赖旧对话的完整内容。
