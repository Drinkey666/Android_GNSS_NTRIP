# 当前手机 WHU SSR：综合检查、确定修复与剩余偏差

> 后续版本说明：本文轨迹使用现名 LEGACY 的电离层几何。此后正式修复了 CODE 产品 MSLM/地心格网约定及无效IONEX头句柄泄漏；当前APK/核心已更新，详见 [最新修复及完整回放](E:/GNSS/PPP_NTRIP_PC/docs/CODE_IONEX_CONVENTION_FIX_REPORT_20261027.md)。本文旧版本的校验收据继续保留，不再视作当前APK校验。剩余约9m偏差仍未解决。

后续已完成更具体的 GIM 基准/空间方向因果检验，见 `SSR_GIM_GEOMETRY_CAUSAL_REPORT_20261027.md`：单个北斗高度角相关先验方向在两种天线产品下均产生约3.1m轨迹效应；GPS/Galileo同类控制无改善。正式版本未再修改，精度尚未解决。以下原始结果保留，不重跑。

整理日期：2026-10-27。**本批可复用证据、受控回放、解析安全检查及 Android 修复已经统一完成。约 9 m 高程偏差尚未得到唯一物理归因，不将更好看的诊断曲线当作正式修复。**

## 1. 范围与版本

实际项目是 `E:/GNSS/PPP_NTRIP_PC` 和 `E:/android/test/PPP_NTRIP`；不是环境中残留的旧 rtklib_Project2。两份活动副本没有独立 Git 仓库。本批没有修改原 PPP_only/FTPGet、提交、推送、安装手机 APK 或重新录流。

主证据始终是 2026-10-25 手机记录的实际 WHU 三路流：SSRC00WHU0 CoM 轨钟、OSBC00WHU1 码偏差、BCEP00BKG0 广播星历，加冻结的预报电离层/VMF3。保持捕获的到达顺序、applied_seq 和既有时效保护，不提前读未来改正。

- 原始捕获 ZIP SHA256：`2014e459041de79261c738401ccffafbb94af39104fb5a3ca5a9edd52b5f02c0`，最终重新核验未变。
- 本次手机 Xiaomi 2407FRK8EC，不是历史 vivo 独立数据。
- 用户指定参考：纬度 **30.69820588888889°**，经度 **104.05203827777777°**，**椭球高 459.813 m**。全部曲线使用同一 WGS84 ECEF→ENU，参考仅用于解后评价。没有额外独立测量证明其框架/天线偏移；绝对误差以用户给定点正确为条件。
- 当前正式配置 **B_VERIFIED_v2_JOSEPH、非组合、GLO 关闭**，存储总 ZTD；不是历史 PHYSICAL 的湿改正量状态。禁止混用两者日志含义。
- 正式 R、Q、P0、GIM 注入策略、抗差阈值和 Joseph 更新均保持原样。隔离干预未安装进正式算法。

## 2. 已修复的两个确定问题

### 2.1 Android 旧 ANTEX 永久复用

旧内置文件 SHA `fd9955ae17d759291e62e144db8e47a3d4f38bb1d8aae7a8e093fbc6cad0b79f`。旧路径仅检查长度/头部，有文件就一直保留；实际 10/25 使用的 C06/C07/C08/C12 对应 C005/C007/C008/C013，官方日期化元数据应为 C220/C221/C224/C233。原记录缺结束日期，原生按时间搜索也不能排除旧身份。

本批最小修复：

|文件/函数|改动|
|---|---|
|`AntennaProductVersion.kt:14`、`usable()`、`migrateKnownStale():55`|给产品版本和 SHA；只自动迁移字节完全匹配的已知旧内置产品。先验证新文件，旧文件保留唯一 `.bak`；失败不丢旧数据，未知用户产品不覆盖。|
|`BundledProducts.kt:23 ensure()`|先迁移已知旧文件，再判断是否跳过；新内置文件安装前检查 SHA。|
|`LivePppProducts.kt:53 resolveAntennaFile()`|拒绝已知旧内容，即使改名；排除 `.bak`，两个解算入口共用。|
|`LiveSsrSession.kt:106`、`NtripCaptureService.kt:78`|直接启动 SSR 时也在串行工作线程准备版本化产品，再冻结快照和 JNI 初始化；升级后不必先访问下载页。|
|`FtpDownloader.kt:528`|仅澄清产品版本管理入口；不改变改正下载或估计模型。|
|`assets/gnss_products/igs20.atx`、`igs20.provenance.json`|换成已核验官方文件的 414 个完整卫星块，保存来源和哈希，不自拟 PCO/PCV。|

新版卫星子集 5,193,078 字节，SHA `737c46fcfd30b80a8a622f011f88bae779449e6a14781ac6e1a558934004261a`。原资产完整 gzip 备份在 Android `tools/antex_version_fix_20261026/previous_bundled_igs20.atx.gz`。

来源：[IGS 官方 igs20_2437.atx.gz](https://files.igs.org/pub/station/general/igs20_2437.atx.gz)。上游 gzip SHA `22897a9f31449de93e9943cb6ecf3212acf24bde81b1b83cfc3aa648d73a5454`。副本来源元数据随资产保存。

边界：这不是自动认证任意未来 ANTEX 的通用服务。未知用户文件仍需原生日期/信号覆盖检查。仅核验当前 GPS/Galileo/北斗配置；归档中 GLO R10/R28 身份尚不完整匹配独立元数据，GLO 继续关闭；不放开 B1C。

已保存同一完整 SSR 回放，原产品末期 U=9.067215 m，全部官方卫星产品为 8.216095 m。**只更正四个错身份块为 9.207433 m，反而略差。** 所以产品管理缺陷确定，但它不解释全部偏差，全部产品变化的 −0.851 m 也不能归因于四个身份。新产品产生的结果变化是明确的产品输入变化，不是解析器改变公式。复用 `SSR_SATELLITE_IDENTITY_ROOT_CAUSE_REPORT_20261026.md`，未重复此实验。

### 2.2 ANTEX 孤立结束标记生成非法记录

原 `core/rtkcmn.c readantex()` 不检查是否进入天线块，看到 `END OF ANTENNA` 就调用 `addpcv(&pcv,pcvs)`：文件开头可加入未初始化记录，完整块后再来一次 END 会重复旧记录。

修复位于 PC `core/rtkcmn.c:2737–2743` 及 Android 同名核心：只有 `state != 0` 才 append；否则日志记录并忽略孤立 END。不裁剪校准量、不补零缺项，也不改滤波器。修改前后完整源快照和可执行 reader 均保存。

|独立最小输入|修复前记录数|修复后记录数|
|---|---:|---:|
|仅孤立 END|1|0|
|一个完整块|1|1|
|完整块后孤立 END|2|1|
|孤立 END 后完整块|2|1|
|缺 END 的未完成块|0|0|

对官方 414 条产品和捕获原 756 条产品，**全部解析 pcv_t 字节的 FNV64 分别保持 `19fbcab064424bc5`、`d7a107860a7ad7ad`**。不是只比较记录数。此问题在正常本次 ATX 上不触发，不是 9 m 根因。

证据 `validation/comprehensive_audit_20261027/antex_parser/`，工具 `tools/check_antex_orphan_record.py`。原始源码 SHA `47f07c3d2d374642f2c4363fa82e9b59f869b3358faadcf17bccd9e257b3425c`，新源码 SHA `9fe32f57ac4300b7d477a41c7862e2e878848c98d213cb078ef9eec344f89aff`；Android ntrip_profile 只显式更新这一项，其余来源记录保留。

## 3. 真实 SSR 全程分离实验：码与电离层先验强耦合

每组 701 输入历元，从新进程/空滤波器开始。同一原始观测、实际 SSR 和冻结旧产品。方程类别实验**保留全部原始 P/L、卫星几何计算和初始化输入，只跳过指定的方程行**，避免旧“把 P 设零导致卫星相位也不参与”的混杂。私有生成源码和二进制隔离保存。

这里“码/GIM 行去除”是鉴别干预，并非新增永久剔除功能。后续状态、既有编辑和权重会随轨迹反馈变化，不是始终固定同一 P− 的单步效应。

|诊断配置|末期 E / m|N / m|U / m|首 60 s U RMS / m|末 60 s U RMS / m|
|---|---:|---:|---:|---:|---:|
|原 SSR 基线|1.5473|1.4492|9.0672|8.5380|9.1725|
|仅 GPS/Galileo|2.3960|1.2296|4.6592|7.5500|4.6506|
|仅去北斗码方程|2.4536|1.2264|4.4052|7.7567|4.3970|
|仅去北斗相位方程|1.4714|1.5428|9.7673|8.3143|9.8751|
|仅去北斗 GIM 虚拟行|2.2134|1.6514|5.1662|7.9842|5.1514|
|去北斗码及 GIM 行（一次交互检验）|2.4502|1.2340|4.5359|7.7558|4.5198|

均为 223 Q0、1 Q5、477 Q6。类别干预的原始观测 dump 全部与基线字节相同；GPS/Galileo-only 有意改变参与星座，所以其接口观测 dump 不相同。一个 Q5 是已记录约 1 ms 接收机钟跳时段，未隐藏。

全程序列、分段 RMS/偏差、最大偏差和坐标跳变：`SSR_component_enu_timeseries.csv`、`SSR_component_metrics.csv`、`summary.json`。首/中/晚段按首 PPP 之后的实际时间界定，不把等待 SSR 的 223 历元隐藏成零误差。没有事先约定的收敛阈值/持续窗口，因此不事后编造“已收敛到 1 m”。

![真实 SSR 方程类别全程曲线](../validation/comprehensive_audit_20261027/SSR_equation_component_curves.png)

末期交互量 `U(no-code,no-GIM)−U(no-code)−U(no-GIM)+U(base)=+4.031770 m`，明显非加性。去码约 −4.662 m 和去先验约 −3.901 m **不能当独立误差贡献相加**。可确定的是：恢复北斗后的持续附加偏移，与北斗码方程和 I 先验共同参与的状态分配有关；不能仅凭这些结果认定北斗 SSR 偏差符号、GIM 数值或某条相位公式错误。

代码入口：`core/ppp.c:3398 ppp_res()` 的真实码/相位与 IONO_PRIOR 行；`udiono_ppp():2456` 与 `udbias_ppp():2648` 定义其时间状态和弧段。私有 probe 省略行位置由 `tools/run_ssr_bds_equation_components.py` 保存。正式这些函数未改。

## 4. 补齐替代解释，保留失败结果

### 4.1 偏差不是只有载波进入后才产生

独立实验保留原始载波/初始化，但不加入任何载波观测方程：701 历元完成，223 Q0、478 Q5，末期 U **9.635263 m**，末 60 s RMS **9.714039 m**。CLI 因成功条件要求 Q6 返回 1，`run_receipt.json` 明确记录这是该实验预期状态，不是数值崩溃。

这排除了“只要修相位更新或删载波，就能去掉本次大偏差”的解释；不证明载波模型所有细节正确。

### 4.2 公共码相钟差模式不足以解释保存的更新

受手机 PPP 文献关于码相钟不一致的启发，使用 8 个已保存的实际更新，离线剖面化一个未知公共相位偏移 B，不改原预测/R：

`S=HᵀP−H+R; beta=(BᵀS⁻¹B)⁻¹ BᵀS⁻¹v; Δx_extra=−KB beta`。

普通直接解法，无伪逆/正则化。首期 Up 变化 −0.058406 m，末期 −0.000145 m；后续最大绝对变化约 0.002331 m，K/线性求解相对残差 <10⁻⁷。beta 受既有模糊度先验与弧段 gauge 约束，**不是独立测量到的物理接收机钟差**；也不是完整双钟滤波回放。证据不支持据此直接新增双钟状态并声称解决偏差。

方法背景：[Chen et al., Real-time Precise Point Positioning with a Xiaomi MI8 Android Smartphone](https://www.mdpi.com/1424-8220/19/12/2835)。仅采用文献启发，不把其他机型的必要性或参数当本机结论。

### 4.3 Android 上报伪距时间不确定度不能直接作为解决方案

隔离候选只对基础码方差使用 `max(原方差,(c·ReceivedSvTimeUncertaintyNanos·1e−9)²)`，原额外误差/处罚保留，平滑输入和 R0 一致使用该基础量。不是在线学习，不装入正式代码。

API 的该字段为 1σ 时间不确定度，单位 ns，见 [Android GnssMeasurement 官方说明](https://developer.android.com/reference/android/location/GnssMeasurement#getReceivedSvTimeUncertaintyNanos())。首期 G03 原基础 σ≈2.8154 m，而 API 对应约 18.8869 m。候选末期 U **33.504327 m**、末 60 s RMS **33.450179 m**，首 60 s RMS 67.851769 m，明显不能作为本次修复。不是据此声称 API 一定错误，而是现有联合系统中这种替代没有解决问题。

![未采用的候选方案](../validation/comprehensive_audit_20261027/SSR_rejected_candidate_curves.png)

### 4.4 已完成的先验实验只复用，不重跑

见 `SSR_INITIAL_HEIGHT_CAUSAL_REPORT_20261026.md`。首次位置均值设为参考但 P0 不变，末期 U=9.065195 m，几乎不变；仅保留 GIM 初始化而取消其后约束为 12.398088 m；同类 VMF3 初始化-only 为 9.075619 m；仅关闭当前残差处罚为 9.638044 m。均不能单独解决。

首 PPP 根本没有北斗，SPP 初始 Up17.695005 m，首 PPP Up10.077624 m。不能将开局和全程所有误差都归到北斗。未重复旧 P0/R 消融，不搜索参数组合。

## 5. raPPPid/NRT 的适用边界

用户指出当前是 SSR 流，这个质疑成立。raPPPid 本次是文件产品辅助运行，**不能冒充真实 SSR 交叉验证**。已停止扩展这条对照，保留结果而不以它代替实际链路证据。

辅助记录 `validation/current_phone_independent_20261026/`：选用原生 GPS/Galileo 的观测转成 RINEX，NRT 轨钟、归档码 BIA、官方 ATX；raPPPid 478 float，末期 U≈15.224851 m；本项目文件入口 477 Q6+1 Q5，末期 U≈2.157335 m。两者模型、先验、平滑及产品接口不同，不能据末点宣布哪个程序或 SSR 解码有错。RINEX roundtrip 还缺 6 个 P=L=0 的纯 Doppler 行、23 个无相位记录的 LLI，非逐字节等价；有效相位 LLI 相符，数值差在输出精度内。

另外完成的实际 SSR 控制骨架中，**只换轨钟值**为同期 NRT、保留实际流可用性/偏差/权重：GEC 末期 U=8.960485 m，原 9.067215 m；GPS/Galileo 为 4.811303 m，原 4.659169 m。只换 GPS/Galileo 卫星产品方差为 3.953846 m。它们仍是辅助敏感性，不是完整产品基准认证，不声称这些归档在采集时已可用。轨钟数值单独替换在该实验中不能解释约 9 m。

## 6. 综合覆盖清单：已查到什么，未证明什么

|环节|有效证据/结论|边界|
|---|---|---|
|原始字段→TXT→native|已安装采集 APK 的 DEX getter、64 组 P/L/D 映射、64 次平滑递推已有证据，正确单位/ADR 符号；复用不重做。|格式正确不等于物理通道无偏；不强认转换错误。|
|实际 SSR 到达与时效|701 个状态：3 缺改正、220 等 WHU 下一 OSB 估计、478 ready；记录 CRC 全为 0/0。启动等待来自既有保守配套策略，不是滤波算不动。|`corrections.csv release_cutoff_utc_ns` 在 ledger 模式仍是 UTC 代理字段，实际决策应读 epochs/arrivals 的 applied_seq，不用此列反推未来泄漏。此命名限制未改。|
|RTCM/BDS/GNSS 时标与广播匹配|此前真实 1261/1260 报文逐位复核、现代 BDS 广播 IOD/TOC 匹配及 BDT/GPST 修复保留；新跑原生测试。|不因源名相似假定任意流配套；不绕过等待/年龄/IOD。|
|轨道/钟差/偏差参考|已有独立广播几何/速度/SSR/相对论重建；34 轨道快照及 48 匹配 OSB，最大码偏差应用差约 0.01644 m。|同中心归档不是独立真值，C12 归档有码缺项不能补零；公共钟基准差不等于定位误差。|
|天线与频率|四个北斗身份管理错误已修复；正常解析结果不变；B1C 仍不参与。|不复制缺项天线，不开启未经验证 GLO。|
|对流层/电离层/钟与 N 物理闭合|保存的逐行方程、K·v 预算、固定参考试验已闭合；当前 LEGACY 总 ZTD 语义明确。|代数闭合不是独立物理正确性证明；绝对码偏差/绝对 I/钟/N 可相互分配。|
|湿延迟异常|本次自由解 160 个负 **ZWD**，非负总 ZTD；固定真值后总 ZTD4.1047 m、ZWD1.9403 m，原预报湿约0.1996 m。|不能沿用历史 vivo“总 ZTD−0.721 m”的标签，不裁剪湿分量掩盖失配。|
|初值/先验/抗差|初始均值、I/T 重复约束、当前处罚已有独立实验；本批补齐北斗方程类别交互。|没有证明哪个 GIM 信息预算正确，亦未发现可直接修改的此类公式错误。|
|滤波与提交|Joseph 保持；原生有限性/失败原子性测试通过，701 正常回放原样。|数值可靠不代表估计无偏，不用历史 PHYSICAL 180 次 PSD 事件解释这次 9 m。|
|原始码相动态参考|原始 GPS G03/G31 同频18 s：码−积分伪距率星间变化10.3394 m，ADR对应0.1955 m；北斗也有同类非公共失配；不依赖 SSR/GIM/KF。|不是最终 Up 的独立贡献，也不能唯一划给多路径/硬件/码/ADR；本批不再做泛化 CN0 审计。|
|尺度化状态辨识|既有末期单历元 GNSS-only 条件 Upσ≈353 m，加两类大气行约12.39 m，而历史后验σ≈0.3836 m；高度—大气依赖强。|单历元信息不足不能证明整段动态系统不满秩，更不能给经验调 Q 的依据。|
|Android 原生一致性/产品快照|32 核心新 pin 两端一致；串行 JNI、产品先冻结、参考只解后使用；新版四 ABI 可构建。|未进行新版真机长期解算，本轮无安装。|

上述结果复用已有 `SSR_CODE_REFERENCE_PROVENANCE`、`SSR_FIXED_REFERENCE_CLOSURE`、`SSR_JOINT_STATE_CAUSAL`、`SSR_PHONE_NRT_CROSSCHECK` 报告；没有重新泛查这些方向。

### 静态分析未当成实际错误的项

MSVC `/analyze:only` 覆盖 ppp/rtkcmn/ephemeris/adapter/rtcm3/signal_policy 和两个 C++ SSR 接口。日志和 XML 保存于本批目录。孤立 END 已另用最小输入证实后修复；**不把分析器某条 buff 告警等同于已证明的错误行**。

其余告警按调用路径核查：NFREQ 常量条件；pppos 约69 KB 栈使用；已初始化默认值的 sscanf 返回值；隔离保持1..7的 quarantine计数移位；ephemeris 中返回路径/再次选星历后才使用的 eph；repstr 中 substring 后紧接写终止串。当前输入未复现对应失效，未无依据改写。repstr 的固定1024缓冲区接口仍缺通用容量参数，属于超长外部路径潜在健壮性限制，不是这次9m证据；静态检查不等于完整内存安全证明。

## 7. 回归、构建与确切交付版本

|验证|结果|
|---|---|
|修复后完整 PC 构建及原生回归|579 SSR +40 因果时间线 +15 滤波安全检查，全部通过。|
|Python 回归|35 unittest 通过，见 python_regression.log；发生于解析 guard 前，Python逻辑不受 guard 影响，未冒充重复新跑。|
|解析器专项|5 最小有效/畸形输入 +2 完整产品解析身份校验通过。|
|Android 最终 Gradle|`testDebugUnitTest assembleDebug` 成功；144 项中140通过、4跳过；包含8项新产品迁移/失败恢复/身份/选择器测试。Gradle 对未变 JVM 源可复用已有测试任务。|
|修复后 701 历元正式 SSR 回放|除 processing_ms，所有 solution 字段完全相同；observations.csv、solution.stat、corrections.csv **字节相同**。|
|PC/Android 源指纹|32项归一化 SHA 均匹配新版 ntrip_profile；rtkcmn 新 pin `edb03a943b08ac8a25d14bc229fa300b9c2aed9852c61df6f41361af84835034`。|

新 PC `bin/ppp_ssr_replay.exe` SHA `4b99486ec9ba10d82aa0c40a99fe9f26ed8e5f1f9c44663dfc22580b24583b3b`。

新 APK `E:/android/test/PPP_NTRIP/app/build/outputs/apk/debug/app-debug.apk` SHA **`23985ebc231226fedc891104aa6b93d8f45915a2d065b3dcd5af86a583530ec7`**。**构建完成，未安装到手机。** 旧报告的 APK 哈希不代表此版本。完整交付收据 `validation/comprehensive_audit_20261027/delivery_verification.json`，Android `tools/antex_version_fix_20261026/verification.json` 同步记录。

复用/运行：

```powershell
# 以下均从 E:\GNSS\PPP_NTRIP_PC 运行
.\tools\plot_venv\Scripts\python.exe tools\summarize_ssr_comprehensive_audit.py
# 仅重新汇总保存的证据，不触发重放
.\tools\plot_venv\Scripts\python.exe tools\build.py --test
# 确有新源码时才构建/回归；现已完成
```

首次 `--verify-new-build` 重放已完成并保存，工具拒绝覆盖已有 replay。专项 `check_antex_orphan_record.py before/after` 也拒绝重复覆盖完成的源快照。Android构建用既有 JBR：`gradlew.bat testDebugUnitTest assembleDebug`，不安装。

## 8. 剩余根因与能够采取的动作

**已证实并处理的代码/产品管理错误**是旧 ANTEX 长期复用和孤立 END 生成非法记录；不是“找到了就能把9m压到1m”的承诺。既有现代北斗 SSR、严格星历匹配和弧段安全修复全部保留。

**最有证据支持的剩余机制**是：非公共码/码相参考不一致进入逐星 I、钟/ISB、N、ZTD 与位置联合状态；北斗码与 GIM 先验共同参与时，把当前这段轨迹拉向更大的高程偏差，存在明显交互和历史记忆。当前观测与先验不足以把它唯一分配给某个硬件物理项、某份外部大气绝对偏差或尚未识别的模型缺项。初期 GPS/Galileo 已偏大，不能只责怪北斗。

**本批没有找到新的确定符号、单位、索引或物理公式错误，能解释并修复全部米级偏差。** 不能由“多检查了几个方向”逻辑推出“剩余所有未知已排除”。缺少独立绝对码/大气参考时，继续在同一批彼此耦合的估计状态上强行选唯一根因，会得到不可辨识的结论。

因此没有把剔除北斗、删除 GIM、双钟、API σ 替换、裁剪 ZWD、降低阈值或套用 raPPPid 参数设为默认。正式可交付的就是已验证的两项确定修复；尚无依据实施一个可声称解决9m的额外物理项修复。

## 9. 证据组织与空间

本批入口：`docs/SSR_COMPREHENSIVE_FIX_AND_CAUSAL_AUDIT_20261027.md`；紧凑机器汇总在 `validation/comprehensive_audit_20261027/summary.json`。实际 SSR 图和 CSV 与辅助 NRT/raPPPid 分开存放。原始 ZIP/产品未删除或复制到 F 盘。

此前自动审批拒绝删除34份已压缩的生成日志，本批没有绕过该拒绝；原日志及已验证 gzip 都仍在，不宣称腾出了那部分空间。新实验保留必要源码、命令、回执和轨迹，未扩大原始产品树副本。

后续接手先读本报告及两份 AGENTS 顶部，不再重跑已完成全段实验或重复泛化排查。
