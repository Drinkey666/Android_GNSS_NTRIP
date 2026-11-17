"""Render audit CSVs as a terminal-friendly Markdown report."""
from audit import OUT, PRIMARY, read, rows

def md(out, title, headers, items):
    out.extend(["",f"## {title}","","| "+" | ".join(headers)+" |",
                "| "+" | ".join("---" for _ in headers)+" |"])
    out.extend("| "+" | ".join(map(str,row))+" |" for row in items)

def signed(row, *keys):
    return "/".join(f"{float(row[key]):+.3f}" for key in keys)

def enu(row, prefix, suffix="_m"):
    return signed(row,*(prefix+axis+suffix for axis in "ENU"))

def main():
    result=read(OUT/"verification.json")
    result_summary=result["observations"]
    best=result_summary["nominal_best"]["candidate"]
    files={p:rows(OUT/(p+".csv")) for p in ("frame_offsets","reeval_accuracy","common_east_by_candidate",
                "cross_site_consistency","dual_phone_consistency","step5_code_ablation")}
    out=["# Step 12 终端汇总", "",result_summary["result"]]
    offsets={ (r["site"],r["scenario"]):r for r in files["frame_offsets"] if r["velocity_model"]==PRIMARY}
    def interval(r):
        return signed(r,"vel95_low_E_m","vel95_high_E_m")
    md(out,"候选参考改正（米，加到原参考）",
       ["候选","11/14 ΔE/ΔN/ΔU","11/14 ΔE 速度敏感区间","10/31 ΔE/ΔN/ΔU","10/31 ΔE 速度敏感区间"],
       [(case,enu(r,"delta_"),interval(r),enu(offsets["10-31",case],"delta_"),interval(offsets["10-31",case]))
        for (site,case),r in offsets.items() if site=="11-14"])
    out.extend(["","显式列出的速度敏感区间仅传递局部速度误差和站间散布。现历元没有速度传播项，框架实现差另见报告。"])
    acc={(r["dataset"],r["scenario"]):r for r in files["reeval_accuracy"]
         if r["velocity_model"]==PRIMARY and r["window"]=="tail60"}
    modern="WGS84_G2139_obs_NGA2024"
    md(out,"六包末 60 s（米）",["包","Q6 数","原参考 E/N/U","CGCS2000 E/N/U",
       "现历元 G2139 E/N/U","原 H/U RMS","CGCS2000 H/U RMS"],
       [(d,r["n"],enu(r,"","_mean_m"),enu(acc[d,best],"","_mean_m"),enu(acc[d,modern],"","_mean_m"),
         "/".join(f"{float(r[k]):.3f}" for k in ("H_RMS_m","U_RMS_m")),
         "/".join(f"{float(acc[d,best][k]):.3f}" for k in ("H_RMS_m","U_RMS_m")))
        for (d,c),r in acc.items() if c=="original"])
    md(out,"共同东向均值及分组（米）",
       ["候选","六包等权","11/14","10/31 V1/V2 平均","10/31 V2","两点按 V2 去重等权","vivo","小米去重"],
       [(r["candidate"],*(f"{float(r[k]):+.3f}" for k in ("E_equal6_m","E_1114_m","E_1031_policy_mean_m",
         "E_1031_V2_m","E_two_independent_site_days_V2_m","E_vivo_m","E_xiaomi_V2_m")))
        for r in files["common_east_by_candidate"] if r["velocity_model"]==PRIMARY])
    md(out,"B1 跨点比较（11/14 四组末段平均减 10/31，米）",
       ["10/31 口径","PPP ΔE/ΔN/ΔU","参考 ΔE/ΔN/ΔU","PPP差减参考差 E/N/U","PPP H/参考 H/差向量 H"],
       [(r["oct31"],enu(r,"PPP_"),enu(r,"reference_"),enu(r,"PPP_minus_reference_"),
         "/".join(f"{float(r[k]):.3f}" for k in ("PPP_H_m","reference_H_m","difference_H_m")))
        for r in files["cross_site_consistency"] if r["nov14"]=="mean_4_sessions"])
    pair=result["policy_pair"]
    out+=["",f"10/31 同一采集的 V2−V1 在 {pair['common_tail_epochs']} 个共有末段 Q6 给出 "
              f"{enu(pair,'V2_minus_V1_')} m。该差值由解坐标直接相减。"]
    md(out,"B2 同点双机比较（小米减 vivo，米）",
       ["时段","窗","共有数","PPP ΔE/ΔN/ΔU","H(均差) / 逐对 H RMS","两机对原参考的共同 E"],
       [(r["session"],r["window"],r["n"],enu(r,"xiaomi_minus_vivo_"),
         "/".join(f"{float(r[k]):.3f}" for k in ("H_of_mean_m","paired_H_RMS_m")),
         signed(r,"pair_common_original_mean_E_m")) for r in files["dual_phone_consistency"]])
    masked={(r["dataset"],r["scheme"]):r["E_tail_m"] for r in files["step5_code_ablation"]}
    md(out,"B3 Step 5 存档的末 60 s E（米）",["包","原基线","+屏蔽 GPS 码","+屏蔽 GAL 码","+屏蔽 BDS 码"],
       [(d,*(f"{float(masked[d,k]):+.3f}" if masked[d,k] else "无存档" for k in
        ("Baseline","NoGPSCode","NoGALCode","NoBDSCode")))
        for d,s in masked if s=="Baseline"])
    text="\n".join(out)+"\n"
    (OUT/"TERMINAL_TABLES.md").write_text(text,encoding="utf-8",newline="\n")
    print(text)

if __name__=="__main__":
    main()
