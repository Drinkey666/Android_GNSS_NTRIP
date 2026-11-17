# 当前项目状态

核验日期 2026-11-17，Asia/Shanghai。范围为 NTRIP 分支后的 PC/Android 工作。
本文件是状态入口，AGENTS.md 是长期规则。本轮已完成独立 WHU OSB 缓存正式隔离及三轮诊断归档；此前上下文整理快照保留在handoff_archive。

## 工程与版本
|用途|实际地址|当前版本事实|
|---|---|---|
|PC 正式录流/因果回放|E:/GNSS/PPP_NTRIP_PC|无 .git，分支和 HEAD 不适用|
|Android 正式采集/在线PPP|E:/android/test/PPP_NTRIP|main，在线源码历史基线 1932fda，11/17 WHU OSB 隔离见 [GitHub 归档](https://github.com/Drinkey666/Android_GNSS_NTRIP/tree/main/docs/ntrip-ppp-closure-20261117)|
|聊天默认目录|E:/GNSS/rtklib_only/rtklib_only/rtklib_Project2|旧工程，本任务不接续该目录|
|独立PC候选|validation/b1c_joint_consistency_20261031/state_activity_fix_v2/|已验证实验产物，未自动替换正式PC/Android|
|正式NTRIP诊断|validation/ntrip_formal_en_20261107_v3/|原585s启动规则、84期成功提交审计；未修改估计器|
|11/8后续排查|validation/ntrip_followup_20261108/|两项独立候选及双频诊断均完成；未设为默认|
|11/8相位OSB浮点链|validation/ntrip_phase_osb_20261108/|已接入PC/Android并构建；未固定模糊度、未安装，水平精度未改善|
|11/10独立中心码产品核验|validation/ntrip_independent_code_20261108/|CODE两族及GFZ一族对照完成；仅事后产品查询/已存矩阵分析，正式解算器未变|
|11/10完整PPP产品精度对比|validation/ntrip_full_product_comparison_20261110/|7组完整669期、每组84Q6；同观测配对完成，未形成全面精度修复|

Android 11/16 在线源码提交基线为 1932fda。后续提交 92ff730 仅发布对外问题报告及相关 PC 源码、诊断脚本和派生证据，已核验 GitHub main。PC 独立目录仍无 Git 远端。对外报告 https://github.com/Drinkey666/Android_GNSS_NTRIP/blob/92ff7308c5afe14410b15cf431905d531fc3fa3f/docs/ntrip-ppp-review-20261116/README.md
PC 不能用 Android HEAD、父工程旧提交或文件时间充当自己的 HEAD。

11/16 Android 提交并推送 25 个 app/src 源码、配置和测试文件，包含共享诊断与相位 OSB、地图、定时留档和新启动规则。11/16 提交后已跟踪文件当时无未提交差异。11/17 的 SSR 源码、回归与三轮证据见 GitHub 归档。离线 Gradle 检查成功，运行了四个 ABI 的 CMake 构建任务，JUnit 使用已有结果。
整理前Git状态在 docs/handoff_archive/20261107/audit.json；11/7交付在validation/ntrip_formal_en_20261107_v3/final_verification.json，11/8核验在validation/ntrip_followup_20261108/verification.json。
PC 无Git，无法列举相对HEAD的未提交修改。原先既有源码、工具和实验均予保留。
11/7修改共享诊断覆盖/行元数据并重建；11/8先完成私有候选，随后按用户要求接入正式相位OSB浮点处理链。Raw/SSR/产品、R/Q/P0/GIM/抗差和启动规则未变；相位观测改正路径及共享布局已变更，两端已重编译，未启用模糊度固定。

## 当前任务与停止位置

- 11/17 33 组基线观察、单星座码屏蔽与 M1_v2 完成。10:04 小米 GPS 1C 前 60 期 E/N/U 推力 +1.781/+3.106/−3.859 m，去 GPS 码全段 H/U 2.342/2.977→1.424/1.893 m，末段仍东偏 +1.108 m。五包没有同一星座通解。M1_v2 两档改善 10:04 小米，11:20 小米及 10/31 V1 水平反退，保留独立实验。用户已淘汰 M2 与 M3。 [实验报告](../README.md)
- 11/17 30 组隔离回放及 6 组正式控制完成。11:20 vivo 联合全段 H/U RMS 1.187/2.289 → 1.402/1.842 m，单独 M1 1.187/2.289 → 1.160/1.955 m。10:04 双机共有 Q6 下，联合使 vivo H/U RMS 1.359/1.453 → 1.690/2.125 m、小米 2.343/2.977 → 1.833/2.581 m。10/31 末 60 秒 H/U RMS，V1 1.822/0.460 → 2.254/0.364 m、V2 1.691/0.407 → 1.778/0.093 m。联合精度取舍明显，归档为 NEGATIVE_NOT_FIX。 30 组逐历元 Q 序列均与对应正式基线一致。 [本地报告](../../ntrip-ppp-step4-20261117/README.md) · [GitHub 证据](https://github.com/Drinkey666/Android_GNSS_NTRIP/tree/main/docs/ntrip-ppp-step4-20261117)
- 11/17 正式修复已完成。独立 WHU 模式下，通道 0 身份检查只看轨钟 k=0/1，通道 2 只看码偏差 k=4。通道 0 在已提交缓存只写非偏差分量，纯码帧且该星无轨钟时跳过写入。1059→1060 回归覆盖 V1/V2、冷启动、已提交合法零与缺失、不同身份和不同时标，usable() 继续通过。 正式 PC 复跑四个小米包 V2，2,623 期 × 17 列与第三轮逐历元表逐字节一致。10:01/10:04/10:41/11:20 分别 119/1466/63/587 个 Q6。逐包 corrections.csv、observations.csv、solution.stat 与私有修正逐字节一致，solution.csv 除 processing_ms 外逐字段一致。 [正式验证报告](../../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/REPORT.md)
- 三轮诊断已登记 [E27–E31](PPP_INVESTIGATION_INDEX.md) 和 [证据台账](PPP_INVESTIGATION_LEDGER.json)。第一轮 11:20 共 282 个 Q6。前 20 期 vivo GPS 1C / Galileo 1C 的 U 更新合计 −5.024/−2.280 m。首期 G25 1C 去均值码差 +21.335 m。可验证连续弧上 C19/C10 2I 双机相位变化 RMS 0.013/0.011 m，同样本码相背离 RMS 3.357/3.364 m。 [brain_step1_diagnosis_20261116](../../ntrip-ppp-closure-20261117/validation/brain_step1_diagnosis_20261116/REPORT.md)
- 第二轮 以 530689 s 锚点分解码注入。vivo 全段 U RMS 2.142 m → 1.471 m（锚点后的动态漂移）→ 1.170 m（加首期静态常值 a）→ 1.135 m（加无首期锚点的 E07 1C）→ 1.123 m（恢复整组算术中心化）→ 0.905 m（历史组中位数中心化，降低 G25 等离群值对中心的牵引）。锚点静态和动态可在同一支持集逐行相加。RMS 随滤波历史和比较顺序变化，不能将各级差值视为独立的物理方差。 vivo 前 20 个 Q6 的 U 累计下拉为 G03 1C −4.1955 m、G10 1C −1.0219 m、E27 1C −1.2554 m、G28 1C −0.7555 m。北斗 C19/C36/C10 下拉与 C22/C20 等上推对冲，北斗码首期净 −2.432 m、前 20 期净 −1.373 m。G25 1C 首期 +21.335 m 码差对应 C/N₀ 17.60 dB-Hz 的基础码方差 12 倍档，U 首期 +1.472 m、前 20 期净 +0.799 m。 [brain_step2_closure_20261116](../../ntrip-ppp-closure-20261117/validation/brain_step2_closure_20261116/REPORT.md)
- 第三轮 G03/G10/E27/C19 的有效首码缺建模次频。非组合模型中，单频码误差可被逐星垂直电离层 I_v 与 U、IC(0) 联合分摊，留给质控的第一次验后组偏差最大仅 1.108/0.690/0.608/0.355 倍物理 σ₀，均未达到 4σ₀ 与 6 倍缩放 MAD 的联合门槛。单频性、MAD、CMC 和无相位存在同星或跨机重叠，已检特征不能干净分离 vivo 目标与小米对照。 四个 11/14 小米包的 17,204 条共有 Q6 新准入信号，旧拒因为 WHU_CODE_BIAS_COMPONENT_MISMATCH。45,946 条共同信号的码与相位 OSB 数值一致。历史准入控制把 10:04 高程和 11:20 水平的部分恶化定位到窗口前新观测改变的滤波状态历史。 [brain_step3_final_audit_20261116](../../ntrip-ppp-closure-20261117/validation/brain_step3_final_audit_20261116/REPORT.md)
- 单机探针 STATMOD 7 归为 LOCATING_EVIDENCE。以 vivo / 小米、全段 H/U RMS（m）计，原样分别 1.165/2.142、0.608/0.550，探针分别 1.060/1.886、0.694/0.610。 连续弧码方差乘 (1+N_lock) 归为 NEGATIVE_NOT_FIX，全段 H/U RMS 为 vivo 1.221/2.726 m、小米 0.622/0.844 m，两个设备的全段和末 60 秒 U RMS 均恶化。两项只保留私有探针，生产 core/ppp.c 和运行默认值保持原样。 [brain_step2_closure_20261116](../../ntrip-ppp-closure-20261117/validation/brain_step2_closure_20261116/REPORT.md)
- 11/16 按 Raw 和钟锚独立复算 11/14 两段双机 19770 条配对 GPS 1C、Galileo 1C/5Q 伪距，最大差 3.73×10⁻⁹ m。样本的 TimeOffset 和硬件钟不连续计数均为零。vivo 四条极端码差来自该批 Raw 测量，旧解算最终均拒绝。11:20 人员在旁的新线索没有逐时标记，尚未确认遮挡作用，优先固定同一会话做人员靠近/远离对照，无正式代码改动。见 `validation/ntrip_raw_clock_audit_20261116/REPORT.md`。
- 11/14 已完成两机双向伪距互换。11:20 vivo 高程 RMS 2.142→0.974 m、小米 0.550→1.114 m；10:04 vivo 1.488→2.928 m、小米 2.671→1.643 m。保留各机钟差公共项、相位、多普勒及因果流。11:20 仅交换 GPS/Galileo 可复现主要高程差，单独交换北斗 2I 无法重现。正式程序未改，优先追 GPS/Galileo 原始码的信号与时标。见 `validation/ntrip_code_swap_20261114/REPORT.md`。
- 11/14 已拆解四段共 184 个最终提交的滤波矩阵。11:20 vivo 首期高程与 GPS 公共钟差相关 +0.877、与北斗系统间偏差 +0.592；共同 19 星电离层初值两机最大差 0.016 mm，差异在观测更新后形成。北斗单码的局部高程项可由逐星电离层和浮点模糊度吸收。未定位单一物理根因，正式源码未改。见 `validation/ntrip_state_separation_20261114/REPORT.md`。
- 11/14 五段因果伪距历史诊断及独立降权试验已完成。固定参考下同星同信号码差可短时预测，但实际验前新息同信号内 AUC 0.617–0.691。五段有界历史降权保持原 Q 和首解，米级偏差未解决；11:20 vivo 前 20 个有效解无一命中，首解后约 30 s 才首次降权，H/U RMS 1.165/2.142→1.166/2.160 m。不采用，正式程序未改。见 `validation/ntrip_code_history_20261114/REPORT.md`，后续优先核对首期伪距、码偏差参考及显式电离层与高程可辨识性。
- 11/14 已拆分 11:20 vivo 首 64 个有效解，首期高程从 +6.05 m 更新到 +1.38 m，第 20 个有效解降到 −3.21 m。首期高程码贡献 −4.67 m，前 20 期累计 −8.94 m，主要差异来自码更新。与小米同秒共同码行的 SSR 来源/IOD/码偏差一致，码闭合高程方向分量中位数 vivo −3.12 m、小米 −1.03 m。vivo 5Q 未准入，单独移除小米 5P 仍未复现 vivo 的高程偏差。物理误差来源未唯一分离，正式源码未改。见 `validation/vivo_capture_20261114/error_attribution/REPORT.md`。
- 11/14 已读取 vivo 当日四包，手机仍用旧启动规则。PC 逐历元复现 2629 期状态、34251 观测行、1320 个 Q6，最大坐标差 0.89 µm。vivo 10:04 和 11:20 全 Q6 水平/高程 RMS 分别为 1.281/1.488 m、1.165/2.142 m。相同 GPST 秒双机都出 Q6 时，10:04 vivo 水平 1.294 m、小米 2.204 m，11:20 vivo 1.165 m、小米 0.607 m。见 `validation/vivo_capture_20261114/REPORT.md`。
- 11/14 已完成 11:20 与 10:04 精度差的首期增益归因。两段五个产品文件相同。10:04 的首期真实码更新高程 −4.20 m，首解 H 2.98 m。11:20 的码更新北向 −1.84 m、高程 −1.64 m，首解 H 0.78 m。固定参考首 18 个 Q6 码空间拟合中位 ENU 从 +1.60/+1.09/−2.80 m 降为 +0.49/−0.27/−0.65 m。关闭相位 OSB 仍复现两段米级差异。观测、实时改正及几何的物理责任尚未唯一分离，正式程序未改。见 `validation/android_capture_20261114/accuracy_gap/REPORT.md`。
- 11/14 已读取小米当日四份采集包并按 `applied_seq` 完整复现，全部为旧启动规则。2623 期 Q 状态、34858 观测行一致，1141 个 Q6 最大坐标差 1.15 µm。11:20 真机首解 268.96 s，H/U RMS 0.608/0.550 m；同包新启动规则 PC 回放 14.80 s 首解、488 Q6（原 293），共同末 60 Q6 的 H/U RMS 0.570/0.296 → 0.629/0.615 m。10:04 约 23:51 后三流无新数据，约 25:09 后无 Q6。定位到轨钟流附带码偏差覆盖独立 WHU OSB 的缓存问题，私有来源修正四段 Q6 55/852/45/488 → 119/1466/63/587，部分共有窗口误差变差。11/17 已同步并复现私有结果，见上文。见 `validation/android_capture_20261114/REPORT.md`。
- 11/14 安卓首解提速已构建。匹配的首份完整 WHU 码偏差可通过启动检查，采集包标记 `WHU_OSB_FIRST_COMPLETE_V2`，PC 按包选择对应规则。偏差流重连后须重新收完整偏差，同估计的重复帧不会重置推进看门狗；未来、倒退、来源、IOD、轨钟时效和广播星历匹配继续检查。10/31 同一到达前缀 669 期，新规则 5 秒首 Q6（5Q0/1Q5/663Q6），旧规则 585 秒（585Q0/84Q6）；旧轨迹除耗时外逐字段复现。末 60 秒 H/U RMS 新 1.691/0.407 m、旧 1.822/0.460 m。首份偏差绝对时效与新 APK 真机首解仍待验证。证据 `validation/whu_first_complete_20261114/verification.json`。
- 11/14 Android 实时留档已增加 1～30 分钟设定、倒计时和自动收尾，并在 `capture.json` 保存参考、高程类型、计划和实际时长、停止原因、首末 Q6、三流连接及产品问题摘要。当前 PC 导入器已通过新版 Android 测试包兼容核验。下次新包优先检查同机同点长时段北偏，见 [Android 当前状态](E:/android/test/PPP_NTRIP/docs/CURRENT_STATE.md)。
- 用户进一步授权实际解算比较，已完成，报告docs/NTRIP_FULL_PRODUCT_COMPARISON_20261110.md：7组669期、均585Q0/84Q6，保留原WHU准入/启动、非组合显式电离层及R/Q/P0策略，每族建立相同输入观测的WHU对照。正式源码/EXE/Android产物未改，不自动安装APK。
- 同一末60秒H/U RMS：正式WHU 1.822400/0.460213m；CODE OPSFIN 1.616050/3.132573m，其配对WHU 1.882480/3.605457m；CODE MGXFIN 2.320072/6.317297m，其配对WHU 1.813996/2.334104m；GFZ GBM快速产品2.497978/1.181575m，其配对WHU 2.786243/3.659041m。覆盖集合不同，不能把相对正式的全部变化归轨钟；没有方案全面优于正式，不迁移/设默认。
- 前阶段docs/NTRIP_INDEPENDENT_CODE_REFERENCE_20261110.md是产品查询/局部矩阵结果，不能代替本轮完整轨迹，也不能再说独立产品尚未实际解算。各族双方观测/支持掩码相同，六组SSR释放日志与正式控制相同；配套产品仍为事后资料，不代表实时可用。
- CODE G/E去公共项码模型差RMS0.270m；CODE MGX北斗5P差RMS7.836m，但参考为1P/5P，不能直接指认为WHU错误。GFZ旧2I/6I同参考族补齐504条北斗2I，对应非公共差RMS1.493m，该组首期局部ΔE−0.158/ΔN+0.120/ΔU−1.731m；仍未解释全部水平偏差。
- 北斗码OSB、卫星钟差与显式电离层先验的参考衔接仍值得优先核对，尚无唯一根因。此前并集2436/2688和252条缺口为产品查询阶段口径；本轮严格掩码按所有实际输入重算，输入行数不冒称最终提交方程数。未混中心补齐、补零缺失或新增自由偏差状态。
- 用户已授权按正式NTRIP误差形成过程排查并修改，当前只专注实时流路径；CLK3.04是文件旁支，不作为本主线前置。
- 用户最新硬约束：以后不考虑双频无电离层组合（IF/IFLC），不再提出、实现或运行，包括旁路诊断/对照。后续在非组合模型内显式处理电离层；此前相关组合结果只作历史，不作为继续路线。
- 正式84期审计已完成，报告 docs/NTRIP_FORMAL_EN_AUDIT_20261107.md。北偏在首次码更新形成；本轮补齐诊断窗口和周跳/弧状态，未定位到可安全修复的米级公式错误，水平误差尚未解决。
- 此前独立预测新息Huber候选只替换B瞬时处罚，末60s水平RMS1.822400→1.824255m，未改善，不采用/不迁移。见docs/NTRIP_INNOVATION_HUBER_TRIAL_20261107.md；持续码误差与电离层/RCB/模糊度可辨识性仍未获得新的解决结论，不重做该候选。
- 11/8后续排查完成，报告docs/NTRIP_FOLLOWUP_MODEL_AUDIT_20261108.md：等待期原始历史候选H RMS1.792m但U RMS0.788m变差；同星共享R候选H1.819/U0.458m仅毫米级变化。均不设默认，不迁移Android，正式H仍1.822m。
- 历史连续双频检验得到566个连续窗、213个有足够伙伴且全部为GAL，关键BDS码缺所需连续双频相位；该路线已按用户要求停止，不能再作为下一步。上次ADB检查未授权，未读取新包，本次未重查设备。
- 用户已明确不考虑模糊度固定，本次仅接相位OSB处理链。docs/NTRIP_UNCOMBINED_PARTIAL_AR_PROPOSAL_20261108.md已标记为停止的历史提案，不作为后续路线。
- 相位OSB非组合浮点链已实现、PC验证并同步Android构建，报告docs/NTRIP_PHASE_OSB_FLOAT_CHAIN_20261108.md。现行解码、独立缓存/连续性、参考断点及corr_meas改正已接通；2186条最终相位提交行中1385条G/E实际应用，801条C保持原浮点参考。原包北斗1270的29颗星重复mode 0，2I歧义不覆盖为零；5P无确切支持不替代。开关均585Q0/84Q6，末60s水平RMS仍1.822400m，未修复水平偏差。
- 业务最终目标是手机实时非组合PPP，收敛更快且精度稳定，优先常规抗差，信号级eta学习未获当前实施任务。
- 不以降低某段末点误差为参数选择依据，继续保留因果回放和完整证据。

## 模块、构建与检查入口
- core/ 共享PPP/滤波/观测生成/RTCM/IONEX/天线/预检。
- src/gnss_replay.c 为手机TXT/RINEX入口，src/ntrip_ssr.cpp/.h 为SSR处理，src/pc_ssr_replay.cpp/.h 为因果回放。
- tools/build.py + build_pc.cmd 为已使用的VS2022 x64构建，CMakeLists.txt为另一个入口。
- 构建及原生回归命令为 .\build_pc.cmd --test。
- Python回归命令为 .\tools\plot_venv\Scripts\python.exe -X utf8 tools/run_ntrip_python_regressions.py，排除用户禁止的4项历史消电离层诊断，不将其计为通过。
- 相位链阶段再次完整重建PC，905项原生及观察器检查通过，允许执行的Python49项通过/0跳过；replay_txt.cmd完成新关闭/开启控制。Android共享布局变更后四ABI构建成功，未重跑JUnit、未安装。11/10独立产品阶段新增4项定向测试通过，允许的Python全套53项通过/0跳过；未重跑905项原生全套或Android构建。
- build.py --test 会执行SSR、时序、滤波安全、GIM几何、偏差参考测试；whu_policy_capture_test另需真实已存夹具，不能从其EXE存在推断它已执行。
- Android构建/测试方法见 E:/android/test/PPP_NTRIP/docs/CURRENT_STATE.md。

## 正式路径已经实现并有证据的工作
1. WHU三路链为 SSRC00WHU0(CoM) + OSBC00WHU1 + BCEP00BKG0，配置见 config/caster_whu.json。
2. WHU独立OSB来源/连续性规则、标准BDS SSR的BDT→GPST、现代BDS DF470/471与IOD/广播匹配已实现。
3. Android串行JNI与PC的处理序列回放、Raw停止排空、到达时标、clock anchors、applied_seq、软件/实际产品快照已经留档。
4. CODE IONEX几何与数值约定、卫星身份/ANTEX读取保护、缺天线信号不建无用模糊度已修复。
5. FIXED_CLOCK_2023观测生成已移植到NTRIP两端。真实钟段固定首个有效FullBias/Bias，按真实信号波长形成P/L/D。
6. 正式内核沿用 B_VERIFIED、非组合、Joseph及有限性/失败提交保护。
7. Android的testClasses兼容别名和Maven镜像修复已存在，实时流入口仍保留。
8. WHU相位OSB已进入非组合浮点观测链，有效零/缺失/冲突分别处理，改正启停及不连续只重建受影响弧；未实现或启用模糊度固定。

相关报告按任务选择，不全量读取
- 协议/数值/大气修复 docs/SSR_BDS_FIX_AND_REPLAY_REPORT_20261025.md、docs/SSR_COMPREHENSIVE_FIX_AND_CAUSAL_AUDIT_20261027.md、docs/CODE_IONEX_CONVENTION_FIX_REPORT_20261027.md。
- 观测生成 docs/ANDROID_OBSERVATION_GENERATION_NTRIP_REPORT.md。
- 真机/PC一致性 docs/ANDROID_CAPTURE_EFFECT_20261031.md。
- 如果某个报告名需要查找，以 docs/PPP_INVESTIGATION_INDEX.md 和实际文件为准。

## 实际部署边界
- 正式 PC `bin/ppp_ssr_replay.exe` 已于 11/17 重建，SHA256 `ade219b70ceedfab089e74d95ae1af92ae80cb981887d905c90f5942b51def7a`。11/14 历史构建的 SHA256 `85fc4d8c2bf09f0c10f5b0a2df5d82b24f6484e423af660cfea7d372e9a7d1c9`。11/8 版 `f0099bda` 保存在 `validation/whu_first_complete_20261114/before/`。11/14 当时通过 925 项原生断言和 59 项允许的 Python 用例，旧规则 669 期的解逐字段复现（耗时除外）。
- 安卓新构建使用 `WHU_OSB_FIRST_COMPLETE_V2`。PC 保留 `WHU_OSB_CONTINUITY_V1` 及原录流配置，旧包按原有两份相隔 300 秒的规则回放。新 APK 尚未在真机安装和验证。
- 原正式观测准入仍排除BDS 1P。独立V2候选才支持B1I+B1C独立槽/RCB/模糊度。
- V2候选修复x!=0遗漏合法零状态，规范码参考变换首期高差0.976089m降为0，989项原生检查记录通过。
- V2实际669期与旧B1C联合候选输出相同，未消除米级东偏。
- V2的无等待策略仍保留到达、年龄、IOD和看门狗保护。首份OSB绝对有效性尚未独立认证，不能凭坐标精度认定时效已验收。
- 11/14 通过 ADB 读取的小米已装 APK 指纹 `04071a6c…` 与当天四包一致，仍使用原 300 秒连续性检查。新版 APK 本轮未安装。

## 当前精度证据及参考
|数据|参考和证据边界|结果|
|---|---|---|
|10/31 11:30小米正式手机/NTRIP|同下行小米参考；585s首次PPP，84个Q6|末60s E RMS1.006m、N RMS1.519m、H RMS1.822m、U RMS0.460m；末点H1.721m、U+0.270m|
|同包CODE OPSFIN / MGXFIN / GFZ GBM完整PPP|同参考、同启动；每族双方使用共同支持观测，事后诊断|末60s H/U RMS分别1.616/3.133、2.320/6.317、2.498/1.182m；各自配对WHU为1.882/3.605、1.814/2.334、2.786/3.659m，未采用|
|10/31 11:30小米669期|［具体坐标留存本地］,［具体坐标留存本地］,椭球高483.980m|原提前SSR末60s东均值+1.477m，H RMS1.691m，U RMS0.407m|
|同Raw的NRT轨钟+RTS BIA|同参考、同大气和天线|末60s东均值+1.714m，H RMS1.798m，U RMS1.333m|
|同期11:30 vivo|［具体坐标留存本地］,［具体坐标留存本地］,椭球高483.960m|原B1C关闭SSR末60s东均值+0.595m，H RMS1.557m，U RMS2.818m|
|10:13一小时小米文件数据|另一采集点，最新参考为［具体坐标留存本地］,［具体坐标留存本地］,椭球高483.000m|连续末H0.716m、U+0.471m；旧486.963m参考导致的−3.492m不作现行误差|

10/31原正式手机链585s开始PPP、84个Q6，提前SSR是独立诊断，不能混同。
用户坐标作为评估参考保留，当前缺独立测量框架/参考误差认证。
10/25旧701期和约9m高差属于旧数据/观测版本，引用必须标明，不能直接套到10/31。

## 已定位、未解决
- 确定待修旁支是 core/rinex.c::readrnxclk() 的CLK3.04列偏移，当前off=0。
  原CODE样本读1.802421113s，正确0.000195441613s；候选及格式对照25+25查询已保存。
  见 validation/ssr_matched_model_20261027/CODE_reference/clock_304_candidate_verification.json 和 PENDING_clock_304_candidate.patch。
  实时SSR不走文件CLK读取，不能据此宣布东偏根因已找到。
- 文件路径存在未认证的钟差/APC/OSB参考及部分缺实际频率PCO/PCV的旧槽回退。
  新核对前31输入期，真实成功提交135条缺OSB提示码、240条缺PCO提示码相。
  见 validation/solution_priority_20261107/file_evidence.json。
- 小米启动共同伪距存在东向空间分量，之后被联合状态与历史延续。
- 本轮CODE完整比较确认core/ppp_product_check.c::clk_apc_model()按空格分词会误读GPSEST V5.5版本号为天线模型。私人预检已改固定列21～60，正式文件预检待修；实时SSR不走该入口。无.atx扩展名别名导致的本轮私人接线失败已纠正，不是原采集天线错误。
  码/电离层/RCB、设备差异及WHU共同产品误差尚无法唯一归因。
- 独立CODE/GFZ对照发现北斗码模型参考差异更大；同参考GFZ 2I仍有1.493m非公共差，尚未确认是WHU码偏差绝对基准、独立产品约定还是与显式GIM先验衔接。CODE MGX 5P参考不同，7.836m差不能直接当改正。252条正式码行仍无独立确切支持；独立产品对照不是完整在线产品替换验证。
- 正式585s启动窗口首次北向先验+0.317m，真实码更新贡献−1.928m，后验−1.637m；原始码空间拟合84期中位数E+1.046m/N−1.745m。末期模型内E/N标准差约0.209/0.206m，与给定参考的米级偏差不匹配。
- 部分正式码新息时间相关性高，但DOPPSM=0.90本身会产生相关；不能据此直接拟合默认相关时间或声称已定位纯码误差。首期最大条件码新息约1.238，普通单期粗差检测不足以识别该方向偏差。
- 已有同星码差和规范参考变换检查通过，无新的确定H/符号/索引错误。
- 观测限制仍有100ms发送时标冲突、GAL7Q ADR/PRR不一致、Native零哨兵及异步表示。
- 没有同期测量型双频接收机数据，用户已答复没有，不列为待用户提供。
- 当前缺少未经方法选择的新时段精度验证。放置/参考条件按用户判断固定，不自动开展转向或换位试验。

## 已完成的排除与负结果
- DOP不支持“东向几何特别差”作为本段主要解释。G25末段去一行重求K的东向局部影响约−0.351mm。
- 首期位置先验东向扰动1m传到后验仅约0.001333m，不能归咎SPP位置直接锁死。
- 共享观测的产品差扣公共项后首期东向影响约5cm，不能解释已有全部米级东偏。
- 两套WHU产品均保留东向分量。11/10已完成DOY304的CODE/GFZ部分确切支持对照，差异和覆盖缺口已保存；不能再写成完全未取得独立产品，也不能称全部绝对准确性已认证。
- 随后完成三族完整PPP配对：同输入控制下OPS/GFZ的H改善约0.266/0.288m，MGX的H恶化0.506m；没有全面优于正式H/U1.822/0.460m的方案。不重做同段比较，不仅凭OPS水平1.616m或GFZ东向0.138m宣称修复。
- B1C联合及合法零状态修复有正确性价值，但实际回放没有消除东偏。
- 预测新息Huber候选未改善正式水平偏差（1.822400→1.824255m）。4条试算软降权均随后被编辑撤销，4874条最终GNSS提交行无软降权；不降低阈值重做，不设为默认。
- 11/8等待期历史候选H RMS约少3cm但U明显变差；恢复同星共享轨钟/模型协方差、保留R对角的候选仅约3.5mm水平变化，均未解决偏差，不重复。
- 正式窗口相同双码集合的无电离层码空间拟合仍有N中位数−1.784m，不支持一阶GIM独自解释全部北偏；仅作噪声放大的诊断，不切换正式非组合模型。
- 本包66891行TimeOffset均0；有效G/E/C的Satellite ISB在同历元星座内全星最大差0，Full ISB分组内为常量。没有据此额外叠加API卫星偏差或改变观测时刻。
- 正式84期4874条GNSS行来源、轨钟IOD/9～17s年龄、码偏差有效及实际频率天线支持检查通过；2186条相位中2148条活动、38条重建（含初始化），不支持普遍反复重置解释。物理产品绝对准确性及OSB绝对有效期仍未独立认证。
- 放宽一次P、前30s保持位置不确定度、推迟30s首次PPP，均未稳定消除东偏。
  小米SSR最好仅减约4cm，文件/vivo延迟反而恶化；这些不设默认。
- 同星座/频段方向一致仍可能共同偏。普通抗差不能仅靠组间同向判正确。
- 细节见 E16/E17/E18 报告及目录，禁止再次全程重跑同组实验来“重新确认”。

## 继续业务时的最小任务与验收
1. 复用已有正式84期矩阵/提交行及11/8新证据，不重跑已完成的P0/R、删星、平滑、启动、预测新息Huber、等待期历史或同星共享R候选。
2. 后续仅在非组合观测方程内检查状态耦合、残差、时间连续性和产品参考；不再沿用双频消电离层组合诊断路线。新增低维码误差方法前先证明覆盖/可辨识性，不用参考坐标给在线解加补偿。
3. 相位OSB浮点接入任务已完成；不推进模糊度固定，不再次试验只加常量相位OSB能否消除该包偏差。复用1385条真实应用、801条回退及北斗信号冲突证据。
4. 独立CODE/GFZ产品查询及其后用户授权的完整PPP配对都已完成，复用E25/E26和CSV，不重新下载/运行同一对照。下一步仍需实际码OSB—钟差—显式电离层参考兼容证据再改正式方程，不能只凭局部估算或单方向改善。事后产品不作为实时来源，不将支持并集拼成混中心链。
5. 会话生命周期仅在新App日志证明无必要重建时处理；CLK3.04仍是文件旁支已知待修问题，当前不转回文件模式。
所有方案按E/N/U全曲线、同窗RMS/偏差、持续收敛、Q6/失败统计验收。
已完成三项未采用候选、相位OSB浮点链接入、独立中心码产品核验及完整PPP产品精度配对。新的持续码误差模型未实现，正式水平偏差尚未修复。本轮 Android 运行验证使用 x86_64 模拟器。实机 USB 调试仍未授权，未安装 APK 或开始新采集。

## 构建和测试证据的当前核验

- 11/17 PC 963 项计数原生断言、滤波诊断窗口与 V1 实录连续性夹具均通过。Python 59 通过，4 项历史 IF 诊断按约束未运行。Android x86_64 模拟器原生 617 项通过，构建了 arm64-v8a 和 x86_64 独立测试；App 四 ABI 重建。JVM 165 通过、3 项外网集成冒烟跳过、0 失败。 两端共享核验 33 项均匹配。[正式验证报告](../../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/REPORT.md)
- 11/7对交接275项文件的“仅5项变化”为当时结论。现阶段增加相位链正式修改，不能再套旧快照声称仅改诊断；当前9个PC EXE与validation/build.json匹配，原EXE/源备份及旧delivery_manifest保留历史含义。
- Android ntrip_profile.sha256的33项与实际及PC同名文件全部匹配；postpos.c在PC也存在，已纠正旧32项/Android专属的文字。
- PC/Android ntrip_ssr.cpp归一化内容一致。
- 本阶段build_pc.cmd --test完整重建，905项原生及观察器检查通过；允许执行的Python49项通过/0跳过，4项历史消电离层诊断按用户约束未执行。此前768/22/53及候选989等计数仍按原阶段解释，不能冒充现阶段执行数。
- 追加预测新息Huber候选12项原生定向检查通过，控制/候选各一次新669期；正式源码、EXE及Android没有因该负结果再改变。
- 11/14定时留档版本的Android JUnit为168项、0失败/错误、6跳过。此前相位链阶段的162项为历史记录。
- Android相位链assembleDebug --offline成功，四ABI完成共享布局重编译；本地Debug APK SHA256为3a01e213f8ef8aed2a526a815136193a7b55551907cd630e186ea92c07440ae6。未重跑JUnit、未安装、未核验真机软件。
- 11/7重建正式669期除耗时精确不变及诊断纳米差为历史证据。相位阶段关闭控制精确复现旧正式，开启后观测/SSR应用文件仍逐字节一致；新观察器与正式开启坐标精确相同，最终1385条改正行由成功提交行核实。该相位观察器未输出完整K/R，11/10敏感性明确复用11/7相位关闭基线矩阵，不冒称开启矩阵。
- 11/8前半阶段“52项源码/EXE不变”是旧候选边界；相位链现阶段的源码/产物、Raw/产品和两端33项pin由validation/ntrip_phase_osb_20261108/verification.json核验。旧followup和11/7证据均保留，不改旧清单伪装当前。
- 11/10独立产品阶段正式46项快照未变、两端33项pin及Android原9项已跟踪修改不变；新工具/测试及两端交接更新见validation/ntrip_independent_code_20261108/verification.json和delivery_manifest.json。4项新定向及53项允许的Python回归通过，0跳过；首次新测试夹具错误已修正，失败日志保留。未重跑原生全套、Android构建/JUnit，未安装。

## 按任务读取证据
- 最新实际完整PPP精度对比 docs/NTRIP_FULL_PRODUCT_COMPARISON_20261110.md。52项正式源码/EXE及原输入、两端33pin和Android原9项修改不变；新6定向及59允许Python通过、0跳过，禁止4项未执行不算通过。有效私人构建build_v2、控制runs/baseline_control、配对runs_v3在validation/ntrip_full_product_comparison_20261110/；失败目录保留，见verification.json/delivery_manifest.json。未重跑正式原生全套或Android构建/JUnit，未安装。
- 前阶段独立中心产品查询 docs/NTRIP_INDEPENDENT_CODE_REFERENCE_20261110.md。三族均为采集后发布，仅事后诊断；其后完整解算以本节上条新报告为准，不是在线候选或精度修复。
- 最新已完成相位OSB浮点链 docs/NTRIP_PHASE_OSB_FLOAT_CHAIN_20261108.md。AR提案已按用户要求停止，不作为当前任务。
- 当前正式NTRIP排查 docs/NTRIP_FORMAL_EN_AUDIT_20261107.md；旧文件/独立产品方案 docs/PPP_SOLUTION_PRIORITY_20261107.md按其原范围解释。
- 最新后续模型排查 docs/NTRIP_FOLLOWUP_MODEL_AUDIT_20261108.md，包含等待期历史、同星共享R、连续双频与API字段证据。
- 追加普通抗差负结果 docs/NTRIP_INNOVATION_HUBER_TRIAL_20261107.md，候选在validation/ntrip_innovation_huber_20261107_v2/。
- 共享行/状态固定诊断 docs/WHU_MATCHED_PRODUCT_EAST_BIAS_20261031.md。
- 启动负结果 docs/WHU_STARTUP_CONFIDENCE_TRIAL_20261031.md。
- B1C与合法零值候选 docs/B1C_JOINT_STATE_CONSISTENCY_FIX_20261031.md。
- 文件/SSR对照 docs/WHU_FTPGET_FILE_VS_SSR_20261031.md。
- 构建启动问题用Android对应Gradle报告，勿从旧初始README推断当前阶段。
- 旧规则全文保存在 docs/handoff_archive/20261107/pc_AGENTS.original.md 与 android_AGENTS.original.md。
- 当前文件合并仍有效规则，分叉前的PPP_only/FTPGet历史交接不作为新会话启动入口。
