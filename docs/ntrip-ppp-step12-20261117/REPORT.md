# Step 12 · 参考坐标框架、历元与共同东偏

**PARTIAL。** 在 CGCS2000（ITRF97@2000.0）的假设下，两处参考点转至 ITRF2020@观测历元的东向改正为 +0.924 m 和 +0.922 m。六包末 60 s E 的等权均值从 +1.178 降到 +0.255 m，逐包范围从 +0.626～+1.620 变为 −0.298～+0.696 m。两处点位及两类手机的分组均值仍为正。10/31 V1/V2 共用一份原始记录，以 V2 作为该日代表、两点等权，残余从 +1.312 降到 +0.389 m，传播局部速度误差后的区间为 +0.351～+0.427 m。现历元 ITRF2014/G2139 的毫米级改正保留原量级东偏。定量上支持固定旧历元能够解释一部分共同项，实际 CORS 框架与历元仍待服务商证实。

## A1 · 解端框架与产品证据

| 证据 | 能确立的事实和边界 |
|---|---|
| PC `config/caster_whu.json:5–8`，`src/pc_ssr_replay.cpp:122–124,183–192`，Step 5 六个 `Baseline/command.json:10–11,38–39` | 实际为 SSRC00WHU0 质心轨钟、OSBC00WHU1 偏差和 BCEP00BKG0 广播星历，回放配置为 COM / `EPHOPT_SSRCOM`。COM 是卫星参考点。|
| PC `core/rtcm3.c:1467–1494,1827`，`src/ntrip_ssr.cpp:309–325`，`core/ephemeris.c:767–773,814–834,862–863` | 解码 orbit datum 的 global/regional 标志，正式门控拒绝 regional。SSR 轨道改正沿径向/切向/法向施加到地固轨道，钟差单独按当前历元施加。归档 RTCM 标志只能证实全局基准类别，精确实现及速度无显式字段。|
| IGS RTS 产品表、WHU 产品公告与直接使用该挂载点的重建研究 | 官方挂载点与 CoM/OSB 配套一致，直接重建研究报 IGc20。IGS 周期表显示 GPS 周 2401 起为 ITRF2020-u2024 的 IGc20，覆盖本批周 2442、2444。重评估采用 ITRF2020 家族作为解端基准。具体这六包 WHU 轨钟的逐包实现声明无法从 RTCM/归档单独认证。|
| 六份冻结 `product_antenna.ATX:1–2`，Android `app/src/main/assets/gnss_products/igs20.provenance.json:2–5,8–10`，PC `src/gnss_replay.c:410–414`，`core/ephemeris.c:822–830` | ANTEX 1.4 绝对校准。六包字节 SHA 与 IGS20_2437 官方卫星子集来源凭据一致。代码将 PCO/PCV 用作观测模型的质心/相位中心几何校准。它也不能作为逐包解端实现的独立认证。|
| 冻结 `product_ionex.INX:1–2,26,35–36`，`core/ionex.c:551–565`，`core/ppp.c:2503–2515,3931` | CODE/AIUB 预报 TEC 网格覆盖两次会话，代码用其派生电离层先验。IONEX 头中的零均值 datum 是偏差产品定义。|
| 冻结 `product_vmf_first:1–7` 和 `product_vmf_second:1–7`，`core/ppp.c:555–568,3057–3060,4021` | TU Wien VMF3_FC 给出纬经网格映射函数与天顶延迟，覆盖当日 00/06 UTC 两端。IONEX 和 VMF3 代码是大气延迟模型调用，未发现把接收机 ECEF 换到另一个地固框架的路径。大气建模误差仍可经估计耦合到位置。|

外部依据见 [IGS RTS 挂载点表](https://www.igs.org/rts/products/) · [WHU 的 IGS 公告](https://lists.igs.org/pipermail/igsmail/2024/008420.html) · [IGS 实现时序](https://rts.igs.org/wg/reference-frame/) · [WHU SSR 重建及 IGc20](https://www.mdpi.com/1424-8220/26/21/7061) · [官方 ANTEX](https://files.igs.org/pub/station/general/igs20_2437.atx.gz)。

## A2 · 参考来源

用户确认两处均由 RTK 仪器经 RTK/CORS 网络服务测得，手簿选择 WGS84。本地检索覆盖 PC 的文档、验证目录、导入包与 Android 参考配置代码。11/14 四包 `imported/capture.json:1` 保存 `frame=WGS84`、`source=USER_CONFIGURED` 和椭球高类型。10/31 V1/V2 共用 `validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json:2–8`，来源标签只关联 10/31 11:30 采集。两机所绑参考相差 **0.209 m 水平**。

Android `ui/ReferencePositionSection.kt:67–90,110` 从手动 DMS 输入取参考，`MainActivity.kt:247–250,498` 保存并绑定，`ReferencePositionStore.kt:7–17` 写本地首选项，`NtripCaptureStore.kt:229–236` 固定写入标签和高程类型。冻结文件里无法取得**服务商、服务名、基准站或网络解实现、参考历元、仪器型号、实际测量日期和原始 RTK 报告**。采集日期与表中的观测历元是两条独立于参考框架的已知信息。Android 工程本地无独立 `captures/` 目录，PC 导入元数据确实可读。 [不含坐标的捕获元数据](reference_metadata.csv)

### 需向 CORS 服务商核实

1. 两次作业分别用了哪个服务商、账号对应产品和挂载点，输出来自实体基站、VRS 还是其他网络解。
2. 基准站和网络改正采用的实际框架及实现版本是什么，是否为 CGCS2000，或明确版本的 ITRF/地方项目框架。
3. 基站坐标的**坐标历元**是什么，输出按固定历元还是按测量时刻表达。请分别确认两次实测日期，提供 RTK 报告或导出元数据。
4. 是否使用速度场或地震形变模型更新基站坐标，是否有地方七参数、平移或高程转换，手簿的 WGS84 是否仅决定椭球和显示。

## A3 · 计算、权威参数与不确定度

- 先在候选椭球将同一录入数值转地心坐标。CGCS2000 用 GRS80。用 2015.0 位置向量约定的 14 参数及其年率，先在候选坐标历元逆变换到 ITRF2020，再用局部 ITRF2020 速度传播到每个 Q6 的观测历元。原参考切平面投影，`Δ参考 = 候选参考 − 原参考`。评估从原误差中减去该向量。两点表用 11/14 小米和 10/31 V2 的首 Q6 时刻，十进制年分别约 2026.8689、2026.8305。每包评分保留其自己的参考值和时间。 [CGCS2000 的 ITRF97@2000 定义](https://unstats.un.org/Unsd/geoinfo/RCC/docs/rccap18/CRP/18th_UNRCCAP_econf.100_crp%2016.pdf) · [NASA/NSIDC R007 附录 B 及 Eq. 1–2](https://nsidc.org/sites/default/files/documents/technical-reference/icesat2_comparison-guide_r007.pdf)
- 主模型水平取 Wang & Shen (2020) Table S4 的 ITRF2008 绝对速度，按 Helmert 导数换至 ITRF2020。每处各取最近 8 站，距离在约 10～60 km，以 `1/max(10 km,d)^2` 加权。不从 PPP 残差拟合速度。垂向取成渝 CCEA v2 邻近 8 站的 H Rate，按同样权重传播，垂向为敏感性估算。另一完整局部对照用 CCEA 速度，将其固定欧亚速度加回 ITRF2014-PMM 欧拉速度后再转入 ITRF2020。 [原论文](https://doi.org/10.1029/2019JB018774) · [S4 原始数据](https://doi.org/10.7910/DVN/C1WE3N) · [CCEA 对应论文](https://doi.org/10.3389/feart.2024.1403620) · [CCEA v2 数据](https://doi.org/10.5281/zenodo.11203896) · [ITRF2014-PMM Table 1](https://doi.org/10.1093/GJI/GGX136)
- ITRF2020-PMM EURA（Altamimi 等 2023 Tables 1–2）加 ORB，仅采用水平分量，垂向沿用 CCEA。刚性欧亚对照的 CGCS2000 东改正为 **+0.735/+0.734 m**。CCEA 局部速度对照为 **+0.927/+0.926 m**。官方 ITRF2020 SSC 给出 WUHN/KUNM/KMNM/LHAZ 的 E 速度约 **33.18/34.80/32.25/46.01 mm/yr**。这些站距评估点数百至千余公里，且 KMNM 是金门，作为区域量级交叉检查。 [ITRF2020-PMM](https://doi.org/10.1029/2023GL106373) · [IERS SSC 发布目录](https://datacenter.iers.org/products/reference-systems/terrestrial/itrf/itrf2020/)
- 速度敏感区间用各方向的加权站间散布和原站标准差合成，再乘 1.96 和传播年数。两点共用速度模型，区间按完全相关项传递，不按样本数缩小。主模型 11/14 的 CGCS 框架修正 E 区间 +0.886～+0.962 m、N −0.262～−0.169 m、U −0.119～+0.099 m。这是速度敏感区间，未计入网络具体实现、基站变动、测量误差或本地点垂向突变。
- 现历元 ITRF2014 使用同历元 Helmert，G2139 另给 NGA 2024.0 固定七参数近似，后者无可用年率。G2296 用零 ITRF2020/IGS20 对齐代理，NGA 报告其量级为 2 cm 以内。现历元诸行的零速度传播宽度与实现误差是不同量。 [NGA G2139](https://earth-info.nga.mil/php/download.php?file=%28U%29WGS+84%28G2139%29.pdf) · [NGA G2296 Table 2](https://earth-info.nga.mil/php/download.php?file=WGS+84%28G2296%29.pdf)

## A4 · 六包重评估

首 Q6、前 20/60 个 Q6、全段和末 60 s 共五种窗。末窗采用 Step 5 的“距最后有效 Q6 小于 60 s”，11:20 小米 59 个，其余各 60 个。H/U RMS 逐历元计算。六包原参考全段与末窗的历史统计最大复算差 **1.78×10⁻¹⁵ m**，共 4,703 个 Q6。原坐标、轨迹及评估参考文件保持各包现有绑定。11/14、10/31 及 vivo/小米在最接近的候选下仍分别呈正均值，10:04 两机合并仍为 +0.501 m。10/31 同采集的 V1/V2 两组不作独立日期样本。 [终端表](TERMINAL_TABLES.md) · [全部候选精度](reeval_accuracy.csv) · [两点框架偏移](frame_offsets.csv) · [共同量与分组](common_east_by_candidate.csv)

## B · 差分交叉验证

- **B1 跨点**。11/14 四组末段平均减 10/31，参考水平距离 10.182 m。PPP 的相对距离为 V2 11.504 m、V1 11.930 m。PPP 差向量减参考差向量，V2 为 **−0.329/+1.318/−1.873 m**，V1 为 **+0.149/+2.009/−1.911 m**。两点相邻，共同框架平移在差分中近乎相消，因此差分对绝对共同项的来源约束有限。同一 10/31 原始记录的 60 个共有末段 Q6，V2−V1 为 **+0.478/+0.691/−0.038 m**。 [跨点全表](cross_site_consistency.csv)
- **B2 同点双机**。以两机解的中点定义坐标轴，按共有 GPST 秒比较。全窗 11:20（349 期）小米减 vivo 为 **−0.496/−0.089/+1.677 m**，H=0.504 m，共同 E（各自对照原参考再取平均）+0.836 m。10:04（1,457 期）为 **+0.381/+1.565/−1.568 m**，H=1.610 m，共同 E +1.497 m。10:04 共有末窗的东西互差 +0.335 m 小于共同 +1.427 m，北向和高程仍有显著差异。数据支持存在共享东向分量，参考框架和两机共同使用的模型/产品都可以产生这一模式。 [全窗及末段配对](dual_phone_consistency.csv)
- **B3 星座码消融**。15 项已有结果全部保留正号，E 范围 **+0.297～+2.348 m**，较各自基线的最大变化 **0.871 m**。单星座码屏蔽无法普遍消掉东偏，幅值仍随观测组合显著变化。各试验继续共享 WHU、IONEX 与 VMF3，现有消融无法排除共享产品误差。10/31 V1 的三项未存档。 [消融逐包表](step5_code_ablation.csv)

## 核验、失败与跳过

- PC 9/9 正式二进制、245/245 Step 11 守卫和 62/62 本轮依赖在评价前后均匹配。零次正式构建、零次回放、零次重跑滤波。既有 `core/`、`src/`、`bin/` 及历史验证目录未写入。 [核验清单](verification.json)
- IGN 主站入口维护中，Helmert 表改用 NASA/NSIDC 公开副本并与 IERS/参数说明对照。IERS SSC 首次下载遇到 Windows 证书吊销状态查询不可用，改为尽力吊销查询后下载成功，保留 TLS 证书链校验。首次 SSC 解析漏了无显式分段号的站，补齐格式后重算通过。最终全部六包及公开速度源均读入。
- CORS 元数据和 RTK 原始报告无法取得，10/31 V1 三个消融缺档。未执行这些额外试验，参考坐标不进入解算。

## 复现

在本机新建本层级的独立验证目录，放入 [参数与转换](frame_model.py)、[评估和守卫](audit.py)、[终端表生成](make_tables.py)。按参数脚本内的固定 URL 获取 S4、CCEA 与 IERS SSC 三个公开速度源并核哈希。用项目 Python（NumPy）依次运行 `audit.py before`、`audit.py evaluate`、`make_tables.py`。完整精度表在本地按双精度保存，可分享 CSV 的地点相关数值舍入到毫米级，公开版不附逐站精确距离表或原始文件。
