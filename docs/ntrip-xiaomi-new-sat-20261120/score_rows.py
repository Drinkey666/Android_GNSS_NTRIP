"""Exact timestamp joins; reference and signed Up projection are evaluation-only."""
import collections
from decimal import Decimal
import csv
import math
import statistics
import sys
import json
from run import D,ROOT,V,SRC,PREV,ARMS,LABELS,B,read,sha,guards
sys.path.insert(0,str(ROOT/"tools"))
from evaluate_solution import enu,reference_ecef

def rows(p):
    with p.open(newline="",encoding="utf-8-sig") as f:return list(csv.DictReader(f))
def key(w,t):return int(w),Decimal(t)
def epoch(r):return key(r["week"],r["tow"])
def sec(k):return k[0]*604800+k[1]
def put(name,data):
    with (D/name).open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def equal(r,s):
    assert len(r)==len(s) and all(set(x)==set(y) and all(x[k]==y[k] for k in x if k!="processing_ms") for x,y in zip(r,s))
def projection(ref):
    lat,lon,_,vert=reference_ecef(ref);assert vert
    return (math.cos(lat)*math.cos(lon),math.cos(lat)*math.sin(lon),math.sin(lat))
def legacy(path,q6):
    with path.open(encoding="ascii",errors="replace") as f:
        for line in f:
            if "$S5_ROW," in line:
                w,t,it,c,sv,sig,slot,*z=line.partition("$S5_ROW,")[2].strip().split(",")
                if key(w,t) in q6:yield key(w,t),int(it),int(c),sv,sig,int(slot),tuple(map(float,z[:3]))
def scan(label,arm,ks,pos,up,raw0):
    epochs=set(pos);closed={};parts={};trials={};event=[];signals=[];primary_seen=set()
    contributions=collections.defaultdict(list)
    archive=legacy(V/"xiaomi_2221_2236_accuracy_origin_20261119"/label/"solution.trace",epochs) if arm=="original" else None
    with (D/(label+"_"+arm)/"solution.trace").open(encoding="ascii",errors="replace") as f:
        for line in f:
            if "$NEW_EVENT," in line:
                w,t,q,it,n,var,b,post,leak=line.partition("$NEW_EVENT,")[2].strip().split(",")
                k=key(w,t)
                assert int(q)==6 and 0<float(post)<float(var) and float(leak)<1e-10
                event.append(dict(session=label,week=int(w),tow=t,elapsed_s=float(sec(k)-raw0),trial=int(it),
                    new_satellites=int(n),sigma_before_m=math.sqrt(float(var)),estimated_offset_m=float(b),
                    sigma_after_m=math.sqrt(float(post)),clock_leak=float(leak)))
            elif "$S13_CLOSURE," in line:
                w,t,ready,*v=line.partition("$S13_CLOSURE,")[2].strip().split(",");k=key(w,t)
                assert k not in closed and ready=="1";closed[k]=math.hypot(*map(float,v))
            elif "$NEW_ROW," in line:
                w,t,it,idx,c,sv,sig,slot,hz,g,*v=line.partition("$NEW_ROW,")[2].strip().split(",")
                k=key(w,t);idx=int(idx);c=int(c);it=int(it);xyz=tuple(map(float,v))
                if archive is not None:
                    lk,li,lc,ls,lg,lf,lv=next(archive)
                    assert (lk,li,lc)==(k,it,c) and all(abs(a-b)<1e-12 for a,b in zip(lv,xyz))
                    if c in (1,2):assert (ls,lg,lf)==(sv,sig,int(slot))
                if k not in parts:parts[k]=[[],[],[],[],[]];trials[k]=it
                assert trials[k]==it and idx==sum(map(len,parts[k]))
                u=math.fsum(a*b for a,b in zip(up,xyz));parts[k][c].append(u)
                if float(g)!=0:
                    assert c==1 and event and epoch(event[-1])==k and sv not in primary_seen
                    signals.append(sv+"/"+sig)
                if c==1:
                    primary_seen.add(sv)
                    if k in ks:contributions[(sv,sig,int(slot),float(hz))].append((k,u))
    assert set(parts)==set(closed)==epochs and max(closed.values())<1e-8
    if archive is not None:assert next(archive,None) is None
    if arm=="new_sat":
        assert len(event)==1 and len(signals)==len(set(signals))==event[0]["new_satellites"]
        event[0]["signals"]=" ".join(signals)
    else:assert not event and not signals
    return parts,contributions,event,max(closed.values())

def main():
    assert guards()==read(D/"guards_local.json")
    windows=[];ranking=[];budgets=[];events=[];curve=[];families=[];early=[];checks={}
    for label in LABELS:
        path=SRC/label;official=rows(path/"SSR/solution.csv")
        capture=read(path/"imported/capture.json")["reference"];up=projection(capture)
        basekeys=[epoch(r) for r in official]
        assert len(set(basekeys))==len(basekeys) and basekeys==sorted(basekeys)
        times={a:rows(D/(label+"_"+a)/"solution.csv") for a in ARMS}
        pos={};qs={};checks[label]={}
        for a,rs in times.items():
            assert [epoch(r) for r in rs]==basekeys
            qs[a]={epoch(r):r["Q"] for r in rs}
            pos[a]={epoch(r):enu([float(r[j]) for j in ("x_m","y_m","z_m")],capture) for r in rs if r["Q"]=="6"}
            if a!="new_sat":equal(rs,official if a=="original" else rows(path/"B1_ema_only_v2/solution.csv"))
        shared=sorted(set.intersection(*(set(p) for p in pos.values())))
        t0,te=map(sec,(basekeys[0],basekeys[-1]));first=sec(min(pos["original"]));mid=(t0+te)/2
        mask=dict(first_q6=shared[:1],first60=[k for k in shared if first<=sec(k)<first+60],
                  second_half=[k for k in shared if sec(k)>=mid],tail60=[k for k in shared if sec(k)>te-60],all=shared)
        for a in ARMS:
            rs=times[a];run=D/(label+"_"+a)
            for f in ("observations.csv","corrections.csv"):assert sha(run/f)==sha(path/"SSR"/f)
            part,contrib,ev,close=scan(label,a,set(mask["second_half"]),pos[a],up,t0)
            checks[label][a]=dict(raw=len(rs),q6=len(pos[a]),first_Q6_elapsed_s=float(sec(min(pos[a]))-t0),
                q_sequence_changes=sum(qs[a][k]!=qs["original"][k] for k in basekeys),common_Q6=len(shared),
                max_kv_closure_m=close,observations_sha256=sha(run/"observations.csv"),
                corrections_sha256=sha(run/"corrections.csv"),solution_sha256=sha(run/"solution.csv"),
                archive_control_exact=a!="new_sat",legacy_row_Kv_matched=a=="original")
            if ev:
                e=ev[0];eventkey=epoch(e);pre=[i for i,k in enumerate(basekeys) if k<eventkey]
                equal([rs[i] for i in pre],[official[i] for i in pre])
                assert min(pos[a])<eventkey
                e.update(seconds_after_first_Q6=float(sec(eventkey)-first),verified_pre_event_epochs=len(pre))
                for b in ARMS:
                    e[b+"_U_m"]=pos[b][eventkey][2]
                    e[b+"_H_m"]=math.hypot(*pos[b][eventkey][:2])
                events.append(e)
            for win,keys in mask.items():
                p=[pos[a][k] for k in keys];H=math.sqrt(statistics.mean(e*e+n*n for e,n,u in p))
                U=math.sqrt(statistics.mean(u*u for e,n,u in p));mean=statistics.mean(u for e,n,u in p)
                windows.append(dict(session=label,arm=a,window=win,n=len(keys),H_RMS_m=H,U_RMS_m=U,
                    mean_U_m=mean,start_U_m=p[0][2],end_U_m=p[-1][2]))
            for i,k in enumerate(shared[:11]):
                sums=[math.fsum(us) for us in part[k]]
                change=pos[a][k][2]-pos[a][shared[i-1]][2] if i else None
                early.append(dict(session=label,arm=a,seconds_after_first_Q6=float(sec(k)-first),U_m=pos[a][k][2],
                    code_m=sums[1],phase_m=sums[2],ionex_m=sums[3],vmf3_m=sums[4],other_m=sums[0],
                    between_commits_m=change-math.fsum(sums) if i else None))
            if label=="2221":
                keys=mask["second_half"];code_total=0.
                grouped=collections.defaultdict(list)
                for (sv,sig,slot,hz),v in contrib.items():
                    us=[u for k,u in v];net=math.fsum(us);code_total+=net
                    grouped[(sv[0],sig,slot)].extend(us)
                    ranking.append(dict(arm=a,satellite=sv,signal=sig,slot=slot,frequency_MHz=hz/1e6,
                        rows=len(v),epochs=len(set(k for k,u in v)),up_rows=sum(u>0 for u in us),down_rows=sum(u<0 for u in us),
                        up_m=math.fsum(u for u in us if u>0),down_m=math.fsum(u for u in us if u<0),net_m=net))
                for (system,sig,slot),us in grouped.items():
                    families.append(dict(arm=a,system=system,signal=sig,slot=slot,rows=len(us),
                        up_m=math.fsum(x for x in us if x>0),down_m=math.fsum(x for x in us if x<0),net_m=math.fsum(us)))
                sums=[math.fsum(u for k in keys for u in part[k][c]) for c in range(5)]
                assert abs(sums[1]-code_total)<1e-10
                oldk=shared[shared.index(keys[0])-1]
                change=pos[a][keys[-1]][2]-pos[a][oldk][2]
                budgets.append(dict(arm=a,common_epochs=len(keys),from_U_m=pos[a][oldk][2],to_U_m=pos[a][keys[-1]][2],
                    observed_change_m=change,code_m=sums[1],phase_m=sums[2],ionex_m=sums[3],trop_m=sums[4],
                    other_rows_m=sums[0],between_commits_m=change-math.fsum(sums)))
        for k in shared:
            r=dict(session=label,week=k[0],tow=str(k[1]),elapsed_s=float(sec(k)-t0))
            for a in ARMS:
                e,n,u=pos[a][k];r[a+"_H_m"]=round(math.hypot(e,n),7);r[a+"_U_m"]=round(u,7)
            curve.append(r)
    W={(r["session"],r["window"],r["arm"]):r for r in windows}
    for r in windows:
        for b in ("original","ema"):
            for v in ("H_RMS_m","U_RMS_m"):r["delta_vs_"+b+"_"+v]=r[v]-W[r["session"],r["window"],b][v]
    put("accuracy.csv",windows);put("startup_events.csv",events);put("matched_epochs.csv",curve)
    put("second_half_signal.csv",sorted(ranking,key=lambda r:(ARMS.index(r["arm"]),r["net_m"])))
    put("second_half_frequency.csv",sorted(families,key=lambda r:(ARMS.index(r["arm"]),r["net_m"])))
    put("second_half_budget.csv",budgets);put("early_updates.csv",early)
    (D/"verification.json").write_text(json.dumps(dict(guard_count=len(guards()),guard_digest=sha(D/"guards_local.json"),
        binary_digest=sha(B/"replay.exe"),sessions=checks),indent=2)+"\n")
if __name__=="__main__":main()
