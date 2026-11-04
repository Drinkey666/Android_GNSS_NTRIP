# 本轮确定问题：静态 ANTEX 产品使用了错误的卫星身份

## 确定结论与影响边界

**找到了有直接证据的软件产品管理缺陷：安卓把 ANTEX 当作只需复制一次的静态表，并以文件大小、文件头作为“可用”依据。实际北斗 PRN 已在 2026 年重新分配，但本次冻结产品仍为旧卫星提供天线记录。**

这不是调参结论，也不是按坐标精度挑选产品。官方带日期的 PRN/SVN 元数据与旧文件的卫星身份直接冲突。本次手机冻结的 ANTEX 与当前 APK 工程内置资产 SHA256 完全相同。

**但这处错误不是全部约 9 m 偏差的解释。** 只替换四颗身份错误卫星的官方记录，末点 Up 从 +9.0672 m 变为 +9.2074 m；使用完整官方卫星 ANTEX 后为 +8.2161 m。正确性修复不应以误差一定降低为成立条件，不能将完整产品更新的 0.8511 m 差值全部归给四颗身份替换。

本轮正式源码、资产、默认参数和手机 APK 均未改。所有替换仅在独立 PC 输出目录中生效。

## 1. 卫星身份冲突证据

参考历元为本次观测 2026-10-25；官方元数据为 `igs_satellite_metadata_2441.snx` 对应内容（2026-10-22 更新）。

| 实际参与的 PRN | 采集 ANTEX 中的 SVN | 官方当期 SVN | 旧类型 | 正确类型 |
|---|---|---|---|---|
| C06 | C005 | C220 | BEIDOU-2I | BEIDOU-3I |
| C07 | C007 | C221 | BEIDOU-2I | BEIDOU-3I |
| C08 | C008 | C224 | BEIDOU-2I | BEIDOU-3I |
| C12 | C013 | C233 | BEIDOU-2M | BEIDOU-3M-CAST |

例如 C06 的 B1I PCO，旧记录 NORTH/EAST/UP 为 `[580,0,3500] mm`，正确 C220 为 `[-69.59,-309.85,1999.59] mm`。这是不同物理卫星的标定，不能因 PRN 相同继续沿用。

元数据明确记载 C005 的 C06 使用期于 2026:100:43200 结束，C220 从 2026:100:57600 使用 C06。C013 的 C12 使用期于 2026:111:14400 结束，C233 从 2026:111:28800 使用 C12。旧 ANTEX 没有这些终止/重新分配记录，因而按其自身日期查找仍可错误通过。

官方依据：[IGS 卫星元数据](https://files.igs.org/pub/station/general/igs_satellite_metadata.snx)、[2026 年北斗重新分配公告](https://lists.igs.org/pipermail/igsmail/2026/008688.html)、[IGS ANTEX 目录](https://files.igs.org/pub/station/general/)。本地保留完整元数据、官方 `igs20_2437.atx.gz`、下载回执和哈希。

原冻结/内置 ANTEX SHA256 均为 `fd9955ae17d759291e62e144db8e47a3d4f38bb1d8aae7a8e093fbc6cad0b79f`。官方完整压缩文件 SHA256 为 `22897a9f31449de93e9943cb6ecf3212acf24bde81b1b83cfc3aa648d73a5454`。

为节省空间，对官方 ANTEX1.4 流式解压，仅提取原样卫星块；完整压缩原件仍保留，不落盘约 59 MB 的完整解压副本。提取文件包含 414 个原样卫星历史块、原始文件头，约 5.2 MB。当前配置没有加载接收机天线模型，卫星子集与该加载方式相容，不是人工修改标定值。

## 2. 缺陷如何进入程序

安卓副本 `E:/android/test/PPP_NTRIP`：

1. `app/src/main/java/com/example/ftpget/BundledProducts.kt:13` 的 `ready()`：ANTEX 只要求 ≥1 MB、第一行含格式标志。
2. 同文件第 34 行：已有文件通过上述检查就跳过复制，不能识别“格式完整但卫星身份已过时”。
3. `FtpDownloader.kt:529` 的 `downloadAtxProduct()` 实际只复用本地文件；536 行通过同一个 `ready()` 即报告可用。
4. `LivePppProducts.kt:91/122` 按名称/文件选择 ATX；本次 `LiveSsrSession` 快照真实保留了旧文件，哈希链没有丢数据问题。
5. PC `src/gnss_replay.c:410` 加载产品，412 行 `searchpcv()` 为各 PRN 选择记录。
6. `core/rtkcmn.c:2743` 的 ANTEX 读取与 2884 行 `searchpcv()` 依靠文件中的 PRN、有效期。它们没有独立 SVN 元数据来识别旧文件中错误的无限有效期。**不能将正常的日期查找函数单独说成公式错误；产品管理没有保证其输入身份正确。**
7. `core/ephemeris.c:824` 的 COM→参考 APC，以及 `core/ppp.c:3507/3525` 的逐信号天线项实际使用了该记录；错误标定进入码相模型。

## 3. 原样参数的完整因果回放

相同实测 701 历元、同期 WHU 三流、IONEX/VMF3、参考坐标和全部模型选项。每组独立清零启动。没有改变 R/Q/P0/GIM/抗差阈值、SSR 时效或广播匹配。

| 组 | 唯一产品差异 | 末点 E/N/U，m | 最后 60 个 Q6 的 Up RMS，m |
|---|---|---|---:|
| 原始 | 原冻结 ANTEX | 1.5473 / 1.4492 / 9.0672 | 9.1725 |
| C06/C12 | 仅这两个 PRN 的全部历史块换成官方原样块 | 1.4924 / 1.2017 / 9.0298 | 9.1318 |
| 四个身份 | 仅 C06/C07/C08/C12 换成官方原样块 | 1.5804 / 1.3782 / 9.2074 | 9.3069 |
| 完整官方卫星 | 全部官方卫星块 | 1.5127 / 1.1798 / 8.2161 | 8.3624 |

所有组 Q0/Q5/Q6 为 223/1/477，没有新增数值失败。全程曲线、初/中/后期统计、ZTD、负 ZWD 计数及重启日志计数保存在 `antex_replay_comparison.json` 与 `antex_identity_trajectories.csv`。官方更新也改变部分可用信号标定和准入结果；不能把完整更新当成仅改变两个 PCO 常量的实验。

![完整时间序列对比](E:/GNSS/PPP_NTRIP_PC/validation/ssr_pair_reference_20261025/antex_identity_comparison.png)

## 4. 对剩余大误差的进一步约束

在相同实际星历/SSR 输入上，独立 Python 标量 Kepler、解析速度、钟差与地球自转计算核对 16 个卫星快照，参考 BNC 官方 ephemeris 实现：

- 广播坐标最大分量差约 1.87e−8 m；SSR COM 坐标差最大约 1.17e−7 m。
- 解析速度与原 1 ms 差分速度导致的卫星钟差最大差约 3.24e−5 m。
- 一阶 Sagnac 与直接旋转距离的差约 0.00025 m 以内。
- 独立原始报文位解码确认 140 个 BDS 码偏差帧，12 个快照的 B1I/B3I 值与 native 一致。这份标为 OSBC00WHU1 的实际录制数据使用标准 RTCM1260，不是 IGS IM105；按实际报文识别，BDT→GPST 转换一致。大/特殊偏差值真实存在于有效 CRC 报文中，不能归为本地 PRN/信号码或符号位解码错。

上述核对使用相同产品输入，**不等于另一个分析中心已证明 WHU 实际轨钟正确**。BNC 未作为独立完整软件运行；这里是单独实现的轨道/钟差算术核对。[BNC 参考源](https://software.rtcm-ntrip.org/export/HEAD/ntrip/trunk/BNC/src/ephemeris.cpp)、[IGS SSR 格式](https://files.igs.org/pub/data/format/igs_ssr_v1.pdf)。

对 tow22335～22366 的 C06/C12 同频连续弧：两星各有 32 个非零载波样本，LLI 均为 0；仅起点 C06 重建，此后两星无已确认重置。固定位置后，构造未扣 N 的星间差：

```
DP = (P6* - P12*) - Δ(rho - c*dt_sat + T_forecast)
DL = (L6* - L12*) - Δ(rho - c*dt_sat + T_forecast)
```

同频下 `DP+DL` 消去一阶电离层；公共接收机钟差/ISB 在星间差中消去，连续弧的常量模糊度在时间差中消去。31 秒变化为：

- ΔDP = +6.0919 m；ΔDL = −0.1355 m。
- **Δ(DP+DL) = +5.9564 m**，不能只解释为一阶电离层变化。
- GIM 预测的该星间电离层差只变化 +0.0528 m。
- 该时段实际码偏差差为常数，旧天线星间项仅变化约 0.00005 m。静态天线身份错误不能单独解释这 31 秒变化。

实际码还存在因果 Doppler 平滑。原始码模型星间差在序号 129 为 13.1908 m；当前平滑差分 −1.8531 m 后为 11.3377 m，与上一轮同次矩阵条件化的 11.3403 m 接近。不能把“实际平滑码残差”直接称作原始伪距误差。

**剩余最强证据是滤波前已存在随时间变化、非纯一阶电离层的码相/模型不一致。** 它仍需区分时变码/相偏差、实际轨钟产品参考/误差及未建模项，不能凭这组方程把其中某个量强行认定为错误。已经尝试取得同期 WHU RTS 轨钟归档作外部对照，但本次 FTP/FTPS 数据连接超时，HTTPS 端点未打通；当前目录也没有同期归档，不能拿旧日期产品替代。失败访问记录已保存，后续不必重复泛化查询。

这里请求的 RTS 归档不是 NRT 预报，也不是要更换手机实时方案。[WHU 官方说明](https://lists.igs.org/pipermail/igsmail/2026/008720.html)指出，实时产品会归档为 WUM0MGXRTS 轨道、钟差、偏差产品。其用途是：在坐标/APC-COM、钟差基准、相对论和 OSB/SSR 符号统一后，核对本地从实际 SSR 还原的量与官方归档是否一致。两者来自同一分析中心，不能将归档称为独立定位真值，也不能未统一基准就按差值判本地程序错误。归档只是下一层交叉核验手段，不能反馈未来文件到手机实时回放。

## 5. 最小正式修复范围与交付状态

可以实施的确定修复是**产品版本和卫星身份管理**，不是滤波参数：

- 更新过时内置 ANTEX，同时让已有旧文件有备份、可追溯地迁移；只换 APK 中资产而继续跳过旧本地文件不会生效。
- `BundledProducts`、`downloadAtxProduct()`、`LivePppProducts` 增加官方版本/内容身份校验，按观测日期核对 PRN→SVN；来源元数据与最终 ANTEX 一起冻结留档。
- 格式正确但身份不相容时明确报产品错误，不能仍以“文件存在/下载完成”启用对应模型。

本轮没有自动实施这些正式改动，也没有覆盖手机或原始数据。所找缺陷已经可复现；**米级精度问题仍未全部解决，四星身份单因素实验也没有带来精度改善。**

工具：`run_ssr_pair_reference_probe.py`、`ssr_pair_reference_probe.inc`、`analyze_ssr_pair_reference.py`、`check_ssr_pair_bias_bits.py`、`audit_antex_satellite_identity.py`、`run_ssr_antex_identity_replay.py`、`analyze_antex_identity_replay.py`。

证据目录：`validation/ssr_pair_reference_20261025/`，入口 `antex_identity_audit.json`、`antex_replay_comparison.json`、`independent_bias_bits.json`、`analysis.json`、下载回执与独立运行 `command.json`。

观察器最初放在更新前，会扰动天文函数内部时间缓存，造成最大约 7.45e−9 m 的 XYZ 差；已移至更新之后。最终只读回放的 701 历元除耗时外逐字段相同，stat/obs 逐字节相同。保留 `observer_order_check.json` 说明，不将纳米级诊断缓存效应说成 9 m 根因。

本轮新增验证包含 16 次轨钟计算、12 次实际码偏差快照核对、32+32 样本弧段连续性检查、三组独立 701 历元产品回放。正式 32 核心文件与 Android pin、原始 ZIP 指纹再次核验。历史 native/JVM 全套未重跑；没有声称新 APK 已安装或精度已验收。大型生成日志可从 `.gz` 直接分析，清理仅针对哈希核验过的本轮未压缩副本。

12 个生成日志已压缩并作 SHA256 往返核验：41,170,889 字节压至 4,594,302 字节，释放约 34.9 MiB；原始包、原产品与官方压缩原件保留。证据目录合计约 30.6 MB。压缩后重新执行诊断分析与指纹验证通过。
