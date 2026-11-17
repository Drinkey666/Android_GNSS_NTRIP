后续方法约束：用户于2026-11-08明确禁止再考虑双频无电离层组合（IF/IFLC），包括旁路诊断/对照；本索引中相关内容仅作历史证据，不代表继续建议。后续坚持非组合模型、显式处理电离层。

## E34 · SPP 首期东偏、逐星 GPS 1C 与 M1_v3（2026-11-17）

24 组 M1_v3 完成。四包首期正东偏已存在于 SPP 初值，既有证据无法拆分 SPP 星座责任。10:04 小米 GPS 1C 的前五星 G10/G25/G28/G13/G32，含两颗持续双频。C 全段 H/U 2.342/2.977→1.763/2.424 m，10:04 vivo 两项反退。A、B、C 保持独立实验。 [实验报告](../README.md)

## E33 · 东偏、GPS 1C 星座消融与 M1_v2（2026-11-17）

33 组基线观察、单星座码屏蔽与 M1_v2 完成。10:04 小米 GPS 1C 前 60 期 E/N/U 推力 +1.781/+3.106/−3.859 m，去 GPS 码全段 H/U 2.342/2.977→1.424/1.893 m，末段仍东偏 +1.108 m。五包没有同一星座通解。M1_v2 两档改善 10:04 小米，11:20 小米及 10/31 V1 水平反退，保留独立实验。用户已淘汰 M2 与 M3。 [实验报告](../../ntrip-ppp-step5-20261117/README.md)

## E32 · GIM 基准残差、可观测性与即时 CMC（2026-11-17，NEGATIVE_NOT_FIX）

30 组隔离回放及 6 组正式控制完成。11:20 vivo 联合全段 H/U RMS 1.187/2.289 → 1.402/1.842 m，单独 M1 1.187/2.289 → 1.160/1.955 m。10:04 双机共有 Q6 下，联合使 vivo H/U RMS 1.359/1.453 → 1.690/2.125 m、小米 2.343/2.977 → 1.833/2.581 m。10/31 末 60 秒 H/U RMS，V1 1.822/0.460 → 2.254/0.364 m、V2 1.691/0.407 → 1.778/0.093 m。联合精度取舍明显，归档为 NEGATIVE_NOT_FIX。 [本轮验证报告](../../ntrip-ppp-step4-20261117/README.md)

## E31 · 独立 WHU OSB 正式来源隔离（2026-11-17，VALIDATED_FORMAL_FIX）

独立 WHU 模式下，通道 0 身份检查只看轨钟 k=0/1，通道 2 只看码偏差 k=4。通道 0 在已提交缓存只写非偏差分量，纯码帧且该星无轨钟时跳过写入。1059→1060 回归覆盖 V1/V2、冷启动、已提交合法零与缺失、不同身份和不同时标，usable() 继续通过。

正式 PC 复跑四个小米包 V2，2,623 期 × 17 列与第三轮逐历元表逐字节一致。10:01/10:04/10:41/11:20 分别 119/1466/63/587 个 Q6。逐包 corrections.csv、observations.csv、solution.stat 与私有修正逐字节一致，solution.csv 除 processing_ms 外逐字段一致。

PC 963 项计数原生断言、滤波诊断窗口与 V1 实录连续性夹具均通过。Python 59 通过，4 项历史 IF 诊断按约束未运行。Android x86_64 模拟器原生 617 项通过，构建了 arm64-v8a 和 x86_64 独立测试；App 四 ABI 重建。JVM 165 通过、3 项外网集成冒烟跳过、0 失败。 Android 已在本地正式源代码同步，arm64 原生测试已编译，尚无真机运行及安装。[正式验证报告](../../ntrip-ppp-closure-20261117/validation/whu_osb_formal_fix_20261117/REPORT.md)

## E30 · 单机可观测特征及 WHU 准入审计（2026-11-16 至 11-17，LOCATING_EVIDENCE）

G03/G10/E27/C19 的有效首码缺建模次频。非组合模型中，单频码误差可被逐星垂直电离层 I_v 与 U、IC(0) 联合分摊，留给质控的第一次验后组偏差最大仅 1.108/0.690/0.608/0.355 倍物理 σ₀，均未达到 4σ₀ 与 6 倍缩放 MAD 的联合门槛。单频性、MAD、CMC 和无相位存在同星或跨机重叠，已检特征不能干净分离 vivo 目标与小米对照。 四个 11/14 小米包的 17,204 条共有 Q6 新准入信号，旧拒因为 WHU_CODE_BIAS_COMPONENT_MISMATCH。45,946 条共同信号的码与相位 OSB 数值一致。历史准入控制把 10:04 高程和 11:20 水平的部分恶化定位到窗口前新观测改变的滤波状态历史。 [brain_step3_final_audit_20261116](../../ntrip-ppp-closure-20261117/validation/brain_step3_final_audit_20261116/REPORT.md)

## E29 · 连续相位弧码降权（2026-11-16，NEGATIVE_NOT_FIX）

连续弧码方差乘 (1+N_lock) 归为 NEGATIVE_NOT_FIX，全段 H/U RMS 为 vivo 1.221/2.726 m、小米 0.622/0.844 m，两个设备的全段和末 60 秒 U RMS 均恶化。两项只保留私有探针，生产 core/ppp.c 和运行默认值保持原样。 [brain_step2_closure_20261116](../../ntrip-ppp-closure-20261117/validation/brain_step2_closure_20261116/REPORT.md)

## E28 · 逐星滤波增量、时间互换闭合及 STATMOD 7（2026-11-16，LOCATING_EVIDENCE）

以 530689 s 锚点分解码注入。vivo 全段 U RMS 2.142 m → 1.471 m（锚点后的动态漂移）→ 1.170 m（加首期静态常值 a）→ 1.135 m（加无首期锚点的 E07 1C）→ 1.123 m（恢复整组算术中心化）→ 0.905 m（历史组中位数中心化，降低 G25 等离群值对中心的牵引）。锚点静态和动态可在同一支持集逐行相加。RMS 随滤波历史和比较顺序变化，不能将各级差值视为独立的物理方差。

vivo 前 20 个 Q6 的 U 累计下拉为 G03 1C −4.1955 m、G10 1C −1.0219 m、E27 1C −1.2554 m、G28 1C −0.7555 m。北斗 C19/C36/C10 下拉与 C22/C20 等上推对冲，北斗码首期净 −2.432 m、前 20 期净 −1.373 m。G25 1C 首期 +21.335 m 码差对应 C/N₀ 17.60 dB-Hz 的基础码方差 12 倍档，U 首期 +1.472 m、前 20 期净 +0.799 m。 STATMOD 7 归为 LOCATING_EVIDENCE。以 vivo / 小米、全段 H/U RMS（m）计，原样分别 1.165/2.142、0.608/0.550，探针分别 1.060/1.886、0.694/0.610。 [brain_step2_closure_20261116](../../ntrip-ppp-closure-20261117/validation/brain_step2_closure_20261116/REPORT.md)

## E27 · 双机码相分解、K·v 六状态及首批互换（2026-11-16，LOCATING_EVIDENCE）

11:20 共 282 个 Q6。前 20 期 vivo GPS 1C / Galileo 1C 的 U 更新合计 −5.024/−2.280 m。首期 G25 1C 去均值码差 +21.335 m。可验证连续弧上 C19/C10 2I 双机相位变化 RMS 0.013/0.011 m，同样本码相背离 RMS 3.357/3.364 m。 [brain_step1_diagnosis_20261116](../../ntrip-ppp-closure-20261117/validation/brain_step1_diagnosis_20261116/REPORT.md)

## E26 · 独立配套产品完整PPP精度对比（2026-11-10，用户授权实算完成）

见[NTRIP_FULL_PRODUCT_COMPARISON_20261110.md](NTRIP_FULL_PRODUCT_COMPARISON_20261110.md)。7组669期、均585Q0/84Q6；三族各有同观测WHU控制，同启动/非组合/显式电离层/原参数策略。末60s H/U：正式WHU1.822/0.460m；CODE OPS1.616/3.133m（配对WHU1.882/3.605）；CODE MGX2.320/6.317m（1.814/2.334）；GFZ GBM快速产品2.498/1.182m（2.786/3.659）。未全面改善，不采用；不能仅以OPS水平或GFZ东向改善宣称修复。配对输入/掩码一致，六组SSR释放与正式控制一致；未混中心/补零。私人CLK304、GFZ标签及预检CLK模型固定列兼容，正式源码不变；52项正式快照、两端33pin、Android原9项修改不变，6定向/59允许Python通过，未构建或安装Android。证据validation/ntrip_full_product_comparison_20261110/，复用结果，不重做同段三族比较。

## E25 · 独立CODE/GFZ码产品参考核验（2026-11-10，已完成诊断、未修复精度）

见[NTRIP_INDEPENDENT_CODE_REFERENCE_20261110.md](NTRIP_INDEPENDENT_CODE_REFERENCE_20261110.md)。CODE OPSFIN/MGXFIN及GFZ GBM同日配套三族，均为事后产品，未注入在线链。三组各2692码请求/84期/0滤波调用，最终码支持1596/1932/1680条；证据并集2436/2688，不是混中心产品链。G/E差RMS0.270m；CODE MGX 5P差7.836m但参考不同，GFZ同2I/6I参考的2I差1.493m，后者首期该组局部ΔE−0.158/ΔN+0.120/ΔU−1.731m，未消除水平偏差。下一步优先北斗码OSB—钟差—显式电离层参考衔接，不重做常量相位OSB/旧调参。新增4定向及53允许Python回归通过，正式46项快照、两端33pin及Android原9项修改不变；没有新PPP回放、Android构建或安装。相位观察器仅有成功提交行，完整K/R复用11/7关闭基线，交接已纠正表述。

## E24 · 相位OSB非组合浮点链接入（2026-11-08，已完成）

见[NTRIP_PHASE_OSB_FLOAT_CHAIN_20261108.md](NTRIP_PHASE_OSB_FLOAT_CHAIN_20261108.md)。按用户要求仅接相位链，不做模糊度固定。现代标准/IGS相位解码、独立缓存/连续性、真实零/缺失/重复信号冲突、弧参考断点与corr_meas改正已接通；PC905原生及观察器、允许的Python49项通过，4项历史消电离层诊断未执行。新关闭控制精确复现旧669期，开启后1385条G/E相位最终提交应用、801条C回退；北斗mode 0冲突不覆盖为零，不补5P。水平RMS仍1.822400m，无精度修复结论。两端33项pin及四ABI构建通过，未安装APK。证据validation/ntrip_phase_osb_20261108/。

## E23 · 审阅后的提案（2026-11-08，用户已停止固定路线）

见[NTRIP_UNCOMBINED_PARTIAL_AR_PROPOSAL_20261108.md](NTRIP_UNCOMBINED_PARTIAL_AR_PROPOSAL_20261108.md)。当时只用码OSB、ppp_ar为空，提出过非组合部分固定可行性；用户随后明确不考虑固定，仅实施相位OSB浮点链（E24）。该提案保留历史，不恢复为当前路线。

## E22 · NTRIP后续模型与连续双频排查（2026-11-08）

见 [NTRIP_FOLLOWUP_MODEL_AUDIT_20261108.md](NTRIP_FOLLOWUP_MODEL_AUDIT_20261108.md)。新问题是SSR等待期原始历史未积累、同星共享产品误差仍作为独立R；两项独立候选各控制/新669期。等待期历史H RMS1.822400→1.792199m但U0.460213→0.788378m，不采用；同星共享R保留对角、无新参数，H1.818873/U0.457501m仅毫米级变化，不设默认/不移植。相同双码集合无电离层诊断N中位数−1.784m；连续双频检验566窗、213条有足够伙伴且全GAL，关键BDS码缺连续双频相位，不能泛化处罚。新22项原生、53项Python通过；正式52项源码/EXE及Raw/产品SHA不变、两端33项pin匹配。本轮ADB未授权，未读新包/构建Android/安装；66891行TimeOffset全0，API ISB字段在实际G/E/C组内为公共项，未额外叠加卫星偏差。

## E21 · 正式NTRIP预测新息Huber候选（2026-11-07，负结果）

见 [NTRIP_INNOVATION_HUBER_TRIAL_20261107.md](NTRIP_INNOVATION_HUBER_TRIAL_20261107.md)。仅私有B_VERIFIED副本替换瞬时legacy处罚为完整预测方差的普通Huber，R0/Q/P0/历史质量/平滑/大气/验后硬拒绝/严格SSR不变。控制和候选各一次669期；末60s水平RMS1.822400→1.824255m，U RMS0.460213→0.463733m，84Q6均不变。5101试算行4条软降权均被撤销，4874最终GNSS行无软降权；12项原生检查通过。候选不采用、不迁移Android，不降阈值重做，不声称已修复水平偏差。

## E20 · 正式NTRIP84期水平偏差审计与诊断改造（2026-11-07）

见 [NTRIP_FORMAL_EN_AUDIT_20261107.md](NTRIP_FORMAL_EN_AUDIT_20261107.md) 及 `validation/ntrip_formal_en_20261107_v3/`。仅正式585s启动后的84期，6566条最终提交行中真实GNSS4874条。首期北向先验+0.317m，码更新贡献−1.928m，后验−1.637m；原始码空间拟合84期中位数E+1.046m/N−1.745m。轨钟年龄9～17s、来源/IOD/实际信号码偏差和天线支持检查通过；相位2148条活动弧/38条重建（含初始化）。首期最大条件码新息1.238，不能靠普通单期大残差发现该方向偏差；平滑新息的相关性不直接等于原始码有色误差。修改共享诊断的有界窗口和频率/周跳/弧元数据，PC768原生+49 Python通过，Android assembleDebug成功；33项真实pin两端匹配。重建正式669期除耗时外精确不变，水平末60s RMS仍1.822m。未修复定位误差、未改参数/启动规则、未安装。CLK304仍是文件旁支，不作为当前NTRIP主线前置。

## E19 · 文件审阅后的解决方案优先级

见 [PPP_SOLUTION_PRIORITY_20261107.md](PPP_SOLUTION_PRIORITY_20261107.md)。当前正式CLK304仍off=0，复用P01候选作为独立产品验证前置。文件路径前31输入期真实提交135条缺OSB提示码行和240条缺实际信号PCO提示码相行，证据在validation/solution_priority_20261107/file_evidence.json。历史10:13小时数据最新参考483.000m，连续末H0.716/U+.471，旧486.963参考的−3.492m不要当现行绝对高差；11:30参考另为483.98/483.96m。提出支持完备产品、独立中心匹配参考、有效弧段连续会话、可辨识慢变码误差四方案，未修改正式源码。

## E18 · 10/31 启动一致性与位置协方差试验

见 [WHU_STARTUP_CONFIDENCE_TRIAL_20261031.md](WHU_STARTUP_CONFIDENCE_TRIAL_20261031.md) 和 `validation/whu_startup_confidence_20261031`。小米SSR启动26/26历元北斗和Galileo码组均向东，25/26高低频同向；vivo方向不同。三条669历元路径的原配置、30秒一次恢复P、前30秒持续保留P、延后30秒首次PPP均完成。小米SSR末60秒东偏+1.477，三试验+1.464/+1.465/+1.437m；延迟使文件组和vivo水平RMS恶化，未消除东偏或达到持续60秒1m，勿当默认策略。控制轨迹逐字段与旧结果相同，SSR改正关联逐字节一致，52项正式文件SHA保留，报告和完整曲线已留存。

## E17 · 10/31 小米东偏的逐行产品与双手机对照

见 [WHU_MATCHED_PRODUCT_EAST_BIAS_20261031.md](WHU_MATCHED_PRODUCT_EAST_BIAS_20261031.md) 和 `validation/whu_east_matched_20261031`。两套小米前31历元、同期vivo前28历元与旧结果逐字段一致（耗时除外）。843共有码、672共有相位；固定坐标共同码差RMS 9.482m，钟差项9.259m。保留各自虚拟先验、同先验双向替换，扣公共项后首期东向约5cm，不能解释共有的米级东偏。相同码集合固定参考后，码减GIM的东向中位数SSR +0.956/文件 +0.778m；消去一阶电离层后仍同号26/26。实际联合状态第16秒固定XYZ目标增量21.186，预测先验19.210。同期vivo 584共同码行，说明共同分量与设备差异并存。已定位启动观测偏差及延续机制，手机、环境与共用产品仍无法唯一归因。原始证据、52项正式文件SHA及新报告保留，继续工作时直接读取结果。

## 最新E16：B1C联合状态零值一致性修复

见 [B1C_JOINT_STATE_CONSISTENCY_FIX_20261031.md](B1C_JOINT_STATE_CONSISTENCY_FIX_20261031.md)。新候选state_activity_fix_v2：B1I+B1C、无相邻300s启动等待。合法零状态故障已修复，989检查通过；实际669期坐标未变，原米级东偏未解决。不要将参考变换0.976m故障复现写成实际精度改善。码/相位分解及公共/星间条件分解已完成，正式/Android未切换。

## 最新E15：B1C联合实验（2026-10-31）

见 [WHU_B1C_JOINT_TRIAL_20261031.md](WHU_B1C_JOINT_TRIAL_20261031.md)。独立四模式669期/870检查完成，1P码4648相位4562实际提交；OFF精确复现旧轨迹。水平略好、高程末段变差，未替换正式或Android默认。旧B1C缺席结论仍适用于正式版本，不能重复运行本组或称已消除东偏。

# 2026-10-28历史排查索引（以下“当前”为当时状态）

以下原入口保留为历史，9m高差、459.813m参考及旧pin数量等不代表现行10/31数据或源码。现在接续以docs/CURRENT_STATE.md及最新E26为准，无需重跑历史。

## 当前结论

- 活动项目为 `E:\GNSS\PPP_NTRIP_PC`，Android为 `E:\android\test\PPP_NTRIP`。聊天默认的旧rtklib_Project2目录不是本轮工作项目。原PPP_only/FTPGet未在本轮修改。
- 当前WHU实际录流、非组合B_VERIFIED_v2_JOSEPH，参考高459.813 m为用户指定椭球高，已确认同高；不重开楼层／高程基准排查。
- 正高差入口主要随真实伪距及逐星电离层形状码差保留；该形状在连续弧中缺少相位支持。
- 最新：冻结各信号首样本差仍维持+11.288 m高差；只保留后续变化为-2.648 m。初始观测基准项很重要，但首样本不是硬件标定值。
- 因果漂移Huber仅改善约1.7 cm，不能修复主高差；不再降低阈值，不设默认。
- 已保存首期实际观测只有GPS/Galileo的证据；后续C06异常不能作为高差首次出现的唯一原因。
- 当前仍未证明新的正式符号／单位／索引错误，不能宣称约9 m已经修好。单频绝对I与未知码参考偏差仍缺独立基准。

## 最小阅读顺序

1. 最新起始码差报告E04。
2. 码侧状态形状报告E03。
3. 码／相／大气分离报告E02。
4. 因果Huber负结果N02。
5. 仅在需要具体背景时查下面其他条目。

## 分类

`FIX_VALIDATED`为应保留的正式修复；`LOCATING_EVIDENCE`为有效定位证据但不是可部署改正；`NEGATIVE_NOT_FIX`为有价值的排除结果；`SUPERSEDED_KEEP`为已被取代且保留来龙去脉；`CONFIRMED_SIDE_BUG_PENDING`为无关主高差的确定待修旁支。

### F01 · 卫星身份及ANTEX读取保护 · FIX_VALIDATED

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_COMPREHENSIVE_FIX_AND_CAUSAL_AUDIT_20261027.md)

保留正式修复。旧PRN/SVN身份确有问题，但没有解释全部9 m。

### F02 · CODE IONEX映射与穿刺点约定 · FIX_VALIDATED

[报告](E:/GNSS/PPP_NTRIP_PC/docs/CODE_IONEX_CONVENTION_FIX_REPORT_20261027.md)

保留AUTO物理约定；精度变差也不能以调参理由退回错误约定。

### E01 · 不同分析中心轨钟与有效码预测核验 · LOCATING_EVIDENCE

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_COMMITTED_UPDATE_AND_INDEPENDENT_REFERENCE_REPORT_20261027.md)

CODE只覆盖G/R/E，未认证BDS；原始CLK304读错的输出不作为有效参考，查验使用官方CLK_V2。

### E02 · 真实码与载波分块交叉回放 · LOCATING_EVIDENCE

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_CODE_PHASE_ATMOSPHERE_SEPARATION_REPORT_20261027.md)

真实P保留高差8.968 m，真实L/D配模型P为-0.404 m；模型码依赖已知参考，不是实际精度改善。

### E03 · 逐星电离层形状码差定位 · LOCATING_EVIDENCE

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_CODE_STATE_COMPATIBILITY_REPORT_20261028.md)

逐星空间形状组+11.262 m，公共组-2.993 m；不是物理I真值或独立误差贡献率。

### E04 · 起始码差与后续变化分离 · LOCATING_EVIDENCE

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_INITIAL_CODE_MEMORY_REPORT_20261028.md)

冻结首样本差+11.288 m，后续变化组-2.648 m；首样本含噪声和模型误差，不能直接标定硬件。

### E05 · 大气几何方向敏感性 · LOCATING_EVIDENCE

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_GIM_GEOMETRY_CAUSAL_REPORT_20261027.md)

只能证明联合状态对先验空间方向敏感，不证明GIM公式错误或可以默认弱化先验。

### N01 · 真实输入绕过伪距平滑均值 · NEGATIVE_NOT_FIX

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_DUAL_FREQUENCY_AND_REAL_SMOOTHER_CAUSAL_REPORT_20261027.md)

末期Up9.043→9.017 m，不能解决9 m；不默认关闭平滑，不重复。

### N02 · 因果码相漂移普通Huber · NEGATIVE_NOT_FIX

[报告](E:/GNSS/PPP_NTRIP_PC/docs/CAUSAL_CODE_CONSISTENCY_HUBER_REPORT_20261028.md)

末期Up9.043→9.025 m，7次实际软降权；保持关闭，不继续调低阈值。

### N03 · 仅替换初始位置均值 · NEGATIVE_NOT_FIX

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_INITIAL_HEIGHT_CAUSAL_REPORT_20261026.md)

历史LEGACY条件下仅毫米级变化；不等于本轮首样本观测基准分离，不重做相同位置初值试验。

### N04 · 手机已有WHU NRT与实录SSR局部核验 · NEGATIVE_NOT_FIX

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_PHONE_NRT_CROSSCHECK_REPORT_20261026.md)

同分析中心轨钟局部吻合不能独立认证全部产品；不再用NRT代替实录SSR证明精度。

### S01 · V1交叉夹具清零未建模槽 · SUPERSEDED_KEEP

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_CODE_PHASE_ATMOSPHERE_SEPARATION_REPORT_20261027.md)

V1空操作有厘米级副作用，保留但不作为主证据；以V2保留全部原始槽为准。

### P01 · 文件CLK3.04列宽偏移错误 · CONFIRMED_SIDE_BUG_PENDING

[报告](E:/GNSS/PPP_NTRIP_PC/docs/SSR_COMMITTED_UPDATE_AND_INDEPENDENT_REFERENCE_REPORT_20261027.md)

有native复现和私有候选验证，正式未修；当前SSR不读CLK文件，不能当作9 m根因。

## 有效性边界和避免重复

- 合成码／相使用已知参考位置，只能定位原因，不能宣传为实际0.4 m定位提升，不能写进App作为改正。
- 原始录流和TXT、旧反例／负结果保留。暂不删除旧日志，不重试此前被拒绝的删除操作。
- 已完成回放器拒绝覆盖目录；统计／绘图分析可以读既有证据。不要对已完成的参数、删星、平滑、码相交叉、投影和Huber试验再次全程回放。
- 老工具交付manifest记录当时源码SHA；私有工具随后扩展会改变其现行SHA，不表示当时证据失效。回放包装源码、对象和可执行文件是对应快照。正式core当前一致性以32份pin及新校验为准。
- 旧native/Python/JVM全套通过是历史记录，不冒称本轮重跑；当前新增检查分别见每项报告。
- 两个项目本轮未提交／推送／安装；不能由PC诊断推断手机已经运行新APK。
- 只保存公开挂载点标识和文件指纹，不复制账号密码到接续索引。

## 尚缺的独立约束

用户真值坐标已知，不需要再改真值。缺的是同期短基线测量型双频接收机观测或同等独立码／电离层基准；当前采集包未包含。用户已明确回复“没有”同期参考接收机RINEX，不再等待或重复索取该资料。不要用同一手机数据反算的状态冒充独立基准。

机器可读索引与当前报告SHA见 [PPP_INVESTIGATION_LEDGER.json](E:/GNSS/PPP_NTRIP_PC/docs/PPP_INVESTIGATION_LEDGER.json)。

## 数值保护历史

[Joseph及后验提交保护报告](E:/GNSS/PPP_NTRIP_PC/docs/HISTORICAL_JOSEPH_NUMERICAL_FIX_REPORT.md)。原数据／模式不同，仅作数值修复来历；当前SSR核心仍保留该保护，不把它当本次精度改善。

## 2026-10-28 独立资料确认

用户确认没有同期同点／短基线测量型双频接收机RINEX。继续保留已有真值坐标；不能用手机反算状态或合成码替代独立观测。现有资料仍可检验因果处理方案的行为，但不足以唯一分配单频绝对I与未知码基准偏差。未经验证不新增自由逐星偏差或默认调参。

## F04 · 2026-10-30 观测生成正式移植至 NTRIP · FIX_VALIDATED

报告：`docs/ANDROID_OBSERVATION_GENERATION_NTRIP_REPORT.md`。只移植固定钟段、时间精度、ADR/PRR、presence、RINEX和Raw辅助UTC；NTRIP/SSR及PPP参数/数值修复保留。新清单33项，历史清单/源码/旧APK/EXE已备份。Native51/PC768/Android源码579/Python42/JVM158通过4跳过；五Raw逐行核验通过；实际WHU701期回放成功，Q和流释放一致。APK构建未安装。100ms/GAL7Q/Native零值和异步限制仍明确保留。

原E01–E05/N01–N04等轨迹数字属于旧观测生成管线；有效证据保留，不自动作为新版本的同值结果。此次回放末Up仍约9.022m，未解决主偏差，也未据此重开PPP调参。

## E06 · 2026-10-31 真机新观测管线与最新精度验证 · LOCATING_EVIDENCE

报告：docs/ANDROID_CAPTURE_EFFECT_20261031.md。最新113002包669历元/585等待/84Q6。使用包内新参考［具体坐标留存本地］/［具体坐标留存本地］/椭球高483.98m，不复用10/25参考。末H1.721m、Up+.270m，末60RMS高程.460m，水平仍米级；短段不足稳定性验收。实际手机新观测代码与本地一致；PC复放观测逐行相同、坐标<.8微米。启动慢对应实收GPS偏差历元600s后300s序列，现有安全连续门控到585s才就绪。不同日期地点比较不能证明旧9m根因已修。无正式代码/参数/设备修改。原包、精度曲线和启动证据已保存，勿重复本次回放。

## E07 · WHU启动门控独立消融 · LOCATING_EVIDENCE

报告：docs/WHU_STARTUP_GATE_TRIAL_REPORT_20261031.md。相同669期/原到达前缀：严格控制585s开始/84Q6；首次正推进290s/378Q6+1Q5；首份完整诊断5s/663Q6+1Q5。末H/Up分别1.721/+.270、1.512/+1.112、1.693/+.388m；首份末60UpRMS.407m。首份实际偏差估计年龄最高910s，公开320s中位延迟不等于有效期上限，不能据本段精度直接设为正式默认。无正式源码/参数/手机修改；3组83项保护测试及原579回归通过、控制逐位复现。全部快照/构建/回放已保存，不重跑。

## E08 · 东北方向拆分与已存验后掩码复核 · LOCATING_EVIDENCE

报告：docs/WHU_EAST_NORTH_DIAGNOSIS_20261031.md。只读旧3组结果，不重跑。末60首份组E+1.477/N-.823m，E占水平平方76.3%；启动改进主要改善N而E偏置仍在。三组载波卫星/槽/几何60/60一致；不能用简化DOP认定PPP根因。最终汇总掩码357/360可唯一重建，3组不明保留；E29极大残差4期被排除，G25C1C60/60匹配包含且mean-7.431m。缺实际R/S/K，尚不能判G25造成东偏或直接删星。状态关联非因果；下一步仅需精确追该行有效R与K_EN/联合状态，不重新泛化排查。无正式代码/参数/手机改动。

## E09 · 完整卫星DOP与逐星几何作用 · LOCATING_EVIDENCE

报告：docs/WHU_DOP_ANALYSIS_20261031.md。只读旧结果，未PPP重算/剔星。常规及多钟DOP、星座子集、逐星几何LOO/天空图已保存；末60载波多钟H1.011,E.764,N.652；重建码集合57期H.717,E.486,N.525。早中期E几何优于N但E偏置已在，不支持“东向DOP太差”简单根因；末段载波集合减少仅解释后期DOP升高。3组几何60/60同，Native3例差1.2e-14。GPS子集不足不等于联合PPP失败，DOP不含实际R/P/I/N/trop，不当误差米值或实际K。G25几何移除反使EDOP增.044，未实际删星，因果仍待原行R/S/K。原证据/默认/设备未变。

## E10 · 真实逐行增益、同先验原生反事实与首期东偏 · LOCATING_EVIDENCE

报告：[WHU_ACTUAL_GAIN_AND_INITIAL_BIAS_20261031.md](E:/GNSS/PPP_NTRIP_PC/docs/WHU_ACTUAL_GAIN_AND_INITIAL_BIAS_20261031.md)。单次独立观察回放，669期数值状态/观测/改正与原首份诊断一致。G25末60真实v均值-7.433m，去行重求K的East局部均差仅-.351mm，不支持末段大残差直接推动米级东偏；不是完整删星实验。第5秒已有东偏，G25第11秒才参与。SPP首期位置虽东偏1.983m，但首期位置直接先验传递仅.001333m/m，不能归咎SPP锁死。490项早期离线原生敏感性显示多行码与I先验共同定解，仍无确定公式错误。77个完整矩阵复现逐位相同，12项新测试通过，正式源码/参数/设备未改。后续仅复用第5～16秒保存方程检查码/I/接收机码基准兼容；不要重跑G25/DOP/旧P0R大范围排查。

## E11 · 码参考/I/RCB兼容性：真实矩阵与完整参考变换 · LOCATING_EVIDENCE

报告：[WHU_CODE_IONO_RCB_COMPATIBILITY_20261031.md](E:/GNSS/PPP_NTRIP_PC/docs/WHU_CODE_IONO_RCB_COMPATIBILITY_20261031.md)。只读第5～16秒，无新回放。652真实H行通过，Galileo全x/P/H换参考12次ENU差0，未见确定连接错误。30个I/clock/RCB/N零方向不改变GNSS方程，但其位置分量为0，不是东偏直接因果证明。E21/E23首期GIM条件隐含RCB差6.047m，实际完整S下仅.860σ，全12期<.973σ，不能据米数判错或剔除。E21相位在0到8历元间断弧，禁止跨弧固定N归因I；C07仅单频码。9项新测试通过；原源/旧增益证据不变，未发现可立即修复的确定错误。不重复绝对I/RCB不可辨识性或扩大QC/P0R排查。

## E12 · 用户指定FTPGet文件与同段SSR对照 · LOCATING_EVIDENCE

报告：[WHU_FTPGET_FILE_VS_SSR_20261031.md](E:/GNSS/PPP_NTRIP_PC/docs/WHU_FTPGET_FILE_VS_SSR_20261031.md)。同113002包669期/ref483.98，同核心同参数；private入口一处允许文件，正式仍SSR-only。原SSR控制逐位复现；手机FTPGet6产品SHA相同，BIA复用day304有效码记录，不用day303外推，大气/天线与包一致。文件组667Q6，末ENU+1.709/-.552/-1.310m，末60RMS H1.798/U1.333m；早启SSR H1.691/U.407m。文件未消除米偏差；行集合、启动历史、参考回退及有效R不同，不能全归轨钟或证明SSR错误。统一预检0错误21告警完整保留，8测试通过。无正式/Android改动；自己的新大表gzip，原产品和旧证据保留，不重复此两路。

## E13 · 此前整星座理解的独立排除试验（保留） · LOCATING_EVIDENCE

证据：validation/whu_constellation_east_20261031。原首份SSR诊断/排除C07/排除北斗，末ENU分别+1.480/-.822/+.388、+1.363/-.804/+1.196、+1.995/-.642/-3.733m，三组663Q6/1Q5/5等待。全部B1C关闭，不能当B1C联合使用验证；排除北斗反而变差，C07有高程代价，不设默认。原生同先验分解与两次完整回放独立保留，不重跑或累加局部差当最终收益。

## E14 · B1C未实际接入，适配器与核心槽位未贯通 · LOCATING_EVIDENCE

报告：[WHU_B1I_B1C_USAGE_20261031.md](E:/GNSS/PPP_NTRIP_PC/docs/WHU_B1I_B1C_USAGE_20261031.md)。用户澄清主问题后完成Raw→映射→准入→实际H核对。Raw5794条1P但当前0参与；2I正常。adapter两者slot0，policy在竞争前排除1P，核心1P支持slot3/独立RCB；因此当前无覆盖证据，但不能直接放开准入。原生频率识别正确，81快照C1PRCB的H支持0，Android/PC3文件同SHA，7项检查通过。未改默认或宣称东偏已找到唯一原因。后续若授权联合接入，应统一1P独立槽与偏差/天线/弧段，勿再把整星座剔除当B1验证。
