# 独立 WHU OSB 缓存修复与三轮诊断

PC 和 Android 已正式隔离 WHU 轨钟数据与独立 OSB 缓存。Android 生产代码和测试位于应用目录。PC 在原工程构建与运行，这里保存相应的源码快照、验证和交接。

| 内容 | 文件 |
|---|---|
| Android 生产修复和回归 | [ntrip_ssr.cpp](../../app/src/main/cpp/ntrip_ssr.cpp#L245) · [ntrip_ssr_test.cpp](../../app/src/main/cpp/tests/ntrip_ssr_test.cpp#L144) |
| PC 生产修复和回归 | [ntrip_ssr.cpp](pc-source/src/ntrip_ssr.cpp#L245) · [ntrip_ssr_test.cpp](pc-source/tests/ntrip_ssr_test.cpp#L174) |
| 第一轮：双机码相分解、K·v 与互换 | [报告](validation/brain_step1_diagnosis_20261116/REPORT.md) · [汇总表](validation/brain_step1_diagnosis_20261116/CORE_TABLES.md) |
| 第二轮：逐星贡献与时间分解 | [报告](validation/brain_step2_closure_20261116/REPORT.md) · [逐星排名](validation/brain_step2_closure_20261116/per_satellite_signal_ranking.csv) |
| 第三轮：单机质控与 WHU 准入 | [报告](validation/brain_step3_final_audit_20261116/REPORT.md) · [准入汇总](validation/brain_step3_final_audit_20261116/whu_window_summary.csv) |
| 正式修复四包验证 | [报告](validation/whu_osb_formal_fix_20261117/REPORT.md) · [逐历元 CSV](validation/whu_osb_formal_fix_20261117/whu_q6_and_admission_by_epoch.csv) · [测试计数与 SHA-256](validation/whu_osb_formal_fix_20261117/verification.json) |
| 项目交接和规则 | [Android 状态](../CURRENT_STATE.md) · [PC 状态](pc-docs/CURRENT_STATE.md) · [排查索引](pc-docs/PPP_INVESTIGATION_INDEX.md) · [证据台账](pc-docs/PPP_INVESTIGATION_LEDGER.json) · [Android 规则](../../AGENTS.md) · [PC 规则](pc-docs/AGENTS.md) |

四包 2,623 历元的正式验证 CSV 与第三轮逐字节一致。SHA-256 为 `adb8e73fc6530c920789abf4835798447b0473f17093f2d721786eef7815bf10`。PC 源码保留 Windows 构建时的文件字节，Android Git 源码使用仓库的 LF 约定。

公开验证证据保留相对误差、状态增量和准入差异。精确参考坐标、原始伪距/载波列、采集包、连接凭据和个人 APK 留在本地。四包完整因果复跑需要本地原始记录和产品快照。

11/16 的报告描述当时的问题和私有探针，见 [历史问题报告](../ntrip-ppp-review-20261116/README.md)。
