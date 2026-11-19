"""Create terminal-readable metric tables using only shareable results."""
from evaluate import OUT, rows, ALL, SCHEMES, DATASETS, read

def table(headers,body):
    return "\n".join("| "+" | ".join(map(str,r))+" |" for r in [headers,["---"]*len(headers),*body])
def short(s):
    return s.split("_")[0]
def vals(row,keys,delta=False,scale=1.0):
    return " / ".join(format(scale*float(row[("d_" if delta else "")+k]),"+.3f" if delta else ".3f") for k in keys)
def rms(w):
    return [w+"_H_rms_m",w+"_U_rms_m"]
def main():
    acc=rows(OUT/"partB_accuracy_summary.csv")
    pv=rows(OUT/"partB_paired_common_q6.csv")
    v=read(OUT/"verification.json")
    lines=["# Step 13 固定参数消融 · 六包对照",
           "单位为米。H 为水平误差模长，U 为有符号垂直误差。Δ 为方案减去同包 Step 5 基线。RMS 的正差表示精度反退。",
           "first20 / first60 取最早的 20 / 60 个 Q6。tail60 取末个 Q6 向前严格小于 60 秒的 Q6。首解延迟从本包首个记录历元算起。所有方案的 Q 序列相同。",
           "## 各包覆盖",table(["数据包","总历元","Q0 / Q5 / Q6","首 Q6 延迟（s）","tail60 样本"],
             [[r["dataset"],r["epochs"]," / ".join(r[k] for k in ("q0","q5","q6")),f'{float(r["first_q6_delay_s"]):.3f}',r["tail60_n"]] for r in acc if r["scheme"]=="Baseline"])]
    keys=[["first_q6_"+a+"_m" for a in "ENUH"],rms("first20"),rms("first60"),rms("all"),
          ["tail60_"+a+"_mean_m" for a in "ENU"],rms("tail60")]
    lines.insert(1,"B1＝纯 EMA；B2＝原 A1 + 电离层 Q 减半；B3＝原 A1 + 纯 EMA；B4＝原 A1 + 纯 EMA + 电离层 Q 减半。A1、A2 为 Step 12 保存结果。")
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
        "重叠行同时触发 A1 与纯 EMA；限幅星次只计最终提交中生效的卫星；扣回量为本试算所用各星电离层预测增量的一半之和，单位 m²。全方案均关闭 Step 12 的 CMC 附加倍率和模糊度退火。",
        table(["数据包","方案","码行","A1 膨胀行 / 最大倍数","纯 EMA 膨胀行 / 最大倍数","重叠行","电离层 Q 减半星次","扣回量（m²）"],
            [[r["dataset"],short(r["scheme"]),r["code_rows"],f'{r["a1_inflated_rows"]} / {r["max_f_out"]:.2f}',
              f'{r["ema_inflated_rows"]} / {r["max_f_stoch"]:.2f}',r["a1_ema_overlap_rows"],
              r["ion_q_halved_satellites"],f'{r["ion_q_removed_m2"]:.6f}'] for r in v["cases"]])])
    ct=rows(OUT/"partB_ablation_contrasts.csv")
    for key,title in [("remove_cmc","关闭 CMC（B1−A2）"),("ionq_given_a1","原 A1 上减半电离层 Q（B2−A1）"),
                      ("ionq_given_a1_ema","原 A1 和纯 EMA 上减半电离层 Q（B4−B3）")]:
        scale=1 if key=="remove_cmc" else 1000
        lines.extend(["## "+title+("（m）" if scale==1 else "（mm）"),
              table(["数据包","前20 ΔH / ΔU","前60 ΔH / ΔU","全段 ΔH / ΔU","末窗 ΔH / ΔU","末窗 ΔU 均值"],
              [[r["dataset"],*[vals(r,rms(w),True,scale) for w in ("first20","first60","all","tail60")],
                f'{scale*float(r["d_tail60_U_mean_m"]):+.4f}'] for r in ct if r["contrast"]==key])])
    lines.extend(["## 原 A2 变化的保留与收回",
          "保留比例 = (B1−基线)/(A2−基线)；收回比例 = 1−保留比例。对 10:04 小米看保留了多少收益，对 10/31 V2 看收回了多少反退。U 均值和 U RMS 分列。",
          table(["数据包","指标","基线（m）","A2（m）","B1（m）","保留","收回"],
                [[r["dataset"],r["metric"],*[f'{float(r[k]):.4f}' for k in ("baseline_m","A2_m","B1_m")],
                  *[f'{float(r[k]):.1%}' for k in ("retained_fraction_of_A2_change","removed_fraction_of_A2_change")]]
                 for r in rows(OUT/"partB_focus_effects.csv")])])
    (OUT/"TERMINAL_TABLES.md").write_text("\n\n".join(lines)+"\n",encoding="utf8")
if __name__=="__main__": main()
