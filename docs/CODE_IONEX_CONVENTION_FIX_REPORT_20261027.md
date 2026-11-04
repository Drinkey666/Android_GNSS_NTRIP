# CODE IONEX 产品约定修复及实际 SSR 偏差复核

2026-10-27；活动工程 `E:/GNSS/PPP_NTRIP_PC`、`E:/android/test/PPP_NTRIP`。

**本轮找到了并修复了确定的产品约定不一致，但没有解决约 9 m 高程偏差。** 原程序对声明采用 CODE 修正单层模型、地心纬度格网的 IONEX，使用普通 450 km 单层映射和球面近似穿刺点。修正后同一官方 ANTEX 下末期 Up 从 +8.2161 m 变为 +9.0426 m；旧近似在此数据中存在误差抵消，不能按更小坐标误差选公式。

新增证据、完整轨迹、测试日志和修复前源码统一保存在：
[validation/code_ionex_geometry_fix_20261027](E:/GNSS/PPP_NTRIP_PC/validation/code_ionex_geometry_fix_20261027)。

## 1. 本轮实际完成的工作

1. 冻结修复前 11 个源码/程序文件及 SHA256，没有覆盖此前可运行程序。
2. 以捕获内原始 IONEX 头和 CODE/Bernese 一手资料确认模型约定；实现 PC/Android 共享几何计算。
3. 独立高精度公式、射线/球面几何不变量及正常/异常文件测试。
4. 完成五份各 701 输入历元的独立回放：旧约定复现、原天线新约定、官方天线新约定、较晚 P0D、次日 RAP。已有官方天线旧约定结果直接复用。
5. 新约定下补充三份各 701 历元的精简固定坐标闭合：关闭条件化控制、固定坐标预报 GIM、固定坐标 RAP。它验证新公式下状态冲突是否仍存在，没有重做旧 P0/R/CN0 消融。
6. 用已保存的真实 SSR 快照及已独立解码的 140 个 BDS 偏差帧，核对时钟参考频对；新增实际码改正函数的未使用信号偏差隔离测试。

没有修改 R/Q/P0 的公式或参数、Joseph、抗差机制、码平滑、卫星屏蔽策略；没有启用新 Huber/eta/自适应 R。修正的是实际电离层物理映射，因此不能再称本轮“正式算法完全未变”。

## 2. 确定错误：产品与使用者约定不一致

捕获文件：`validation/android_long_20261025/imported/product_ionex.INX`，原名 `COD0OPSP1D_20262980000_01D_01H_GIM.INX`，SHA256 `fb0786e6cb618c9526130248a76c1c59c6f3597deb461ce47371ad430c1859f4`。

其头部明确声明 CODE、modified single-layer model、以 geodetic elevation 计算映射、6821 km 穿刺点球面以及 geocentric 而非 geodetic 格网纬度。IONEX 的格网高度 450 km 与映射函数的有效高度不同；不能因为格网标注 450 km 就直接认定映射也应使用 450 km。

[Bernese 官方手册 §13.3、式13.8](https://www.bernese.unibe.ch/docs/DOCU52.pdf) 给出的 CODE 约定为：

`z = π/2 - elevation_geodetic`

`M_CODE = 1 / sqrt(1 - [6371/(6371+506.7) × sin(0.9782×z)]²)`

穿刺点另采用 `R_IPP = 6371+450 = 6821 km`。这些数值来自产品模型定义，没有用本次坐标真值拟合。手册页面内容由官方站点可检索文本核实；本轮没有声称完整下载其大 PDF。

旧路径的问题是：`ppp_iono_mapf()` 调用普通 `ionppp()`；`iondelay()` 同样按普通单层模型处理。普通函数直接把输入测站大地纬度用于球面穿刺点，没有按声明的地心格网生成穿刺点。旧程序两边使用相同近似，代数闭合可以通过，但这不能证明它符合产品的物理约定。

修复位置：

| 文件/函数 | 当前位置 | 内容 |
|---|---:|---|
| [ionex.c](E:/GNSS/PPP_NTRIP_PC/core/ionex.c:31) `ionex_geometry_select()` | 31 | AUTO 按产品声明选择；LEGACY 可复现；混合不兼容约定明确失败 |
| [ionex.c](E:/GNSS/PPP_NTRIP_PC/core/ionex.c:49) `ionex_geometry()` | 49 | 共享 CODE MSLM；测站 WGS84 ECEF 与大地 ENU 视线交地心球面，再生成地心纬经度 |
| [ionex.c](E:/GNSS/PPP_NTRIP_PC/core/ionex.c:233) `readionexh()/readionexb()` | 233 起 | 从生产者及描述识别，逐图保存 convention；不按文件名猜测 |
| [ionex.c](E:/GNSS/PPP_NTRIP_PC/core/ionex.c:524) `iondelay()` | 524 | TEC 查询使用相同几何；时间插值和原日固坐标旋转保留 |
| [ppp.c](E:/GNSS/PPP_NTRIP_PC/core/ppp.c:2407) `ppp_iono_mapf()` | 2407 | 状态初始化、GIM 先验换算、GNSS 电离层项及 H 共用该映射 |
| [ppp.c](E:/GNSS/PPP_NTRIP_PC/core/ppp.c:3062) `model_iono()` | 3062 | 无效几何返回失败，不能把零映射当正常电离层改正 |
| [gnss_replay.c](E:/GNSS/PPP_NTRIP_PC/src/gnss_replay.c:409) | 409、411、427、441 | 读产品前后显式选择和验证约定 |
| [Android JNI](E:/android/test/PPP_NTRIP/app/src/main/cpp/gnss_jni.cpp:114) | 114、135、534 | AUTO 加载及软件记录追加产品约定/修订标识 |

另外修复 `readtec()` 无效头部失败分支未关闭文件的确定句柄泄漏；100 次无效输入回归通过。它属于异常文件安全问题，没有证据认为它造成了此次 9 m 偏差。

本次未修改通用 `ionppp()`：未声明 CODE 约定的产品及 LEGACY 分支保留原计算。生产者声明、modified、geocentric 三项须匹配；声明 CODE 但层高不符合已支持约定时明确报错。没有把所有 IONEX 强行当 CODE。

## 3. 误差量级与完整回放

同一 Xiaomi 2407FRK8EC 采集包、实际 WHU `SSRC00WHU0`+`OSBC00WHU1` 及原广播流。参考为用户给定 30.69820588888889°、104.05203827777777°、**椭球高459.813 m**。普通回放真值只用于解后 ENU；固定坐标实验单独标注为已知位置条件化，不作为定位精度结果。

9781 个已保存卫星/历元几何查询中，有 8509 个匹配旧控制组实际提交的真实 GNSS 行。后者新旧斜向电离层差为 **−1.6478～+0.0876 m**，中位数 +0.00683 m；地心 IPP 纬度变化约 −0.1619～−0.0662°。有符号中位数很小不代表低高度角影响很小。

分解 `Δslant=(M_new−M_old)I_old + M_new(I_new−I_old)` 最大闭合误差 3.78e−15 m。独立模型采样使用固定参考几何，仅用于约定诊断，不把它混作实际自由解的原始新息。

| 组 | 最后水平误差 m | 最后 Up m | 前60秒 Up RMS m | 60～300秒 Up RMS m | 300秒后 Up RMS m | 最后60秒 Up RMS m |
|---|---:|---:|---:|---:|---:|---:|
| 旧天线、LEGACY | 2.1200 | +9.0672 | 8.5380 | 8.9156 | 9.2530 | 9.1725 |
| 旧天线、AUTO CODE | 2.1360 | +9.9040 | 9.4636 | 9.8242 | 10.1320 | 10.0219 |
| 官方天线、LEGACY（已有结果） | 1.9184 | +8.2161 | 8.5774 | 8.6231 | 8.4794 | 8.3624 |
| 官方天线、AUTO CODE | 1.9253 | +9.0426 | 9.4973 | 9.5239 | 9.3447 | 9.2001 |
| 官方天线、AUTO、较晚P0D；非实时实验 | 1.8923 | +8.7915 | 9.2376 | 9.2468 | 9.0823 | 8.9465 |
| 官方天线、AUTO、次日RAP；非实时实验 | 2.1022 | +8.2227 | 8.6303 | 8.6903 | 8.5386 | 8.4167 |

时间以首次 PPP 为零；包含一次 Q5，不能把所有有效行都声称为 Q6。各组均701输入：223Q0、1Q5、477Q6；没有记录到 NaN/Inf、NON_PSD 或 filter error。统计限于已有数值诊断覆盖，不声称对全部后验重新做了独立特征值审计。

同官方天线控制相比，几何修复后的 post-fit reject 日志事件1076→1079，ARC_RESET事件1386不变，Doppler slip事件4不变。旧天线1075→1078、ARC_RESET1381不变、Doppler slip2不变。这里是**日志事件数**，不冒充独立卫星/弧段数。物理映射改变残差后，已有抗差/编辑分支可以自然改变；没有新增拒绝规则。

天线产品变化也改变可用卫星记录：旧天线观测日志16371行，官方天线17161行（均不计表头）。因此只在相同天线控制下要求观测日志相同，不能把不同天线组伪称同一行集合。

![同一实际SSR的约定对照](E:/GNSS/PPP_NTRIP_PC/validation/code_ionex_geometry_fix_20261027/convention_control.png)

完整 [ENU时间序列](E:/GNSS/PPP_NTRIP_PC/validation/code_ionex_geometry_fix_20261027/enu_timeseries.csv)、[统计及校验](E:/GNSS/PPP_NTRIP_PC/validation/code_ionex_geometry_fix_20261027/analysis.json) 已保存。

## 4. 较晚 P0D 与次日 RAP 的用途和局限

仅通过 CODE 官方 HTTPS 有界获取，保留响应时间、SHA、原头部和失败状态。没有重新开展 FTP/RTS 档案下载。

- [P0D来源](https://download.aiub.unibe.ch/CODE/IONO/PRD/COD0OPSP0D_20262980000_01D_01H_GIM.INX.gz)：本次下载版本 Last-Modified 为10月25日06:21:29 UTC，晚于采集结束06:17:44.999；不能据此证明同版本在实际采集中可用，也不反推当时是否存在另一个早期版本。
- [RAP来源](https://download.aiub.unibe.ch/CODE/COD0OPSRAP_20262980000_01D_01H_GIM.INX.gz)：Last-Modified 为10月26日06:20:44 UTC，使用次日分析信息。
- 捕获的 P1D 为2日预报，不是因名称误判而读了错误日文件；命名依据 [CODE官方通告](https://lists.igs.org/pipermail/igsmail/2026/008735.html)。

这两份仅作事后物理诊断，不替换捕获、手机默认文件或声称实时性能改善。始终使用原来记录的真实 WHU SSR，没有换成 NRT，也没有拿 raPPPid 的文件路径冒充实际 SSR。

RAP 相对 P1D 在匹配实际 GNSS 卫星/历元的 L1 斜向差约 −0.0787～+2.0886 m，中位数+0.6682 m。RAP 垂直方差0.1787～0.3283 m²，全部低于原2.25 m²基础先验下限；没有通过降低基础先验方差改善结果。轨迹反馈和旧处罚仍可改变实际有效 R。

RAP 回放仍有 +8.2227 m Up；**不能把全部9 m归因于预报GIM值，也不能把次日分析当电离层真值。**

## 5. 新约定下的固定坐标闭合

独立程序只在 `udpos_ppp()` 将位置及协方差精确条件化到外部参考；其余状态、模型和参数保留。使用当前完整构建的头文件和对象，不重新链接旧 ABI 的快照。关闭条件化的控制，701个历元除耗时字段外、状态/观测/改正日志逐字节与新正式 AUTO+官方天线一致。

| 固定坐标实验 | 最后总ZTD m | 最后ZHD m | 最后估计ZWD m | VMF预报ZWD m | 总ZTD形式sigma m |
|---|---:|---:|---:|---:|---:|
| CODE P1D预报 | 4.2977 | 2.1644 | 2.1332 | 0.1996 | 0.0876 |
| CODE RAP；非实时诊断 | 4.1927 | 2.1644 | 2.0282 | 0.1996 | 0.0873 |

三份各701输入、478提交，无新增数值失败。不是负总ZTD、也不是把湿改正量误读成总量：当前 B_VERIFIED 存储总ZTD，ZWD=ZTD−独立ZHD。

这证明**坐标固定后仍有约1.8～1.9 m的额外湿延迟由联合状态承担**，修正映射、甚至改用次日 GIM 分析都没有消除。它不是仅靠换一份更准 GIM 就已解决的问题。没有当地独立水汽真值，不能把差值的全部物理来源强行分配给某个接收机偏差或某颗卫星；但实际总ZTD与外部先验的强冲突仍存在。

![修正模型下的固定坐标湿延迟](E:/GNSS/PPP_NTRIP_PC/validation/code_ionex_geometry_fix_20261027/corrected_fixed_reference_trop.png)

[固定坐标状态序列](E:/GNSS/PPP_NTRIP_PC/validation/code_ionex_geometry_fix_20261027/corrected_fixed_reference_trop_timeseries.csv)。固定位置实验没有“零定位误差”的验证意义。

## 6. WHU 码偏差与时钟参考复核

[IGS实时产品官方说明](https://www.igs.org/rts/products/) 给出的参考信号为 GPS1W/2W、GAL1C/5Q、BDS2I/6I；本地 `NtripSsr::setReference()` 与之相符。[WHU发布通告](https://lists.igs.org/pipermail/igsmail/2024/008420.html) 说明 OSBC00WHU1 固定使用 SSRC00WHU0 的轨钟，支持当前配套策略。

本轮读取已有34个首末卫星快照，没有重新录流。GPS RAP IONEX AUX 提供的 `C1W−C2W` ns转换为m，与 `−(SSR_cbias1W−SSR_cbias2W)` 比较：9颗卫星、17个快照，最大差0.113649 m。没有看到统一米级GPS双频DCB基准错位。这不验证GPS所有信号绝对OSB，也不外推到没有AUX数据的北斗/伽利略。

按参考频对计算 `c1*bias1+c2*bias2`，C12末期组合约+26.2692 m，是需要保留的产品基准疑点。已有140个RTCM1260帧的独立比特解析证实 `B1I=-1.37 m、B3I=-15.59 m` 是实际收到的值，没有新发现本地解码/符号/数组错位。

**但当前C12只有477条B1I记录，无B3I观测。** `corr_meas()` 和 SSR `prange()` 仅取当前实际code的cbias；时钟参考的天线换算使用频率/PCO，不读取参考频对cbias做额外减法。新增13项实际函数测试中，将未使用B3I值改成0、+12345、−9876 m及无效，B1I输出完全相同；只有B1I自身无效才禁用对应码。

因此：不能将26.2692 m直接从已使用码中扣除，不能把异常频对组合当当前9 m的已证实原因。此消费者侧隔离也没有证明上游C12钟差或B1I标定正确；仍归为**证据不足的产品参考疑点**。

## 7. 测试、复现和影响范围

- PC全构建：579 SSR、40时序、15滤波安全、121新几何、13新参考隔离，**768项通过**。
- Python：35项通过。
- Android：`testDebugUnitTest assembleDebug` 成功，4 ABI；144报告项、140通过、4跳过、0失败/错误。
- 32份PC/Android归一化核心源码pin全部匹配；相对上一验证版本只改变 `ionex.c/ppp.c/rtklib.h` 三份共享核心。`rtkcmn.c`及Joseph未改变。
- 新APK SHA256：`965a3ddcc091581c2719cd856b170181b35a178187848167513ece751cb753fd`，**未安装到手机**；旧报告23985e...为历史版本。
- 原始捕获ZIP SHA256仍为 `2014e459041de79261c738401ccffafbb94af39104fb5a3ca5a9edd52b5f02c0`。
- `LEGACY` 回放701历元的全部解算字段（除运行耗时）相同；状态、观测、改正日志**逐字节相同**。不能把这条结果泛化为本轮未重跑的原PPP_only全部A/B/new数据保持相同。
- 两个活动副本没有Git仓库，本轮未提交、推送或覆盖原PPP_only/FTPGet。

PC旧行为复现：在相同原捕获产品输入下，环境设置 `RTK_PPP_IONEX_GEOMETRY=LEGACY`；`AUTO`或不设置使用产品声明。未知选项明确失败。Android正式路径显式AUTO，新nativeProfile记录约定版本。

可复用命令（PowerShell，PC活动工程下）：

```powershell
& .\tools\plot_venv\Scripts\python.exe .\tools\analyze_code_ionex_geometry_fix.py
# 仅重新汇总已有证据，不重跑滤波、不联网、不动手机。
& .\tools\plot_venv\Scripts\python.exe .\tools\build.py --test
```

`run_code_ionex_geometry_validation.py` 与 `run_corrected_geometry_fixed_reference.py` 的显式回放开关均拒绝覆盖已完成目录；不必再次运行。完整源码变化及APK校验见 PC `analysis.json` 和 Android `tools/code_ionex_geometry_fix_20261027/verification.json`。

## 8. 当前准确结论与下一步边界

**确定且已修复**：CODE产品MSLM/地心格网约定与旧使用者不一致；异常IONEX头失败分支文件句柄泄漏。此前ANTEX版本管理和解析安全修复保留。

**本轮进一步排除的单一解释**：不是仅改正GIM映射就能消掉9 m；不是仅把2日预报换成1日/次日分析就足够；不是把C12未使用B3I异常值直接代入本地参考频对修正就有依据；没有发现本地GPS双频DCB统一米级错位。

**剩余最有证据的机制**：非共同的码/相/参考不一致与电离层、星座钟差、接收机码偏差、对流层和高度的联合分配。新几何下已知位置仍需2.03～2.13 m湿延迟，说明外部大气先验与完整观测/状态系统的冲突持续存在。此前原始通道差分、双频代数闭合及GIM方向实验是相关证据，不能从中唯一指定一个硬件或卫星物理项。

**尚无证据可直接正式修复某个接收机码偏差/WHU钟差公式。** 不把额外卫星剔除、放松先验、改R/Q/P0、手工扣常数或限制高程当作已验证的答案，也不将剩余9 m声称已经解决。现有单段数据对未建模码偏差与外部先验/联合状态的归因仍不足；继续重复同段权重/参数消融不会补足独立标定证据。

历史报告的“源码/APK未变”描述仅适用于各自当时的版本。旧GIM方向和综合审计结果使用LEGACY几何，保留用于追溯；当前版本以本文和新校验收据为准。
