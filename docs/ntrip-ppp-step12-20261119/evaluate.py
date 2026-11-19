"""Post-replay evaluation. Raw obs, products and absolute positions stay local."""
from collections import Counter
import csv
import math
from pathlib import Path
from statistics import fmean
import sys
from guard import ROOT, OUT, OLD, read, save, sha
from run_replays import SCHEMES, DATASETS, baseline
sys.path.insert(0,str(ROOT/"tools"))
from evaluate_solution import enu

ALL=("Baseline",*SCHEMES)
def rows(p):
    with p.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))
def write(name,data):
    with (OUT/name).open("w",encoding="utf8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
def key(r):
    return r["week"],r["tow"]
def epoch(k):
    return int(k[0])*604800+float(k[1])
def ref(d):
    if d.startswith("1031"):
        return read(ROOT/"validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json")["reference"]
    args=read(baseline(d)/"command.json")["args"]
    return read(Path(args[args.index("--stream-session")+1])/"capture.json")["reference"]
def stats(pts):
    return dict(E_mean_m=fmean(p[0] for p in pts),N_mean_m=fmean(p[1] for p in pts),
                U_mean_m=fmean(p[2] for p in pts),H_rms_m=math.sqrt(fmean(p[0]**2+p[1]**2 for p in pts)),
                U_rms_m=math.sqrt(fmean(p[2]**2 for p in pts)))
def metrics(points):
    keys=list(points)
    p=list(points.values())
    first=dict(zip(("first_q6_E_m","first_q6_N_m","first_q6_U_m"),p[0]))
    first["first_q6_H_m"]=math.hypot(*p[0][:2])
    for prefix,subset in (("first20",p[:20]),("first60",p[:60]),("all",p),
                          ("tail60",[points[k] for k in keys if epoch(keys[-1])-epoch(k)<60])):
        first[prefix+"_n"]=len(subset)
        first.update({prefix+"_"+k:v for k,v in stats(subset).items()})
    return first
def differences(record,base):
    record.update({"d_"+k:v-base[k] for k,v in list(record.items()) if k.endswith("_m") and k in base})
def trace_records(path):
    actions,closures={},{}
    with path.open("rb") as trace:
        for raw in trace:
            if b"$S12_ACTION," in raw:
                p=raw[raw.index(b"$S12_ACTION,"):].decode("ascii").strip().split(",")
                k=tuple(p[1:3])
                assert k not in actions and len(p)==17
                actions[k]=[int(p[3]),int(p[4]),int(p[5]),int(p[6]),float(p[7]),int(p[8]),
                            float(p[9]),float(p[10]),int(p[11]),float(p[12]),int(p[13]),int(p[14]),int(p[15]),int(p[16])]
            elif b"$S12_CLOSURE," in raw:
                p=raw[raw.index(b"$S12_CLOSURE,"):].decode("ascii").strip().split(",")
                k=tuple(p[1:3])
                assert k not in closures and p[3]=="1" and len(p)==7
                dv=list(map(float,p[4:]))
                assert all(math.isfinite(v) for v in dv)
                closures[k]=max(map(abs,dv)),math.hypot(*dv)
            elif b"$S12_INVALID_PROFILE" in raw:
                raise ValueError("profile violation")
    return actions,closures
COLS=("filter_q","accepted_trial_1based","code_rows","a1_inflated_rows","a1_max_factor",
      "a2_inflated_rows","a2_mean_factor_all_code","a2_max_factor","anneal_arcs","anneal_variance_m2",
      "a3_single_freq_ion_q_halved","fallback_code_rows","ungrouped_code_rows","cmc_boost_rows")
def verify_case(d,s,base,data,folder,action_rows):
    assert list(map(key,data))==list(map(key,base))
    hc={}
    for name in ("observations.csv","corrections.csv"):
        hc[name]=sha(folder/name)
        assert hc[name]==sha(baseline(d)/name)
    act,cl=trace_records(folder/"solution.trace")
    keys={key(r) for r in data}
    keys6={key(r) for r in data if r["Q"]=="6"}
    assert len(keys)==len(data) and set(cl)==keys6 and set(act)<=keys
    diffs=[]
    total=Counter()
    maxfo=maxfs=1
    retries=0
    for r,b in zip(data,base,strict=True):
        k=key(r)
        if r["Q"]!=b["Q"]:
            diffs.append(dict(week=k[0],tow=k[1],before=b["Q"],after=r["Q"]))
        committed=k in act
        values=act.get(k,[None,None,0,0,1.,0,1.,1.,0,0.,0,0,0,0])
        a=dict(zip(COLS,values,strict=True))
        if committed: assert a["filter_q"]==int(r["Q"])
        assert (k in cl)==(a["filter_q"]==6)
        assert 0<=a["a1_inflated_rows"]<=a["code_rows"] and 1<=a["a1_max_factor"]<=36
        assert 0<=a["a2_inflated_rows"]<=a["code_rows"] and 1<=a["a2_mean_factor_all_code"]<=a["a2_max_factor"]+1e-12 and a["a2_max_factor"]<=25
        if s not in (SCHEMES[0],SCHEMES[2]): assert not a["a1_inflated_rows"]
        if s not in (SCHEMES[1],SCHEMES[2]): assert not a["a2_inflated_rows"]
        if s not in SCHEMES[2:]: assert not a["anneal_arcs"] and not a["anneal_variance_m2"]
        if s!=SCHEMES[2]: assert not a["a3_single_freq_ion_q_halved"]
        total.update({k:a[k] for k in ("code_rows","a1_inflated_rows","a2_inflated_rows","anneal_arcs",
                                        "anneal_variance_m2","a3_single_freq_ion_q_halved","cmc_boost_rows")})
        maxfo=max(maxfo,a["a1_max_factor"]); maxfs=max(maxfs,a["a2_max_factor"])
        retries+=int(committed and a["accepted_trial_1based"]>1)
        action_rows.append(dict(dataset=d,scheme=s,week=k[0],tow=k[1],Q=r["Q"],committed=int(committed),
                                **a,closure_linf_m=cl[k][0] if k in cl else "",closure_l2_m=cl[k][1] if k in cl else ""))
    closure=max(v[0] for v in cl.values())
    euclidean=max(v[1] for v in cl.values())
    assert max(closure,euclidean)<1e-8
    return dict(dataset=d,scheme=s,epochs=len(keys),q_counts=dict(Counter(r["Q"] for r in data)),
                same_week_tow=True,q_changes=diffs,same_q_sequence=not diffs,hashes_match_baseline=hc,
                q6_closure_rows=len(cl),max_kv_closure_m=closure,max_kv_closure_l2_m=euclidean,
                committed=len(act),commits_after_retry=retries,**total,max_f_out=maxfo,max_f_stoch=maxfs)
def paired(series):
    result=[]
    for label,dx,dv in (("11:20",DATASETS[0],DATASETS[1]),("10:04",DATASETS[2],DATASETS[3])):
        for s in ALL:
            maps=[]
            for d in (dx,dv):
                q=series[d,s]
                m={(int(k[0]),round(float(k[1]))):(float(k[1]),p) for k,p in q.items()}
                assert len(m)==len(q)
                maps.append(m)
            keys=sorted(maps[0].keys() & maps[1].keys())
            skew=max(abs(maps[0][k][0]-maps[1][k][0]) for k in keys)
            r=dict(pair=label,scheme=s,common_q6=len(keys),max_pair_skew_s=skew)
            for prefix,m in zip(("xiaomi","vivo"),maps):
                r.update({prefix+"_"+k:v for k,v in stats([m[k][1] for k in keys]).items()})
            if s=="Baseline": base=r.copy()
            differences(r,base)
            result.append(r)
    return result
def main():
    series,summary,actions,cases,secondary={},[],[],[],[]
    oldrows={r["dataset"]:r for r in rows(OLD/"partB_accuracy_summary.csv") if r["scheme"]=="Baseline"}
    frame_path=OUT.parent/"brain_step12_reference_frame_audit/frame_offsets.csv"
    shifts={r["site"]:[float(r["delta_"+axis+"_m"]) for axis in "ENU"] for r in rows(frame_path)
            if r["scenario"]=="CGCS2000_2000" and r["velocity_model"]=="regional_S4_CCEA"}
    baseline_diff=0
    for d in DATASETS:
        reference=ref(d)
        base_rows=rows(baseline(d)/"solution.csv")
        shift=shifts["10-31" if d.startswith("1031") else "11-14"]
        for s in ALL:
            folder=baseline(d) if s=="Baseline" else OUT/"runs"/d/s
            data=base_rows if s=="Baseline" else rows(folder/"solution.csv")
            if s!="Baseline":
                cases.append(verify_case(d,s,base_rows,data,folder,actions))
            q={key(r):enu([float(r[k]) for k in ("x_m","y_m","z_m")],reference) for r in data if r["Q"]=="6"}
            series[d,s]=q
            m=metrics(q)
            approx=metrics({k:tuple(v-o for v,o in zip(p,shift)) for k,p in q.items()})
            if s=="Baseline":
                orig,orig2=m.copy(),approx.copy()
                baseline_diff=max(baseline_diff,max(abs(v-float(oldrows[d][k])) for k,v in m.items()))
            differences(m,orig); differences(approx,orig2)
            k=next(iter(q))
            meta=dict(dataset=d,scheme=s,week_first_q6=k[0],tow_first_q6=k[1],
                      first_q6_delay_s=epoch(k)-epoch(key(data[0])),epochs=len(data),q0=sum(r["Q"]=="0" for r in data),
                      q5=sum(r["Q"]=="5" for r in data),q6=len(q))
            summary.append(dict(**meta,**m))
            secondary.append(dict(**meta,**approx))
    assert baseline_diff<1e-10
    frame_baselines={(r["dataset"],r["window"]):r for r in rows(frame_path.with_name("reeval_accuracy.csv"))
                     if r["scenario"]=="CGCS2000_2000" and r["velocity_model"]=="regional_S4_CCEA"}
    sensitivity_diff=max(abs(r[w+"_"+k]-float(frame_baselines[r["dataset"],fw][k.replace("_rms_","_RMS_")]))
        for r in secondary if r["scheme"]=="Baseline"
        for w,fw in (("first20","first20"),("first60","first60"),("all","full"),("tail60","tail60"))
        for k in ("H_rms_m","U_rms_m","E_mean_m","N_mean_m","U_mean_m"))
    assert sensitivity_diff<6e-6
    write("partB_adaptive_action_stats.csv",actions)
    write("partB_accuracy_summary.csv",summary)
    write("partB_paired_common_q6.csv",paired(series))
    write("partB_candidate_frame_sensitivity.csv",secondary)
    verification=dict(new_replays=len(cases),reused_baselines=len(DATASETS),all_same_week_tow=True,
        all_same_observations=True,all_same_corrections=True,all_same_q_sequence=all(c["same_q_sequence"] for c in cases),
        max_kv_closure_m=max(c["max_kv_closure_m"] for c in cases),
        max_kv_closure_l2_m=max(c["max_kv_closure_l2_m"] for c in cases),baseline_summary_max_difference=baseline_diff,
        candidate_offsets_sha256=sha(frame_path),baseline_candidate_approximation_max_difference_m=sensitivity_diff,
        formal_binary_sha256=read(ROOT/"validation/build.json")["binaries"],
        extended_step11_sha256={f:sha(OLD/f) for f in ("input_guard_sha256.json","verification.json","REPORT.md","TERMINAL_TABLES.md")},
        private_guard_manifest_sha256=sha(OUT/"input_guard_sha256.json"),
        local_dependency_guard_sha256=sha(OUT/"local_dependency_guard.json"),
        before=read(OUT/"guard_before.json"),after=read(OUT/"guard_after.json"),
        cases=cases,sha256={f:sha(OUT/f) for f in ("step12_probe.exe","step12_private.patch","core/ppp.c","core/rtkcmn.c",
           "partB_accuracy_summary.csv","partB_adaptive_action_stats.csv","partB_paired_common_q6.csv","partB_candidate_frame_sensitivity.csv")})
    save(OUT/"verification.json",verification)
    print({k:v for k,v in verification.items() if k not in ("cases","sha256")})
if __name__=="__main__":
    main()
