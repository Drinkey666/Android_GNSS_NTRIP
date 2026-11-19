"""Create terminal-readable metric tables using only shareable results."""
from evaluate import OUT, rows, ALL, SCHEMES, DATASETS, read

def table(headers,body):
    return "\n".join("| "+" | ".join(map(str,r))+" |" for r in [headers,["---"]*len(headers),*body])
def short(s):
    return s.split("_")[0]
def vals(row,keys,delta=False):
    return " / ".join(format(float(row[("d_" if delta else "")+k]),"+.3f" if delta else ".3f") for k in keys)
def rms(w):
    return [w+"_H_rms_m",w+"_U_rms_m"]
def main():
    acc=rows(OUT/"partB_accuracy_summary.csv")
    pv=rows(OUT/"partB_paired_common_q6.csv")
    v=read(OUT/"verification.json")
    lines=["# Step 12 自适应 PPP · 六包对照",
           "单位为米。H 为水平误差模长，U 为有符号垂直误差。Δ 为方案减去同包 Step 5 基线。RMS 的正差表示精度反退。",
           "first20 / first60 取最早的 20 / 60 个 Q6。tail60 取末个 Q6 向前严格小于 60 秒的 Q6。首解延迟从本包首个记录历元算起。所有方案的 Q 序列相同。",
           "## 各包覆盖",table(["数据包","总历元","Q0 / Q5 / Q6","首 Q6 延迟（s）","tail60 样本"],
             [[r["dataset"],r["epochs"]," / ".join(r[k] for k in ("q0","q5","q6")),f'{float(r["first_q6_delay_s"]):.3f}',r["tail60_n"]] for r in acc if r["scheme"]=="Baseline"])]
    keys=[["first_q6_"+a+"_m" for a in "ENUH"],rms("first20"),rms("first60"),rms("all"),
          ["tail60_"+a+"_mean_m" for a in "ENU"],rms("tail60")]
    for d in DATASETS:
        group=[r for r in acc if r["dataset"]==d]
        lines.append("## "+d)
        for delta in (False,True):
            if delta: lines.append("相对基线的差值（m）。")
            lines.append(table(["方案","首 Q6 E / N / U / H","前20 H / U RMS","前60 H / U RMS","全段 H / U RMS",
                                "末60 s E / N / U 均值","末60 s H / U RMS"],
                         [[short(r["scheme"])]+[vals(r,ks,delta) for ks in keys] for r in group if not delta or r["scheme"]!="Baseline"]))
    lines.extend(["## 双机共有 Q6",
        "同一 GPST 周内，依 Step 5 口径按最近整数秒作一对一评价配对。两个窗口的最大实际时差见表；回放、闭合与逐历元 Q 守卫保留各机原始小数秒。",
        table(["窗口","方案","共同历元","最大时差（ms）","小米 H / U RMS","小米 ΔH / ΔU","vivo H / U RMS","vivo ΔH / ΔU"],
              [[r["pair"],short(r["scheme"]),r["common_q6"],f'{1000*float(r["max_pair_skew_s"]):.4f}',
                *[vals(r,[phone+"_H_rms_m",phone+"_U_rms_m"],de) for phone in ("xiaomi","vivo") for de in (False,True)]] for r in pv]),
        "## 最终提交中使用的动作",
        "退火弧次按每历元激活的星与频槽计数，方差为这些弧次注入的过程方差之和。A2 均值以最终提交的全部真实伪距行为分母。逐历元表另列覆盖状态、最终试算序号、CMC 触发及电离层限幅。",
        table(["数据包","方案","码行","A1 膨胀行 / 最大倍数","A2 膨胀行 / 最大倍数","CMC 加权行","退火弧次 / Σq（m²）","电离层 Q 减半星次"],
            [[r["dataset"],short(r["scheme"]),r["code_rows"],f'{r["a1_inflated_rows"]} / {r["max_f_out"]:.2f}',
              f'{r["a2_inflated_rows"]} / {r["max_f_stoch"]:.2f}',r["cmc_boost_rows"],
              f'{r["anneal_arcs"]} / {r["anneal_variance_m2"]:.4f}',r["a3_single_freq_ion_q_halved"]] for r in v["cases"]])])
    (OUT/"TERMINAL_TABLES.md").write_text("\n\n".join(lines)+"\n",encoding="utf8")
if __name__=="__main__": main()
