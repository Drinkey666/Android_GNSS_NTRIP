"""Evaluate only after replay. Export relative horizontal/vertical errors on shared Q6."""
import csv
import math
import statistics
import sys
from decimal import Decimal
from experiment import HERE,ROOT,SOURCE,LABELS,ARMS,read,digest,guard
import json
sys.path.insert(0,str(ROOT/"tools"))
from evaluate_solution import enu

def rows(path):
    with path.open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def key(w,t):return (int(w),Decimal(t))
def epoch(r):return key(r["week"],r["tow"])
def seconds(k):return k[0]*604800+k[1]
def writecsv(name,table):
    with (HERE/name).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
def same_solution(a,b):
    assert len(a)==len(b)
    fields=set(a[0])-{"processing_ms"}
    assert set(a[0])==set(b[0])
    for i,(r,s) in enumerate(zip(a,b)):
        for f in fields:assert r[f]==s[f],(i,f)
    return len(fields)
def trace(path):
    closure={};acts={};sigma={};seed=[];confirm=[]
    with path.open(encoding="utf-8",errors="replace") as f:
        for line in f:
            if "$S13_CLOSURE," in line:
                w,t,ready,*d=line.partition("$S13_CLOSURE,")[2].strip().split(",")
                k=key(w,t); assert ready=="1" and k not in closure
                closure[k]=math.hypot(*map(float,d))
            elif "$FIELD_COMMIT," in line:
                w,t,*a=line.partition("$FIELD_COMMIT,")[2].strip().split(",")
                k=key(w,t);assert k not in acts;acts[k]=list(map(float,a))
            elif "$FIELD_SIGMA," in line:
                w,t,p,q=line.partition("$FIELD_SIGMA,")[2].strip().split(",")
                k=key(w,t);assert k not in sigma;sigma[k]=[float(p),float(q)]
            elif "$FIELD_SEED," in line:
                seed.append(list(map(float,line.partition("$FIELD_SEED,")[2].strip().split(","))))
            elif "$FIELD_CONFIRM," in line:
                confirm.append(list(map(float,line.partition("$FIELD_CONFIRM,")[2].strip().split(","))))
    return closure,acts,sigma,seed,confirm

def main():
    allmetrics=[];actions=[];curves=[];sigmas=[];checks={}
    before=read(HERE/"guards_local.json")
    assert guard()==before
    for label in LABELS:
        src=SOURCE/label
        formal=rows(src/"SSR/solution.csv");timestamps=[epoch(r) for r in formal]
        assert len(timestamps)==len(set(timestamps)) and timestamps==sorted(timestamps)
        ref=read(src/"imported/capture.json")["reference"]
        dirs={a:HERE/(label+"_"+a) for a in ARMS}
        pos={};events={};sdata={}; audits={}
        raw0,end=map(seconds,(timestamps[0],timestamps[-1]))
        for a,d in dirs.items():
            r=rows(d/"solution.csv");assert [epoch(i) for i in r]==timestamps
            pos[a]={epoch(i):enu([float(i[j]) for j in ("x_m","y_m","z_m")],ref) for i in r if i["Q"]=="6"}
            closure,events[a],_,seed,confirm=trace(d/"solution.trace")
            assert set(closure)==set(events[a])==set(pos[a])
            assert max(closure.values())<1e-8
            for f in ("observations.csv","corrections.csv"):
                assert digest(d/f)==digest(src/"SSR"/f)
            first=min(pos[a]);qdiff=sum(i["Q"]!=j["Q"] for i,j in zip(formal,r))
            audit=dict(raw_epochs=len(r),q6=len(pos[a]),q_sequence_differences=qdiff,
                first_q6_elapsed_s=float(seconds(first)-raw0),max_commit_closure_m=max(closure.values()),
                source_dumps_sha256_equal=True,solution_sha256=digest(d/"solution.csv"),
                q_counts={q:sum(i["Q"]==q for i in r) for q in sorted(set(i["Q"] for i in r))})
            if a in ("original","ema"):
                other="SSR" if a=="original" else "B1_ema_only_v2"
                audit["archive_fields_exact_excluding_processing_ms"]=same_solution(r,rows(src/other/"solution.csv"))
            if a in ("original","seed"):
                other=HERE/("sigma_"+label+"_"+a)
                same_solution(r,rows(other/"solution.csv"))
                for f in ("observations.csv","corrections.csv"):assert digest(other/f)==digest(d/f)
                sc,sa,sdata[a],_,_=trace(other/"solution.trace")
                assert set(sc)==set(sdata[a])==set(pos[a]) and sc==closure and sa==events[a]
                audit["independent_sigma_diagnostic_exact"]=True
                if a=="seed":
                    assert len(seed)==len(confirm)==1
                    prior=read(HERE.parent/"xiaomi_2221_2236_accuracy_origin_20261119/startup.json")[label]
                    assert abs(seed[0][1]-max(map(abs,prior["omission_vertical_shift_fixed_linearization_m"].values())))<0.001
                    audit.update(max_spp_omission_up_m=seed[0][1],confirmation_median_up_m=confirm[0][1],confirmation_range_m=confirm[0][2])
            audits[a]=audit
        common=sorted(set.intersection(*(set(v) for v in pos.values())))
        first=seconds(min(pos["original"]))
        windows={"first_q6":common[:1],"first60":[k for k in common if first<=seconds(k)<first+60],
                 "second_half":[k for k in common if seconds(k)>=(raw0+end)/2],
                 "tail60":[k for k in common if seconds(k)>end-60],"all":common}
        for k in common:
            row=dict(session=label,week=k[0],tow=str(k[1]),elapsed_s=float(seconds(k)-raw0))
            for a in ARMS:
                e,n,u=pos[a][k];row[a+"_H_m"]=round(math.hypot(e,n),6);row[a+"_U_m"]=round(u,6)
            curves.append(row)
        for win,ks in windows.items():
            metrics={}
            for a in ARMS:
                p=[pos[a][k] for k in ks]
                hm=math.sqrt(statistics.mean(e*e+n*n for e,n,u in p))
                um=math.sqrt(statistics.mean(u*u for e,n,u in p))
                metrics[a]={"H_RMS_m":hm,"U_RMS_m":um,"U_mean_m":statistics.mean(u for e,n,u in p),
                    "first_U_m":p[0][2],"last_U_m":p[-1][2]}
            for a in ARMS:
                m=dict(session=label,window=win,arm=a,n=len(ks),**metrics[a])
                for b in ("original","ema"):
                    for field in ("H_RMS_m","U_RMS_m"):m["delta_vs_"+b+"_"+field]=metrics[a][field]-metrics[b][field]
                allmetrics.append(m)
            for a in ("seed","drift"):
                v=[events[a][k] for k in ks]
                actions.append(dict(session=label,window=win,arm=a,n=len(ks),
                    startup_variance_events=sum(x[0]>0 for x in v),mature_satellite_epochs=int(sum(x[2] for x in v)),
                    mature_epochs=sum(x[2]>0 for x in v),code_rows=int(sum(x[3] for x in v)),
                    ionex_rows=int(sum(x[4] for x in v)),code_epochs=sum(x[3]>0 for x in v),
                    ionex_epochs=sum(x[4]>0 for x in v),max_code_R_factor=max(x[5] for x in v),max_ionex_R_factor=max(x[6] for x in v)))
        for k in common:
            stage,add,*_=events["seed"][k]
            if stage:
                for a in ("original","seed"):
                    sigmas.append(dict(session=label,stage=int(stage),elapsed_s=float(seconds(k)-raw0),arm=a,
                        added_Up_variance_m2=add if a=="seed" else 0,
                        prior_sigma_U_m=sdata[a][k][0],posterior_sigma_U_m=sdata[a][k][1],signed_U_m=pos[a][k][2]))
        checks[label]=dict(shared_Q6=len(common),arms=audits,observations_sha256=digest(src/"SSR/observations.csv"),corrections_sha256=digest(src/"SSR/corrections.csv"),guarded_inputs=len(read(src/"SSR/replay.json")["input_sha256"]))
    writecsv("matched_windows.csv",allmetrics);writecsv("action_windows.csv",actions)
    writecsv("common_epoch_errors.csv",curves);writecsv("startup_confidence.csv",sigmas)
    (HERE/"verification.json").write_text(json.dumps(dict(formal_binaries=9,pre_post_guard_count=len(before),guard_match=True,guard_manifest_sha256=digest(HERE/"guards_local.json"),
        shared_input_mode="Arrival-prefix realtime SSR, no file substitution",sessions=checks,
        build_sha256=digest(HERE/"private/replay.exe"),sigma_probe_sha256=digest(HERE/"sigma_build/replay.exe")),indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":main()
