# Step 11 报告：已保存基线全段/末60秒东向平衡切片（Part A）与 `S1..S4` 隔离实验评估（Part B）

- **结论归类**：
  - **Part A（只读 `tail60` 与全段 `K·v` 切片）**：`LOCATING_EVIDENCE`
  - **Part B（`S1_O1_robust`、`S2_Q0_presmooth`、`S3_presmooth_cmd`、`S4_joint`）**：四组均判定为 **`NEGATIVE_NOT_FIX`（不进入正式版）**，提供明确的物理定位排除证据。
- **合规边界**：严格非组合浮点 PPP（`used_if=False`、`used_ar=False`、`reference_used_only_after_replay=True`），零修改正式 `core/`、`src/`、`bin/`；24 组新回放与 Step 5 基线逐历元 `same_Q=True`、`observations.csv` 与 `corrections.csv` 逐字节一致，每历元 `K·v` 最大闭合差 `4.6565e-10 m`。

---

## 1. Part A：已保存基线全段与 `tail60` 东向 `K·v` 平衡切片（只读）

复用 Step 5 基线 `solution.csv`、`solution.stat`、`solution.trace`（245 项输入/基线哈希锁定前后一致，单历元 `max |x_after - x_before - Σ(K·v)| = 4.6566e-10 m`）：

| 数据集 | Q6 / tail60 | 首→末 Q6 E (m) | 全段 / 末60s E均值 | 首后 Code / Phase / IONEX / ZWD E | 末60s净ΔE / 步均Code E | 末历元非零 `$RCB` (m) |
| --- | --- | --- | --- | --- | --- | --- |
| `11:20 小米` | 349 / 59 | `+0.486 -> +0.648` | `+0.613 / +0.626` | `-0.959 / +0.018 / +1.104 / -0.001` | `+0.023 / -0.0002` | `BDS_C5P=+0.425; GAL_C5Q=+1.927; GPS_C5Q=+3.567` |
| `11:20 vivo` | 362 / 60 | `-0.882 -> +1.141` | `+1.060 / +1.116` | `+1.127 / -0.042 / +0.942 / -0.005` | `+0.089 / +0.0011` | `GAL_C5Q=+1.405; GPS_C5Q=+1.357` |
| `10:04 小米` | 1459 / 60 | `+1.837 -> +1.612` | `+1.713 / +1.620` | `+0.322 / +0.067 / -0.614 / -0.001` | `-0.013 / -0.0002` | `BDS_C5P=+0.200; GAL_C5Q=+1.875; GPS_C5Q=+1.650` |
| `10:04 vivo` | 1786 / 60 | `+3.824 -> +1.233` | `+1.273 / +1.229` | `-2.304 / +0.020 / -0.302 / -0.005` | `+0.009 / +0.0001` | `GAL_C5Q=+1.150; GPS_C5Q=+0.614` |
| `10/31 小米 V1` | 84 / 60 | `+1.247 -> +1.185` | `+1.009 / +0.999` | `-0.061 / +0.004 / -0.005 / +0.000` | `+0.307 / +0.0040` | `BDS_C5P=+2.646; GAL_C5Q=+2.999; GPS_C5Q=+3.856` |
| `10/31 小米 V2` | 663 / 60 | `+1.252 -> +1.479` | `+1.617 / +1.477` | `+1.372 / +0.184 / -1.330 / +0.001` | `-0.013 / +0.0000` | `BDS_C5P=+2.460; GAL_C5Q=+2.989; GPS_C5Q=+3.256` |

核心物理发现：
1. **末 60 秒增益已冻结，稳态东偏锁定在收敛前期**：除总长仅 84 个 Q6 的 `10/31 小米 V1`（`tail60` 净推东 `+0.307 m`，主要由 `G25 +0.305 m`、`C20 -0.143 m` 仍在收敛）外，其余 5 组 `tail60` 净东移仅 `-0.013 ~ +0.089 m`，步均 Code 增益 `-0.0002 ~ +0.0011 m/epoch`，累计相位增量 `<= 0.002 m`。
2. **载波与对流层非主因，首频伪距（`1C/2I`）与 IONEX 平衡决定稳态基准**：全段 `PHASE` 东向净推力仅 `-0.042 ~ +0.184 m`，`VMF3_ZWD` `<= 0.005 m`；而 `5Q/5P` 次频码硬件偏置已被 `$RCB` 参数显式吸收（末历元 `GPS_C5Q +0.614~+3.856 m`、`GAL_C5Q +1.150~+2.999 m`、`BDS_C5P +0.200~+2.646 m`）。最终东向基准由 `CODE` 与 `IONEX` 在收敛期共同锁定（如 `11:20 vivo` 从 `-0.882 m` 推至 `+1.141 m`，来自 `ex1_CODE +1.127 m` 与 `ex1_IONEX +0.942 m`；`10/31 小米 V2` 由 `ex1_CODE +1.372 m` 对冲 `ex1_IONEX -1.330 m`）。

---

## 2. Part B：面向泛在手机的四组正交隔离实验（24 组回放）

- `S1_O1_robust`：双频锚定单频电离层先验 `I_GIM + δI_df`（`ndf >= 3`），单频标准差下限由 Step 10 的 `0.60 m` 放宽至 `0.90 m`，`udiono_ppp` 过程噪声尺度由 `0.5x` 放宽至 `0.7x`，且恢复单频 `ION_CONSTR_ROBUST` 抗差膨胀。
- `S2_Q0_presmooth`：在 `gnss_replay.c` 初始 `Q0` 等待期（`ready < 4 && !rtk->ppp_clock_valid`）仅对原始域运行 `prepare_signal_quality_ppp` / `precheck_obs_ppp` / `uddoppsm_ppp(..., NULL)`，绝不触碰 `rtk->x/P/sol`。
- `S3_presmooth_cmd`：`S2` + 跨星等权中位去钟漂的因果 1s CMD 残差方差 EMA（`alpha=0.25`，`count >= 4` 后启用 `f_cmd = clamp(0.5 * cmd_var_ema / max(base_obs_var, 1.0), 1.0, 16.0)` 缩放码测量方差项，保持 `sigma0/z0` 原值）。
- `S4_joint`：`S1` + `S3`。

关键数值结果（完整表见 [`TERMINAL_TABLES.md`](TERMINAL_TABLES.md) 与 [`partB_accuracy_summary.csv`](partB_accuracy_summary.csv)）：
1. **`S1_O1_robust`（放宽后仍存在跨场景高程退化）**：
   - `11:20 小米 / vivo` 与 `10:04 小米 / vivo` 全段 `U_rms` 仍稳定改善（分别 `-0.124 / -0.192 / -0.087 / -0.102 m`）。
   - 但 `10/31 小米 V1 / V2` 全段 `U_rms` 仍退化（`0.881 -> 0.993 m`、`0.469 -> 0.772 m`），`tail60 U_rms` 分别为 `0.896 m`（基线 `0.460 m`）与 `1.007 m`（基线 `0.407 m`）。说明即使放宽至 `0.90 m` 并保留 `ION_CONSTR_ROBUST`，在 `10/31` 等实际电离层与 `I_GIM + δI_df` 存在残差偏离的时段，无条件收紧单频先验仍会将模型偏差挤入高程估计；水平精度变化仅 `-0.094 ~ +0.055 m`，无法消除稳态东偏。
2. **`S2_Q0_presmooth`（首 20s 双向敏感，无助于稳态东偏）**：
   - `Q0` 预平滑在所有等待期数据包均真实激活（`10/31 V1` `585` 历元/`32,982` 槽，`11:20 vivo` `273`/`10,387`，`11:20 小米` `268`/`12,203`，`10:04 小米/vivo` `12`/`544` 与 `504`，`10/31 V2` `5`/`218`）。
   - `first20` 表现呈明显双向性：`10:04 vivo` 水平 `H_rms` 从 `3.432 -> 2.202 m`（`-1.230 m`）但高程 `U_rms` 由 `1.473 -> 2.395 m`（`+0.923 m`）；`10/31 V1` 高程 `U_rms` `1.611 -> 0.517 m`；`10/31 V2` 水平 `2.386 -> 2.163 m`、高程 `1.777 -> 1.160 m`；而 `11:20 小米` 反而退化（`first20 H_rms` `0.681 -> 1.099 m`，`U_rms` `0.399 -> 0.707 m`），因为 `268` 秒等待期内的早期原始码多路径残差被 `DOPPSM=0.90` 带入了 `first_q6`。
   - 对收敛后稳态 `tail60` 东偏几乎无改变（五组长序列仍在 `+0.642 ~ +1.636 m`），证实等待期原始域平滑无法消除准静态码偏差。
3. **`S3_presmooth_cmd`（关键负结果证实手机误差主要不是 1s 高频白噪声）**：
   - 全 6 组共计 `124,363` 条建模码观测行上，`f_cmd > 1` 触发占比仅 `0.0% ~ 0.3%`（`11:20 小米` `5/10828`、`11:20 vivo` `14/8053`、`10:04 vivo` `113/41632`，其余 3 组为 `0`；均值 `f_cmd` `1.000 ~ 1.005`），致使 `S3` 与 `S2` 轨迹几乎重合。
   - **物理解释**：基线按 C/N0、高度角与信号权重给出的 `base_obs_var` 已有 `5 ~ 160 m²`（`σ ~ 2.2 ~ 12.6 m`），而手机实测 1 秒去钟漂 CMD 高频随机噪声方差 `0.5 * E[res_cmd^2]` 多数远小于该先验方差；真正限制手机非组合浮点 PPP 收敛与稳态基准的并非高频随机跳变，而是 **1 秒时间差分看不见的准静态/低频多路径与信号组内码偏置**。

---

## 3. 文件与验证清单

- 代码补丁与构建：[`step11_mods.inc`](step11_mods.inc)、[`step11_private.patch`](step11_private.patch)、[`build_private.py`](build_private.py)（构建 `step11_probe.exe`，`validation/build.json` 未变更）
- 回放与评估脚本：[`run_replays.py`](run_replays.py)、[`evaluate.py`](evaluate.py)
- 汇总表与证据 CSV：[`TERMINAL_TABLES.md`](TERMINAL_TABLES.md)、[`verification.json`](verification.json)、[`partA_tail60_east_slice.csv`](partA_tail60_east_slice.csv)、[`partA_tail60_top_sats.csv`](partA_tail60_top_sats.csv)、[`partB_accuracy_summary.csv`](partB_accuracy_summary.csv)、[`partB_cmd_presmooth_stats.csv`](partB_cmd_presmooth_stats.csv)、[`partB_paired_common_q6.csv`](partB_paired_common_q6.csv)
