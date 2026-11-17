# 当前项目状态

核验日期 2026-11-17（Asia/Shanghai）。本文件用于跨会话接手。长期约束见 [AGENTS.md](AGENTS.md)。

## 当前目标和停点

用 Android 手机原始 GNSS 观测与实时 NTRIP 产品实现非组合浮点 PPP，缩短首解并降低不同会话的水平偏差；PC 按原三流到达顺序因果回放，复现 Android 并评估候选。当前重点是首解前的系统性东偏和部分会话的码更新偏差。

最后完成 Step 9 启动 SPP 方程导出及归因。已经查清首个 Q6 前的东偏发生在 SPP，并按星座和钟差列闭合。正式 WHU OSB 缓存隔离已落地，正式估计器继续用原有基线。此轮停在隔离诊断与归档，下一项工作等待用户启动。 [Step 9 报告](../ntrip-ppp-step9-20261117/README.md)

## 工程与 Git

以下为本次审查时、文档镜像发布前的快照。接手时重新核对，尤其要区分仓库 HEAD、最后业务版本和实际手机安装版本。

|工程|根目录|核验版本与工作区|
|---|---|---|
|PC 因果回放| `E:/GNSS/PPP_NTRIP_PC` | 当前无 `.git`，`git rev-parse` 无仓库，分支、HEAD 和相对 HEAD 的修改列表均不适用。|
|Android 在线采集和 PPP| `E:/android/test/PPP_NTRIP` | `main`，HEAD 与 `origin/main`、远端 `refs/heads/main` 均为 `c739be7d1bfba9590b75e68171bd5943647cd011`；已暂存和已跟踪工作区差异均为空。|

Android 当时未跟踪项为 `.agents/`、`.idea/`、`AGENTS.pre_live_ssr_20261024.md`、`docs/Android_GNSS原始数据采集学习手册.docx`、`docs/CODEX_HANDOFF_SNAPSHOT_20261018.json`、`docs/PPP_INVESTIGATION_LEDGER.json`、`docs/ntrip/`。这些属于已有本地内容。

- 最近业务提交是 `18be1550a3df422654c82d7f6af9b971c5e30eec`，同步两端 WHU OSB 来源隔离和回归。此前的 `1932fdabb607412d89fe60615032320a14278e57` 包含启动提速、相位 OSB、定时采集与地图。 [正式修复提交](https://github.com/Drinkey666/Android_GNSS_NTRIP/commit/18be1550a3df422654c82d7f6af9b971c5e30eec)
- Step 4–8 的 Android 提交 `1c62f47`、`691dcea`、`9acd4a7`、`7b1574c`、`d2eb9c0` 归档 PC 隔离实验。 [Step 8 归档](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/d2eb9c0728856c6786fef62d545ee82cdc7ffc1e/docs/ntrip-ppp-step8-20261117/README.md)
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

|工作|证据与边界|
|---|---|
|正式产品与估计器| WHU `SSRC00WHU0` CoM 轨钟 + `OSBC00WHU1` 独立偏差 + `BCEP00BKG0` 广播星历，配套预报 IONEX/VMF3。沿用 `B_VERIFIED` 非组合联合估计、Joseph 更新及现有 R/Q/P0。采集包保存时序、流、产品和参考高程类型。参考坐标只用于解后评估。 `config/caster_whu.json` · `src/verified_profile.h`|
|独立 WHU OSB 缓存隔离| PC/Android 的 `NtripSsr::feed()` 将通道 0 轨钟的身份与写入限制为其分量；通道 2 独立管理码及相位偏差。合法零值、缺失、时效与 IOD 检查保留。四个小米包 V2 正式重放的 2,623 历元 × 17 列和第三轮准入对照逐字节一致，10:01/10:04/10:41/11:20 分别有 119/1466/63/587 个 Q6。第三轮匹配的 45,946 条共有信号 OSB 数值一致，部分共有窗口误差变化可追到新增准入和此前滤波状态历史。 [回放与测试](../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/REPORT.md) · [对应 Android 源码](https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/18be1550a3df422654c82d7f6af9b971c5e30eec/app/src/main/cpp/ntrip_ssr.cpp)|
|首解门控| Android 现行源码采用 `WHU_OSB_FIRST_COMPLETE_V2`，旧包保留 `WHU_OSB_CONTINUITY_V1`。10/31 小米固定三流到达前缀，首个 Q6 为旧 585 秒、新 5 秒，Q6 为 84/663，末 60 秒 H/U RMS 为旧 1.822/0.460 m、新 1.691/0.407 m。 `validation/whu_first_complete_20261114/verification.json`|
|相位 OSB 浮点处理| 两端已接入。10/31 的 2,186 条最终提交相位中，1,385 条 GPS/GAL 应用，剩余 801 条北斗保持原浮点参考。该对照中末 60 秒 H RMS 仍为 1.822 m。 `docs/NTRIP_PHASE_OSB_FLOAT_CHAIN_20261108.md`|
|实录复现和 Android 功能| 11/14 两机旧版实录已按应用顺序复现，分别有小米 2,623 期、vivo 2,629 期状态验证。采集定时、自动收尾、即使没有 Q6 也留档参考及失败摘要已通过构建、JVM 和 PC 导入夹具。11/11 vivo 实测高德内嵌底图的设备标点、拖动、放大；实时 PPP 来源切换待届时真机验证。 `validation/android_capture_20261114/REPORT.md` · `validation/vivo_capture_20261114/REPORT.md` · [Android 状态](../CURRENT_STATE.md)|

## 已证实的精度现象与未解决的问题

- **首个 Q6 前的东偏已完成定量归因。** 六组隔离回放 6,202 历元、4,703 个 Q6 完全复现保存的正式基线。SPP 接纳坐标原样进入首个 Q6 验前，无二次覆盖、Q5、回退或更早 PPP 提交。11:20 小米主要为 GPS 1C，10:04 vivo 主要为 BDS 2I，10:04 小米由 GPS/GAL 1C 共同推动，10/31 V2 无 GPS 实测行，GAL 1C 与 BDS 2I 分别推东 +1.207/+0.776 m。同组常量偏移由钟差/ISB 吸收，尚未分离组内相对残差的物理来源。固定线性化闭合 1.95×10⁻¹⁴ m。 11:20 vivo 独立对照在验前为西偏 −2.462 m，GPS 1C 贡献 −2.877 m。四个正东偏包与 Step 6 表对齐。 [首期原表](../ntrip-ppp-step6-20261117/pre_q6_init.csv) · [Step 9 报告](../ntrip-ppp-step9-20261117/README.md)
- **末段东偏仍在。** 五个正式基线的末 60 秒 E 均值约 +0.63～+1.62 m。10:04 小米的 GPS 1C 前 60 个 Q6 对 E/N/U 累计 +1.781/+3.106/−3.859 m，屏蔽 GPS 码使其全段 H/U RMS 从 2.342/2.977 m 降到 1.424/1.893 m，末段 E 仍为 +1.108 m。其他包的消融反应不同。已定位这段 PPP 的主要推力，跨包的共同东偏与原始码、共享产品、建模历史的物理责任仍未分离。 [Step 5 消融](../ntrip-ppp-step5-20261117/README.md) · [GPS 逐星明细](../ntrip-ppp-step6-20261117/gps1c_first60_satellites.csv)
- **11:20 vivo 的单频码质控盲区已有证据。** 前 20 个 Q6 的 G03 1C、G10 1C、E27 1C 各累计下拉 U 4.1955、1.0219、1.2554 m；G25 1C 首期双机去均值码差 +21.335 m，已有 12 倍码方差档，累计净上推 +0.799 m。部分单频参考码的误差由逐星垂直电离层、高程和公共钟差分摊，验后组偏差最大约 1.11 倍物理 σ₀，低于现有质控门限。双机互换已拆分锚点静态项、随后时变项及 E07 等无首期锚点的差异，组中心口径也影响结果。单频标志、MAD、CMC 和相位弧状态在这两机样本中存在重叠，尚无稳定的单机观测判据。 [Step 2 排行与互换](../ntrip-ppp-closure-20261117/validation/brain_step2_closure_20261116/REPORT.md) · [Step 3 核查](../ntrip-ppp-closure-20261117/validation/brain_step3_final_audit_20261116/REPORT.md)
- **部署与观测风险。** 现行 Android 修复版的 arm64 真机首解、定时收尾和真实 PPP 地图来源切换尚待验证。首份完整 OSB 的绝对时效尚未获得独立认证。Native 零值哨兵、异步表示、100 ms 发送时标冲突、GAL7Q ADR/PRR 不一致仍是已知限制。已有用户确认无同期测量型接收机数据。旧报告的 ADB 状态只代表原核验时点。 [原生与真机边界](../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/REPORT.md) · [历史索引](../ntrip-ppp-step9-20261117/pc-docs/PPP_INVESTIGATION_INDEX.md)
- **非实时旁支。** 文件 CLK3.04 列偏移及产品预检的 CLK 天线头解析还有已记录问题，实时 SSR 不走这些入口。 `docs/NTRIP_FULL_PRODUCT_COMPARISON_20261110.md`

以上误差以各包绑定的参考位置与高程类型评估。E/N/U 为米，H 为水平误差，末 60 秒为按相应报告定义的有效坐标时间窗。原版实录、正式来源修复基线和私有互换有不同准入窗口；比较时以同一包、启动策略和共同 Q6 口径为准。

## 已排除或仅保留为诊断

- 已完成 P0/R、DOP、删星、平滑、启动延迟、相位 OSB 开关及最终/实时产品配对。给定样本未证实东偏可由东向几何劣化、SPP 位置锁死或相位常量 OSB 单独解释。CODE/GFZ 对照已实际解算，其覆盖与参考不同，各方案未全面优于正式基线。 [历史索引 E20–E26](../ntrip-ppp-step9-20261117/pc-docs/PPP_INVESTIGATION_INDEX.md)
- Step 4 M2 单频普降与 M3 弧起点 CMC 降权已淘汰。STATMOD 7 是定位证据，连续弧码降权 `1+N_lock` 为负结果。Step 5 M1_v2 与 Step 7 M1_v4 跨包取舍明显，Step 6 B/C 淘汰，A 只作隔离对照。 [索引 E28–E35](../ntrip-ppp-step9-20261117/pc-docs/PPP_INVESTIGATION_INDEX.md)
- Step 8 新跑 12 组、复用 12 组，P 与伪观测核对一致。A 加定锚后，10/31 V2 与 10:04 小米首期 U 分别从 +3.120 到 +1.785 m、从 −3.163 到 −2.815 m，末 60 秒 U RMS 仅改善 3 mm、2 mm。11:20 小米前 20 期 U RMS 从 0.486 到 0.560 m，持续东偏仍存在。作为启动诊断保留。 [Step 8 报告与数据入口](../ntrip-ppp-step8-20261117/README.md)
- 后续固定使用非组合浮点模型。历史 IF/IFLC、AR 以及私有 B1C/零状态/取消等待的结果保留原范围，禁止以诊断对照名义重新执行 IF/AR。

## 下一步及验收（待用户启动）

1. 复用 Step 9 接纳行和钟差投影。若继续追物理来源，优先按同秒、同星和参考条件核对 11:20 两机的 GPS 1C（尤其 G25、G03）、10:04 vivo 的 BDS 2I、10/31 V2 的 GAL 1C 与 BDS 2I。把各行相对残差拆到首槽原始码、应用的 WHU 码偏差、轨钟、大气与权重。用共享观测和实际应用前缀做对照。缺独立证据时，定位到方程或观测组即可，保留物理来源未归因。
2. Step 9 观察器已经精确复现六组，已保存 SPP 方程、传递与 PPP 首期位置。复用其产物及 Step 5/6 后续 PPP 矩阵。仅在有明确新问题时追加隔离控制。候选验收仍需多包共同 Q6、首解、ENU、H/U RMS 与失败/退化统计，参考坐标只用于解后评分。

## 核验记录与最小阅读索引

- **本次 Step 9 核验**：重编译 29 个私有回放对象，完成六次无损回放。校验前后 Step 8 清单 223/223、PC 二进制 9/9、两端共享内核 33/33；另核对 238 项输入、源码及已存基线文件快照。逐场景的计算、闭合与输出哈希见 [验证清单](../ntrip-ppp-step9-20261117/verification.json)。本轮未重新执行正式原生、Python 或 Android 全套回归。
- **沿用的正式修复测试证据**：PC 原生 963 项计数断言，另通过诊断窗口和 V1 实录夹具。Python 59 通过，4 项 IF 未执行。Android x86_64 模拟器 Native 617 项通过，arm64 Native 已编译，App 四 ABI 已构建。JVM 165 通过、3 项外网冒烟跳过、0 失败。正式报告的“未提交”是报告生成时状态，之后的 Git 记录确认 Android 正式源码已发布。 [测试明细](../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/verification.json) · [发布提交](https://github.com/Drinkey666/Android_GNSS_NTRIP/commit/18be1550a3df422654c82d7f6af9b971c5e30eec)
- 启动/SPP 优先读 Step 9 与四组 Step 6 旧先验表；末段和星座消融读 Step 5；判断是否重做定权或定锚先看 Step 7、8；WHU 可用性先看正式修复及第三轮准入表。其余历史按编号查 [实验索引](../ntrip-ppp-step9-20261117/pc-docs/PPP_INVESTIGATION_INDEX.md)、[证据台账](../ntrip-ppp-step9-20261117/pc-docs/PPP_INVESTIGATION_LEDGER.json)。旧规则快照在 `docs/handoff_archive/20261107`。
- 当前可复核范围以链接到的本地源码、Git、产物和保存日志为准。历史聊天未保存的细节或缺失的 SPP 数据不补写为事实。交接不依赖旧对话的完整内容。
