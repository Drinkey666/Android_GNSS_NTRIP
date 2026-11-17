# 当前 Android NTRIP 项目状态

核验日期 2026-11-17，Asia/Shanghai。只接续 NTRIP 分支后内容。
新会话先读根目录 AGENTS.md，再读本文件。精度诊断的主状态在 E:/GNSS/PPP_NTRIP_PC/docs/CURRENT_STATE.md，按需读取其报告索引。

## 路径和版本
- Android根目录 E:/android/test/PPP_NTRIP，PC根目录 E:/GNSS/PPP_NTRIP_PC。
- Git 分支 main。11/17 修复与后续交付规则见 [GitHub 当前版本](https://github.com/Drinkey666/Android_GNSS_NTRIP/commits/main/)。
- 11/16 在线源码提交 1932fda，Update Android NTRIP PPP startup, capture, and map。已推送至 https://github.com/Drinkey666/Android_GNSS_NTRIP 并核对远端 SHA。
- 11/16 提交 92ff730 发布对外问题报告、PC 源码摘录、诊断脚本、派生证据及实验补丁。已提交的 Android 源码基线为 1932fda。11/17 独立 OSB 缓存隔离、回归及三轮证据统一归档于 [GitHub 归档](ntrip-ppp-closure-20261117/README.md)。对外报告 https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/92ff7308c5afe14410b15cf431905d531fc3fa3f/docs/ntrip-ppp-review-20261116/README.md
- 本次提交包含此前的相位 OSB 处理、地图与页面布局、定时留档、实时 PPP 启动规则及相关测试，共 25 个 app/src 文件。本地文档、采集数据及 APK 保留在本机。离线 Gradle 检查成功，运行了四个 ABI 的 CMake 构建任务，JUnit 使用已有结果。
- 11/7同步诊断覆盖；11/8先更新交接，随后完成用户要求的相位OSB非组合浮点链及四ABI构建，未迁移旧估计候选。原有未跟踪文件保留。
- PC本身无Git，不能将本HEAD当PC版本。
- 旧聊天目录 E:/GNSS/rtklib_only/rtklib_only/rtklib_Project2 不用于本项目接续。

## 当前任务

11/17 Step 10 完成 SPP/首期相对残差物理拆解（Part A）与 `O1`/`O2`/`O3_joint` 隔离提精消融（Part B）。Part A 复用 Step 9 115 行及首 Q6 快照证实：共视卫星钟差、SSR OSB 与大气相对差完全相消（`0.000 m`），`11:20` 双机 `+3.635 m` 启动东向差中纯手机原始测码相对差贡献 `+4.252 m`（`G25 1C` 相对差 `−21.311 m` 贡献 `+3.300 m`）；`Saastamoinen vs VMF3` 东推力 `≤0.017 m`，`startup_fde` 与 `STARTQC` 最高仅达 30 m 门限 `0.625` 倍。Part B 完成 18 组隔离回放，同 Q 序列且 `observations/corrections` 逐字节一致，`K·v` 最大闭合差 `4.66e-10 m`；但 `O1` 使 `10/31 V2` 末 60 s U 反退（`0.407→1.245 m`），`O2` 使 `11:20/10:04 vivo` 全段 U 反退（`2.289/1.390→2.707/2.463 m`），三档均归档为 `NEGATIVE_NOT_FIX`，正式源码不变。 [Step 10 报告](ntrip-ppp-step10-20261117/README.md) · [PC 交接镜像](ntrip-pc-handoff/CURRENT_STATE.md)

11/17 Step 9 完成隔离 SPP 方程审计。六组隔离回放 6,202 历元、4,703 个 Q6 完全复现保存的正式基线。SPP 接纳坐标原样进入首个 Q6 验前，无二次覆盖、Q5、回退或更早 PPP 提交。11:20 小米主要为 GPS 1C，10:04 vivo 主要为 BDS 2I，10:04 小米由 GPS/GAL 1C 共同推动，10/31 V2 无 GPS 实测行，GAL 1C 与 BDS 2I 分别推东 +1.207/+0.776 m。同组常量偏移由钟差/ISB 吸收，尚未分离组内相对残差的物理来源。固定线性化闭合 1.95×10⁻¹⁴ m。 [Step 9 报告](ntrip-ppp-step9-20261117/README.md) · [PC 交接镜像](ntrip-pc-handoff/CURRENT_STATE.md)

11/17 12 组私有试算完成，复用六组正式及六组 A。定锚前后 P 与伪观测完全一致。A→联合的首期 U，10/31 V2 +3.120→+1.785 m、10:04 小米 −3.163→−2.815 m。末 60 秒高程 RMS 分别仅改善 3 mm、2 mm。11:20 小米前 20 期高程反退，持续东偏仍在。保留独立证据。 [实验报告](ntrip-ppp-step8-20261117/README.md)

11/17 六包 A 精确复现，另完成 18 组 M1_v4。E27 全部未触发，C19 与 G28 均未在前 60 期触发。10:04 小米相对 A 的全段 H/U 全档反退，11:20 vivo 高程改善伴随水平反退。B/C 淘汰，保留 A 为诊断对照，M1_v4 三档归档为 NEGATIVE_NOT_FIX。 [实验报告](ntrip-ppp-step7-20261117/README.md)

11/17 24 组 M1_v3 完成。本轮发现四包首期正东偏已存在于 SPP 初值，当时尚缺逐组方程，后由 Step 9 补齐。10:04 小米 GPS 1C 的前五星 G10/G25/G28/G13/G32，含两颗持续双频。C 全段 H/U 2.342/2.977→1.763/2.424 m，10:04 vivo 两项反退。A、B、C 保持独立实验。 [实验报告](ntrip-ppp-step6-20261117/README.md)

11/17 33 组基线观察、单星座码屏蔽与 M1_v2 完成。10:04 小米 GPS 1C 前 60 期 E/N/U 推力 +1.781/+3.106/−3.859 m，去 GPS 码全段 H/U 2.342/2.977→1.424/1.893 m，末段仍东偏 +1.108 m。五包没有同一星座通解。M1_v2 两档改善 10:04 小米，11:20 小米及 10/31 V1 水平反退，保留独立实验。用户已淘汰 M2 与 M3。 [实验报告](ntrip-ppp-step5-20261117/README.md)

11/17 已完成 PC 隔离码定权评测。30 组隔离回放及 6 组正式控制完成。11:20 vivo 联合全段 H/U RMS 1.187/2.289 → 1.402/1.842 m，单独 M1 1.187/2.289 → 1.160/1.955 m。10:04 双机共有 Q6 下，联合使 vivo H/U RMS 1.359/1.453 → 1.690/2.125 m、小米 2.343/2.977 → 1.833/2.581 m。10/31 末 60 秒 H/U RMS，V1 1.822/0.460 → 2.254/0.364 m、V2 1.691/0.407 → 1.778/0.093 m。联合精度取舍明显，归档为 NEGATIVE_NOT_FIX。 Android 正式 ppp.c 继续使用已发布基线。[回放报告](ntrip-ppp-step4-20261117/README.md)

11/17 独立 WHU OSB 缓存隔离已同步到 Android 正式代码。独立 WHU 模式下，通道 0 身份检查只看轨钟 k=0/1，通道 2 只看码偏差 k=4。通道 0 在已提交缓存只写非偏差分量，纯码帧且该星无轨钟时跳过写入。1059→1060 回归覆盖 V1/V2、冷启动、已提交合法零与缺失、不同身份和不同时标，usable() 继续通过。 PC 963 项计数原生断言、滤波诊断窗口与 V1 实录连续性夹具均通过。Python 59 通过，4 项历史 IF 诊断按约束未运行。Android x86_64 模拟器原生 617 项通过，构建了 arm64-v8a 和 x86_64 独立测试；App 四 ABI 重建。JVM 165 通过、3 项外网集成冒烟跳过、0 失败。 arm64 实机未运行，APK 未安装。正式 PC 复跑四个小米包 V2，2,623 期 × 17 列与第三轮逐历元表逐字节一致。10:01/10:04/10:41/11:20 分别 119/1466/63/587 个 Q6。逐包 corrections.csv、observations.csv、solution.stat 与私有修正逐字节一致，solution.csv 除 processing_ms 外逐字段一致。 [PC 验证报告](ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/REPORT.md) · [三轮诊断索引](ntrip-ppp-closure-20261117/pc-docs/PPP_INVESTIGATION_INDEX.md)
11/14 从连接的小米 `2407FRK8EC` 取回四个当日采集包。采集包和该机实际 APK SHA256 均为 `04071a6c54e1fdf9e2af09e8ac24c461f81ef7f94ee1400d097ee7a65d3c01bf`，仍采用旧启动规则。PC 复现 2623 期状态，1141 个 Q6 最大坐标差 1.15 µm。11:20 真机首解 268.96 s、293 Q6、全 Q6 水平 RMS 0.608 m；新规则 PC 同包首解 14.80 s、488 Q6。10:04 长段尾部三流无新字节。另定位到轨钟流附带码偏差覆盖独立 WHU OSB 的缓存问题，随后由私有 PC 回放验证，11/17 已同步至正式 PC/Android 本地源码。详见 `E:/GNSS/PPP_NTRIP_PC/validation/android_capture_20261114/REPORT.md`。

11/14 实时 PPP 首解改用 `WHU_OSB_FIRST_COMPLETE_V2`。首份完整 WHU 码偏差到达后，结合匹配的轨钟、广播星历和覆盖当前 GNSS 时间的大气产品进入原 PPP 更新。偏差流重连后须重新收到完整偏差，重复旧估计不会刷新推进计时。记录页显示轨钟、码偏差或广播星历等对应等待状态。`capture.json` 和 `profile.txt` 记录新规则，旧包仍按原规则回放。

11/14 首解策略构建通过，四 ABI 重编译，当时 JUnit 162 通过、6 跳过。PC 使用 10/31 原始三流到达前缀复核，首个 Q6 从 585 秒到 5 秒，末 60 秒 H/U RMS 从 1.822/0.460 m 到 1.691/0.407 m；首个新 Q6 的水平误差 2.499 m、高程误差 +3.192 m。首份偏差绝对时效尚未独立认证。新 APK 未安装，首解仍待真机验证。证据见 `E:/GNSS/PPP_NTRIP_PC/validation/whu_first_complete_20261114/verification.json`。

「记录」页的 WHU 实时留档可设置 1～30 分钟，默认 30 分钟并记住上次设置。开始采集后显示剩余时间，到点沿用现有停止、排空和 ZIP 保存流程。实际录制区间从 Raw 注册成功到请求停止计算，另保留排空结束时刻。手动停止和现有异常保护仍可提前结束会话。

`capture.json` 已包含开录时设定的 WGS84 参考及高程类型、设定与实际时长、停止原因、首末有效 Q6 的 GPST 和可用时间、各 Q 数量、未返回解算结果的已处理历元数、产品准备和覆盖失败摘要、各流连接次数与首帧时间。无参考或无 Q6 时对应字段为空。Raw、三流、`arrivals.csv`、`epochs.csv`、时钟锚点、误差序列、软件指纹和实际产品快照继续通过原格式保存。下一包以同机同点 30 分钟为主，用前后窗口比较北偏是否持续。

本轮编译与 JUnit 通过，PC 导入器接受新版 Android 生成的测试 ZIP。当时 ADB 无可用设备，计时到点、自动打包和实时出解尚未进行新版真机验证。证据见 `tools/ntrip_timed_capture_20261114/verification.json`。

## 地图阶段
11/11地图页已接入高德嵌入底图，复用FTPGet已验证的单点标注转换与WebView iframe方案。设备、最新有效实时Q6、有效后处理解进入地图显示状态，实时结束回到设备来源。坐标卡显示WGS84原值，GCJ-02仅用于地图标点。iframe随`window.innerHeight`和resize更新。同源坐标至少间隔5秒刷新，触摸时延后；来源切换立即请求新标点。

WHU设置、实时启动和配套留档集中在「记录」页。「定位」页保留设备位置、PPP结果、后处理和参考坐标。按用户后续要求移除了应用自己的外部地图入口及「回到定位点」按钮。

vivo V2507A已安装本次Debug构建并核对APK指纹。真机验证了设备标点、道路建筑、双击放大、拖动，以及记录/定位页入口分布。真机产品目录中当前预报文件仍为10月旧期，本轮未实测真实PPP出解后的来源切换。证据见`tools/amap_map_20261111/verification.json`与`vivo_final_map_check.png`。

## 精度工作记录
用户随后授权的完整PPP产品精度对比也已完成，报告 E:/GNSS/PPP_NTRIP_PC/docs/NTRIP_FULL_PRODUCT_COMPARISON_20261110.md，证据validation/ntrip_full_product_comparison_20261110/。7组669期、均585Q0/84Q6，三族各配同输入WHU控制，保留原启动/非组合/显式电离层及参数策略，仅私人PC入口实际解算，Android源码/APK不变。
同末60s H/U：正式WHU1.822/0.460m；CODE OPS1.616/3.133m（同输入WHU1.882/3.605）；CODE MGX2.320/6.317m（1.814/2.334）；GFZ GBM快速产品2.498/1.182m（2.786/3.659）。没有全面优于正式的方案，不迁移/设默认。配对观测/支持掩码一致，全部SSR释放与正式控制一致；未混中心或补零缺失OSB。新6定向及59允许Python通过、0跳过，禁止4项未执行；无正式原生全套/Android构建/JUnit/安装，52项PC正式快照/两端33pin/原9项修改/本地APK均不变。
此前11/10先完成PC独立中心码产品查询，报告 E:/GNSS/PPP_NTRIP_PC/docs/NTRIP_INDEPENDENT_CODE_REFERENCE_20261110.md，证据 validation/ntrip_independent_code_20261108/。该查询阶段没有PPP回放；后来完整解算见上文，不能混用两阶段范围。CODE OPSFIN/MGXFIN及GFZ GBM都是采集后产品，不代表在线可用。
G/E去公共项产品差RMS0.270m；CODE MGX北斗5P差7.836m但参考不同，GFZ同2I/6I参考的504条2I差RMS1.493m，该组首期局部ΔE−0.158/ΔN+0.120/ΔU−1.731m，尚未消除水平偏差。三族独立支持证据并集2436/2688，剩余G01/G28的5Q及C06的2I共252条，未混中心补齐、未补零；优先追北斗码OSB—钟差—显式电离层参考衔接。
本阶段已完成用户要求的WHU相位OSB处理链接入，详见PC的docs/NTRIP_PHASE_OSB_FLOAT_CHAIN_20261108.md。PC因果验证后同步Android并成功构建，未安装。
用户最新明确禁止后续考虑双频无电离层组合（IF/IFLC），定位、候选及旁路诊断/对照均不再采用。继续非组合模型、显式处理电离层；旧组合结果仅为历史。
用户明确不考虑模糊度固定。本次接通现代相位解码、独立缓存/连续性、信号参考断点与浮点相位改正，modear仍OFF，ppp_ar为空实现；R/Q/P0/GIM/抗差和原启动规则不变。CLK3.04仍为文件旁支，不作为主线。
10/31正式窗口2186条相位最终提交中1385条G/E应用相位OSB；801条C因重复信号歧义或无确切支持保留原浮点参考，不补零/重映射。开关均585Q0/84Q6，水平RMS仍约1.822400m，没有精度修复结论。
此前正式审计、等待期历史/共享R/Huber等负结果已完成，保留原报告，不重新排查或迁移；历史消电离层诊断不再运行。
最终应用目标为手机实时非组合PPP，B_VERIFIED，轨钟/偏差来自WHU实时流，大气用预报文件，保留完整PC回放资料。
此前非组合部分固定提案已按用户要求停止，仅作历史，不作为后续任务。

## 实际模块和入口
|模块|代码地址|
|---|---|
|定位UI与配置|app/src/main/java/com/example/ftpget/MainActivity.kt 与 ui/|
|在线PPP串行处理|app/src/main/java/com/example/ftpget/LiveSsrSession.kt|
|三流连接/采集/留档|同目录 NtripClient.kt、NtripCaptureService.kt、NtripCaptureStore.kt|
|原始GNSS与RINEX|同目录 GnssDataLogger.kt、RinexConverter.kt|
|JNI实时桥|app/src/main/cpp/gnss_jni.cpp|
|SSR处理|app/src/main/cpp/ntrip_ssr.cpp|
|共享解算核心|app/src/main/cpp/ppp_live/rtklib/|
|来源清单与构建保护|该核心 ntrip_profile.sha256 和 app/src/main/cpp/verify_ppp_profile.cmake|

包名 com.example.pppntrip，Kotlin namespace com.example.ftpget。
CMake中 gnss_ppp_live 是启用PPP_NTRIP_SSR的实时库，rtklib_engine为事后处理库。
旧 cpp/rtklib 是另一个目录，不作为本实时核心。

## 已实现并保留
- 当前MainActivity/LiveSsrSession实际WHU配置为SSRC00WHU0(CoM)+OSBC00WHU1、广播BCEP00BKG0。
- 实时PPP和完整录制链已经实现。README_NTRIP中“只采集/尚未启用/默认BKG”属于旧阶段。
- Raw排空、三流字节和到达/应用顺序、clock anchors、实际产品快照及软件指纹已纳入留档和PC回放。
- BDS SSR布局/BDT时标/广播匹配、WHU独立OSB、GIM几何与CODE约定、ANTEX身份保护已有修复证据。
- FIXED_CLOCK_2023已移植并启用，Native共享结构调用方已重建的记录保留。
- 10/31真实手机/PC回放669期，观测逐行匹配、坐标差小于0.8微米，证明实现链一致，未达到持续亚米级精度验收。
- Gradle的testClasses别名和Maven镜像已存在，旧“找不到任务/直连403”的修复不应重复实现。
- 相位链四个共享文件及NtripSsr已同步，33项核心pin与PC全部匹配；Android头保留显式ppp_live/rtklib/rtklib.h路径，未误引旧内核。
- 旧“仅5项诊断变化/两端ntrip_ssr未改”为11/7历史边界，现阶段已有正式相位链修改；证据在PC的validation/ntrip_phase_osb_20261108/verification.json，旧清单不覆盖。

## 正式与候选必须区分
- 当前本地 App 已单独接入首份完整码偏差启动规则。10/31 的旧真机包仍按连续两份估计的旧规则记录，约 585 秒首次 PPP。
- 正式观测准入仍排除BDS1P，独立PC state_activity_fix_v2才启用B1I+B1C独立槽。
- V2另修复零状态漏激活。候选989项检查记录通过，实际回放米级东偏仍在。
- 候选位置 E:/GNSS/PPP_NTRIP_PC/validation/b1c_joint_consistency_20261031/state_activity_fix_v2/。
- 11/11 vivo真机已核对安装APK与地图阶段本地Debug构建一致，验证范围为页面和地图交互。
- 流内未确认完整实时电离层/对流层服务，当前预报大气链不能描述成大气SSR。

## 构建、测试和产物
在本根目录运行
```powershell
.\gradlew.bat :app:testDebugUnitTest --console=plain
.\gradlew.bat :app:assembleDebug --console=plain
```
testClasses仅编译测试源，不执行测试。Wrapper为Gradle8.11.1，Java/Kotlin目标11，Android compileSdk36/minSdk28/targetSdk35。
原生NFREQ=4、ENAGLO、无ENAQZS，C/C++ signed-char，共享头修改后要重编译所有受影响调用方/ABI。
当前仓库镜像配置见settings.gradle.kts，凭据仅从忽略的本地properties读取，不复制其内容。
本阶段PC完整重建，905项原生及观察器检查通过，允许执行的Python49项通过/0跳过，4项历史消电离层诊断按用户约束未执行。Android assembleDebug --offline成功：布局变更后四ABI完整构建1m11s，最终raw/raw保护变更再次构建4s。未重跑JUnit、未安装。此前768/22/53等数字按原阶段解释。
上述构建是11/8相位阶段历史记录。11/10独立产品阶段新增4项定向测试及允许的Python全套53项通过、0跳过，禁止的4项未执行且不计通过；三族native产品查询各84期、FILTER_CALLS=0。没有重跑原生全套/Android构建/JUnit，正式46项PC快照及两端33项pin、Android原9项已跟踪修改和本地APK SHA均未变，只同步本交接文档。

11/14实际执行`:app:testDebugUnitTest :app:assembleDebug --offline --console=plain`，构建通过。JUnit汇总168项、0失败/错误、6跳过，定时与采集摘要测试通过。Android测试包保留参考及设定时长，PC导入成功。
本地Debug APK在 app/build/outputs/apk/debug/app-debug.apk，11/14 首解提速构建，SHA256为69a1640afce33ed6977dcb73ddf2b09bf56f579814e09ee4f2df40d88f3ec66e。个人Debug按原有本地用途保留。
11/14 重新通过 ADB 核对 vivo V2507A 实际安装，APK SHA256 `04071a6c54e1fdf9e2af09e8ac24c461f81ef7f94ee1400d097ee7a65d3c01bf`，与当天四包一致，仍使用旧启动规则。PC 完整复现，11:20 段全 Q6 水平/高程 RMS 为 1.165/2.142 m。见 `E:/GNSS/PPP_NTRIP_PC/validation/vivo_capture_20261114/REPORT.md`。11/11 地图构建安装为历史记录。
本地release产物是 app/build/outputs/apk/release/app-release-unsigned.apk，未签名发布包。
真机版本与精度验收状态需按新的任务重新核验，旧报告的“未授权/已安装”不作当前连接状态。

## 剩余问题和已排除方向
- 精度仍存在米级持续偏差，近期小米主要东偏，同期vivo方向/高程不同。
- 正式小米链末60s E RMS1.006m、N RMS1.519m、H RMS1.822m。首次北向由先验+0.317m变为后验−1.637m，其中码更新贡献−1.928m；不能只沿用提前启动候选的东偏结论解释正式结果。
- 本轮正式4874条GNSS提交行来源/轨钟IOD/9～17s年龄/码偏差有效及实际频率天线支持核对通过；2186条相位中2148条活动弧、38条重建（含初始化）。没有发现可据此安全修复的米级公式/索引错误。
- 部分码新息时间相关，但正式Doppler平滑本身也会造成相关；新持续误差方法须先证明可辨识性，尚未作为估计候选实施。
- PC追加独立预测新息Huber候选，正式窗口水平RMS1.822400→1.824255m未改善，12项定向检查通过。候选不采用、不迁移，App的抗差、估计器和本地APK没有因此改变。
- 新模型/数据来源需绑定具体采集与高程，不能复用别点真值。
- 两个旧产品路径同属WHU。11/10已完成DOY304的CODE/GFZ部分确切支持对照，北斗码参考差异和252条覆盖缺口保留，不能再写成完全没有独立中心资料，也不能声称绝对参考已全部认证。
- 正式共享rinex.c的CLK3.04偏移错误已确认但未正式修复，实时SSR不调用该文件CLK入口。
- 文件对照中的OSB/天线回退尚未完整认证，不能为了曲线自行补零或套用其他频率标定。
- 100ms发送时标、GAL7Q ADR/PRR、Native异步/零哨兵限制仍需明示。
- DOP、G25大残差、SPP位置直接记忆、B1C零状态、三种30s启动方案均已有结果，不能当成待重查任务。
- 同期测量型接收机记录用户已确认没有，放置与参考按当前用户条件固定。
- 参考/实时有效性/独立数据覆盖不足须保留为证据边界，不将候选精度改善写为已解决。

## 下一步与验收
- 用 11/14 首解提速 APK 采一段同期数据，比较开录、首份有效三流、首个 Q6 的间隔及首解后误差。按 `epochs.csv`、`arrivals.csv`、`capture.json` 核对停等和重连；首解提速与达到稳定精度分别验收。
- 当前接续先读PC正式NTRIP84期审计，复用已保存矩阵/提交行，不重复P0/R/删星/平滑/启动试验。
- 追加11/8后续报告和负结果也须复用；不把等待期历史或同星共享R的小幅单段变化直接作为默认精度修复。
- 相位OSB浮点链、独立CODE/GFZ产品查询和随后完整PPP精度配对都已完成，不自动推进固定。复用E25/E26逐行与完整轨迹，不重做同段三族或旧调参；不能将局部矩阵估算当作实际精度，也不能再说独立产品尚未实际解算。北斗码OSB与显式电离层参考仍待实际兼容证据。相位1385应用/801回退保留，旧完整K/R来自11/7关闭基线。CLK3.04、GFZ C2/C3标签和新确认的预检CLK天线模型多词解析兼容仍是文件旁支，只在私人PC入口处理，正式实时链未改。
- 同步候选到手机前，明确B1C、启动规则、零状态修复哪些实际入库，并保留旧正式回放作为控制。
- 如果任务是会话连续性，先用日志确认页面/后台/短断流是否无必要重建引擎，已有一小时连续对照可复用。
- 所有精度方案验收完整E/N/U、持续收敛、有效历元、产品关联与失败保护，另需新时段独立验证。
- 本轮已完成授权的相位链同步、构建和PC因果验证；后续不自动安装APK或把未经验证的精度候选移植到手机。
- 11/8未授权状态为历史。11/11 vivo已通过ADB进行地图验收并核对安装指纹，本次未采集新的实时PPP包。

## 精简证据索引
- 最新实际完整PPP精度配对 E:/GNSS/PPP_NTRIP_PC/docs/NTRIP_FULL_PRODUCT_COMPARISON_20261110.md，不能单看OPS水平或GFZ东向误差认定正式精度已修复。
- 最新独立中心核验 E:/GNSS/PPP_NTRIP_PC/docs/NTRIP_INDEPENDENT_CODE_REFERENCE_20261110.md及validation/ntrip_independent_code_20261108/verification.json，正式水平RMS仍1.822400m。
- 观测生成 docs/ANDROID_OBSERVATION_GENERATION_NTRIP_REPORT.md 及 tools/observation_generation_ntrip_20261030/verification.json。
- Gradle docs/GRADLE_TESTCLASSES_FIX_20261030.md、tools/maven_403_fix_20261030/verification.json。
- 实时链 docs/ANDROID_WHU_SSR_FORECAST_INTEGRATION.md、docs/WHU_OSB_COMPATIBILITY_FIX_REPORT.md。
- 最新精度与候选以 E:/GNSS/PPP_NTRIP_PC/docs/CURRENT_STATE.md 的按任务索引为准。
- 整理前AGENTS和本轮Git/源码/测试核验在 E:/GNSS/PPP_NTRIP_PC/docs/handoff_archive/20261107/。
- 10/18旧CODEX_HANDOFF与旧台账保留，仅作历史，不自动加载其分叉前上下文。
