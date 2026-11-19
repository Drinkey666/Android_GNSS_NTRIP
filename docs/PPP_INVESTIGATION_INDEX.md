# PPP有效排查记录索引

更新：2026-10-28。供后续接续使用；先读本页和最新报告，无需重跑全部历史。

## 小米两段晚间采集、码偏差断解与武大文件对照（2026-11-19）

11/20 小米首解后新增卫星的垂向修正已在 PC 双包验证。22:36 的 6 颗新 Galileo E1C 使当秒高程改善 1.524 米，下一秒仅余 0.039 米，首分钟 RMS 改善 0.046 米。22:21 首解仍为 −0.020 米，首分钟高程改善 0.013 米。后半段原版伪距净下拉 1.661 米，以北斗 C13 B1I（−0.404 米）和 GPS G06 L1 C/A（−0.351 米）为首。手机保留现行版本。 [首分钟精度与逐星垂向贡献](ntrip-xiaomi-new-sat-20261120/REPORT.md)

11/20 小米 22:21、22:36 的两种 PC 改法已在共同历元分别验证。22:36 放宽启动高程方差只让首个 Q6 的高程改善 1.3 毫米；22:21 连续弧码降权让末分钟高程 RMS 从 2.408 升至 2.504 米，实际放宽的电离层先验为 0 行。EMA 在 22:36 全段水平／高程改善 0.084／0.291 米，但首分钟水平退化 0.256 米。手机保留现行版本。 [同历元指标、曲线与可信度](ntrip-xiaomi-isolated-fixes-20261119/REPORT.md)

11/19 小米晚间两包精度归因。22:36 首个单点解仅用 9 颗北斗 B1I，高程初值 −11.832 米；按星座钟投影后 C06、C27 分别贡献 −9.27、−4.77 米。22:21 首个 PPP 更新后 U 为 −0.020 米，首分钟后伪距与 IONEX 约束累计向下 1.407、0.665 米。四次私有诊断重现正式解，已取得进入估计器的路径，物理误差仍待独立分离。 [启动与逐历元更新](ntrip-xiaomi-accuracy-origin-20261119/REPORT.md)

11/19 小米 22:21 与 22:36 两包首次复核。武大码偏差估计未推进造成连续 10／54 期缺解，PC 以采集前已有的同日偏差文件独立补回，原有 Q6 可逐期保留。冻结 EMA 定权后，22:36 原 830 期水平／高程 RMS 从 1.354／2.382 降至 1.270／2.090 米，22:21 高程仅改善 0.0025 米。完整同批武大文件在第二段高程更好，第一段两项均退步。手机维持原版。 [报告与误差曲线](ntrip-xiaomi-2221-2236-20261119/REPORT.md)

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

报告：docs/ANDROID_CAPTURE_EFFECT_20261031.md。最新113002包669历元/585等待/84Q6。使用包内新参考30.767151638888887/103.97950708333333/椭球高483.98m，不复用10/25参考。末H1.721m、Up+.270m，末60RMS高程.460m，水平仍米级；短段不足稳定性验收。实际手机新观测代码与本地一致；PC复放观测逐行相同、坐标<.8微米。启动慢对应实收GPS偏差历元600s后300s序列，现有安全连续门控到585s才就绪。不同日期地点比较不能证明旧9m根因已修。无正式代码/参数/设备修改。原包、精度曲线和启动证据已保存，勿重复本次回放。

## E07 · WHU启动门控独立消融 · LOCATING_EVIDENCE

报告：docs/WHU_STARTUP_GATE_TRIAL_REPORT_20261031.md。相同669期/原到达前缀：严格控制585s开始/84Q6；首次正推进290s/378Q6+1Q5；首份完整诊断5s/663Q6+1Q5。末H/Up分别1.721/+.270、1.512/+1.112、1.693/+.388m；首份末60UpRMS.407m。首份实际偏差估计年龄最高910s，公开320s中位延迟不等于有效期上限，不能据本段精度直接设为正式默认。无正式源码/参数/手机修改；3组83项保护测试及原579回归通过、控制逐位复现。全部快照/构建/回放已保存，不重跑。

## E08 · 东北方向拆分与已存验后掩码复核 · LOCATING_EVIDENCE

报告：docs/WHU_EAST_NORTH_DIAGNOSIS_20261031.md。只读旧3组结果，不重跑。末60首份组E+1.477/N-.823m，E占水平平方76.3%；启动改进主要改善N而E偏置仍在。三组载波卫星/槽/几何60/60一致；不能用简化DOP认定PPP根因。最终汇总掩码357/360可唯一重建，3组不明保留；E29极大残差4期被排除，G25C1C60/60匹配包含且mean-7.431m。缺实际R/S/K，尚不能判G25造成东偏或直接删星。状态关联非因果；下一步仅需精确追该行有效R与K_EN/联合状态，不重新泛化排查。无正式代码/参数/手机改动。

## E09 · 完整卫星DOP与逐星几何作用 · LOCATING_EVIDENCE

报告：docs/WHU_DOP_ANALYSIS_20261031.md。只读旧结果，未PPP重算/剔星。常规及多钟DOP、星座子集、逐星几何LOO/天空图已保存；末60载波多钟H1.011,E.764,N.652；重建码集合57期H.717,E.486,N.525。早中期E几何优于N但E偏置已在，不支持“东向DOP太差”简单根因；末段载波集合减少仅解释后期DOP升高。3组几何60/60同，Native3例差1.2e-14。GPS子集不足不等于联合PPP失败，DOP不含实际R/P/I/N/trop，不当误差米值或实际K。G25几何移除反使EDOP增.044，未实际删星，因果仍待原行R/S/K。原证据/默认/设备未变。
