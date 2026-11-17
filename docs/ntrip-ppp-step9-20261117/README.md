# Step 9 · SPP 启动方程与首个 Q6 前的东偏

2026-11-17。实验使用六组已有正式配置及原三流到达前缀。11/14 四包沿用 Step 5 已存基线的 V1，10/31 单独保留 V1、V2 两组。11/14 的 Q6 计数按这批配对基线统计。后续 PPP 归因沿用 Step 5/6，不追加定权或删星对照。

## 已定位的启动环节

- 六组中，`pntpos_startup` 的接纳坐标在首个 Q6 同历元写入 `rtk->sol`，`udpos_ppp` 从它初始化位置。首个 Q6 接纳试次的验前 ECEF 与 SPP 输出逐分量完全相同。此前只有 Q0，Q5、成功提交的 PPP 更新、二次 SPP 覆盖和退回旧位置均为零。直接记录的先验 ENU 与 Step 5 已保存的反算最大差 1.09×10⁻⁹ m，四组正东偏与 Step 6 逐项对齐。
- 11:20 时段，小米与 vivo 的启动 E 相差 3.635 m。GPS 1C 的东向贡献分别为 +1.351 和 −2.877 m，差 +4.228 m，Galileo 与北斗抵消部分差值。GPS 1C 里 G25 是该历元主要方向贡献之一，小米 +1.093 m、vivo −2.510 m。
- 10:04 vivo 的 +2.121 m 东偏主要由 BDS 2I 贡献 +1.858 m。10:04 小米的 +1.402 m 则同时由 GPS 1C +0.738 m 与 GAL 1C +0.712 m 推动。这个 SPP 结论与 Step 5 后续 60 期 PPP 的 GPS 1C 主推力对应不同阶段。
- 10/31 V2 接纳的 15 条实测行是 8 条 GAL 1C 和 7 条 BDS 2I，两组分别贡献 +1.207 和 +0.776 m 东偏。此历元 GPS 公共钟列由零新息的秩亏约束支撑。SPP 公共钟约为 0，两个 ISB 各包含约 9.35 km 的公共分量。PPP 验前对公共钟重新定中心为 +9346.850 m，位置坐标原样传入。10/31 V1 的首解时刻不同，此时已包含 5 条 GPS 1C。
- 逐个实测星座注入数学上的 +1 m 常量向量，用同一线性化设计直接投影。位置各分量最大绝对响应为 6.93×10⁻¹⁵ m。GAL/BDS 常量进入各自 ISB。GPS 可见时，GPS 常量进入公共钟，GAL/BDS ISB 出现 −1 m 相对变化。按钟差列剔除组公共项后，各组 E 贡献变化最大为 1.15×10⁻¹⁴ m。东偏由本批 SPP 方程里的组内相对残差经几何投影产生。手机测码、卫星产品和大气模型各自占多少，现有证据无法唯一归因。

## 方程与核验

- 观察器记录 SPP 调用、每个求解尝试和迭代、`valsol` 结果、FDE 候选选择、最终 `*output = *sol`，及 `rtkpos` 是否采用为 PPP 启动。全段 4,710 个 SPP 尝试，4,707 次通过 `valsol`，3 次迭代未收敛（均在 10:04 vivo 首解之后）。这六组未触发删星候选，FDE 替换路径有独立标记但本次无实录样本。
- 最终接纳的六个启动方程共导出 115 条实测首槽码和 19 条虚拟秩亏约束。记录原始码、实际改正码、几何/钟差/大气项、分项方差、实权、H 和 K。采集包实际使用 `EPHOPT_SSRCOM`，因此改正码来自原始首槽码加 WHU SSR 码偏差，广播 TGD/ISC 未叠加。电离层与对流层分别使用广播模型和 Saastamoinen。验后同时保留线性残差与接纳坐标上的只读非线性重算。
- 以最终一次真实加权迭代的 H、W 计算 K。参考位置只在解后进入平移 `v_ref = v + H × (x_before − x_anchor)`，其中 `x_anchor` 为评价参考 ECEF 与接纳 SPP 的钟差/ISB。逐行 `K × v_ref` 加实测的浮点加法舍入项闭合于 SPP 输出减该参照。最大闭合差 1.95×10⁻¹⁴ m，实际最终 LS 改正数最大复算差 4.35×10⁻¹⁵ m。从最初种子累计各次接纳解路径的增量，单列求解器数值差与状态更新舍入，最大闭合差 5.52×10⁻¹⁰ m。钟差列加权投影及 Schur 消元的核验见明细。
- 私有构建从源文件重编译 29 个回放对象。六组 6,202 历元、4,703 个 Q6，首个 Q6、所有 Q 值与 `solution.csv` 除 `processing_ms` 外逐字段一致，`observations.csv`、`corrections.csv`、`solution.stat` 逐字节一致。实验前后核对原 Step 8 的 223 项清单、9 个正式二进制及 PC/Android 各自的 33 项共享内核。正式代码和产物未改。

## 复核入口

- [终端表](TERMINAL_TABLES.md) · [首解状态链](spp_to_first_q6_chain.csv) · [分星座与约束贡献](spp_constellation_contributions.csv) · [钟差耦合](spp_clock_coupling.csv) · [核验](verification.json)
- 本地逐行正规方程见 `spp_accepted_rows.csv`，[迭代闭合摘要](spp_iteration_closure.csv)，全部求解尝试见 `spp_attempts.csv`，原始观察器日志见 `runs/<dataset>/observer.tsv`。含伪距或可还原绝对位置的记录仅保留在本机。公开的分星座 CSV 只含固定线性化分解。验证清单分别保存本地完整产物及公开文件的哈希。
- [构建](build_private.py) · [回放](run_replays.py) · [评价](evaluate.py) · [私有补丁](step9_private.patch) · [SPP 观测钩子](step9_spp.inc) · [状态钩子接口](step9_audit.h)。复现时在有原始输入与旧基线的 PC 工程中新建 `validation/brain_step9_spp_bootstrap_audit/`、放入脚本与钩子，依次执行构建、回放和解后评价。各脚本使用项目的 Python 环境，评价依赖 NumPy。
