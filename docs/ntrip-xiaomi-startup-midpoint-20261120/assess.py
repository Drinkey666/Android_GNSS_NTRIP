"""Post-solution joins and accounting; no reference data is passed to either solver path."""
from ambiguity_ablation import *
from collections import defaultdict,Counter
from decimal import Decimal
import csv,statistics as st,math
TOTAL=ARMS+ARMS2+ARMS3+ARMS4+ARMS5+ARMS6+ARMS7+ARMS8
def write(name,data):
    with (D/name).open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
def mean(x):return st.mean(x)
def scan(run,up,q6,common,early,rebound,late,interest):
    at={};ctrl={};u_for={};code_u=defaultdict(float);tc=Counter();evt=[];lifts=[];weights=[];confirmed=Counter()
    cls=defaultdict(lambda:[0.]*5);byrow=defaultdict(lambda:defaultdict(float))
    pred={};row_key={};model={};max_row=max_model=0.;bound={};seen={};em={};native_counts={};shadow=[]
    for line in (run/"solution.trace").open(encoding="utf8",errors="replace"):
        if "$REASON," in line:
            w,t,tr,i,c,sv,sg,*v=line.partition("$REASON,")[2].strip().split(",");k=key(w,t);i=int(i);c=int(c);V,R,peer,pv,z,cond,prec,f,gx,gy,gz,pk,lf=map(float,v)
            ku=sum(x*y for x,y in zip(up,(gx,gy,gz)));assert 1<=f<=20.00000001 and k in q6
            row_key[k,i]=(int(tr),ku*V)
            if (k,i) in pred:
                m=pred.pop((k,i));assert (int(tr),sv,sg)==m[:3]
                terms=m[6:];close=abs((terms[0]-sum(terms[1:]))-V)
                max_model=max(max_model,close)
                if k==rebound:
                    model[sv,sg]=dict(v=V,ku=ku,contribution=ku*V,R=R*f,scalar_z=z,condition_m=cond,peer_median=pv,df=m[3],
                        chi2=m[4],block_z=m[5],terms=terms,factor=f)
            if f>1:
                assert c==1
                weights.append((k,sv,sg,f))
            if (k,i) in em:
                tr1,s1,g1,r0,r1=em.pop((k,i));assert (int(tr),sv,sg)==(tr1,s1,g1) and c==1 and f==1 and r1>r0>0
                weights.append((k,sv,sg,r1/r0))
                if k==rebound:model[sv,sg]['factor']=r1/r0
        elif "$MID_MODEL," in line:
            w,t,tr,i,sv,sg,b,T,z,*v=line.partition("$MID_MODEL,")[2].strip().split(",")
            k=key(w,t);pred[k,int(i)]=(int(tr),sv,sg,int(b),float(T),float(z),*map(float,v))
        elif "$MID_EMA," in line:
            w,t,tr,i,sv,sg,r0,r1=line.partition("$MID_EMA,")[2].strip().split(",")
            em[key(w,t),int(i)]=(int(tr),sv,sg,float(r0),float(r1))
        elif "$MID_V," in line:
            w,t,tr,n,ng,agree,restore=line.partition("$MID_V,")[2].strip().split(",")
            confirmed[(int(agree),int(restore))]+=1
        elif "$NEW_ROW," in line:
            w,t,tr,i,c,sv,sg,slot,hz,g,*v=line.partition("$NEW_ROW,")[2].strip().split(",");k=key(w,t);i=int(i);c=int(c);tr=int(tr)
            u=sum(x*float(y) for x,y in zip(up,v))
            assert seen.setdefault(k,tr)==tr
            if c in (1,2):
                trial,check=row_key.pop((k,i));assert tr==trial
                max_row=max(max_row,abs(u-check))
            if k in common:
                cls[k][c]+=u
                if interest:byrow[k][c,sv,sg]+=u
                if k in late and c==1:code_u[sv,sg]+=u
        elif "$S13_ACTION," in line:
            w,t,q,tr,n,na,fa,ne,*tail=line.partition("$S13_ACTION,")[2].strip().split(",")
            if q=="6":
                k=key(w,t);assert k not in native_counts
                native_counts[k]=int(ne)
        elif "$S13_CLOSURE," in line:
            w,t,ok,*v=line.partition("$S13_CLOSURE,")[2].strip().split(",");k=key(w,t)
            assert k not in bound and ok=="1";bound[k]=math.hypot(*map(float,v))
        elif "$WINDOW_EVENT," in line:
            w,t,q,tr,n=line.partition("$WINDOW_EVENT,")[2].strip().split(",")
            assert q=="6";shadow.append(key(w,t))
        elif "$NEW_EVENT," in line:
            w,t,q,tr,n,var,b,post,leak=line.partition("$NEW_EVENT,")[2].strip().split(",")
            evt.append((key(w,t),int(q),float(b),int(n)));assert int(q)==6
        elif "$REASON_LIFT," in line:lifts.append(int(line.strip().split(",")[-1]))
    assert not pred and not em and not row_key and set(bound)==set(seen)==q6
    assert max(bound.values())<1e-8 and max_row<1e-10 and max_model<2e-7,(max_model,max_row)
    return dict(bound=max(bound.values()),row_error=max_row,model_error=max_model,model=model,cls=cls,byrow=byrow,code=code_u,events=evt,
                weights=weights,lifts=lifts,shadow=shadow,native_counts=native_counts,agree=confirmed[(1,0)],restore=confirmed[(0,1)])
def compute(arms=TOTAL):
    assert guards()==read(D/"guards_local.json")
    M=[];T=[];A=[];budget=[];diag=[];growth=[];contributors=[];onsets=[];verification={};signals=[];weighted=[]
    for l in LABELS:
        ref=read(SRC/l/"imported/capture.json")["reference"];up=projection(ref);official=rows(SRC/l/"SSR/solution.csv")
        keys=[epoch(r) for r in official];assert keys==sorted(set(keys))
        raw0,end=map(sec,(keys[0],keys[-1]));mid=(raw0+end)/2
        sol={a:rows(D/(l+"_"+a)/"solution.csv") for a in arms}
        pos={a:{epoch(r):enu([float(r[c]) for c in ("x_m","y_m","z_m")],ref) for r in rs if r["Q"]=="6"} for a,rs in sol.items()}
        common=sorted(set.intersection(*(set(p) for p in pos.values())));start=sec(min(pos["original"]))
        event=epoch(next(r for r in rows(parent.P/"startup_events.csv") if r["session"]==l))
        rebound=common[common.index(event)+1];assert abs(sec(rebound)-sec(event)-1)<Decimal(".01")
        wins=dict(first60=[k for k in common if start<=sec(k)<start+60],late=[k for k in common if sec(k)>=mid],tail60=[k for k in common if sec(k)>end-60],all=common)
        S={};verification[l]={}
        for a in arms:
            p=D/(l+"_"+a);rs=sol[a];assert [epoch(r) for r in rs]==keys
            for n in ("observations.csv","corrections.csv"):assert sha(p/n)==sha(SRC/l/"SSR"/n)
            if a in ARMS[:4]:equal(rs,rows(P/(l+"_"+a)/"solution.csv"))
            s=scan(p,up,set(pos[a]),set(common),set(wins['first60']),rebound,set(wins['late']),l=="2221" and a in ("selective","original"));S[a]=s
            branch=a.startswith("carry")
            assert len(s['events'])==int(branch or a=="new_sat_window") and len(s['lifts'])==int(branch)
            if branch:
                assert s["events"][0][0]==event
                equal(rs[:keys.index(event)+1] if a!="carry" else rs[:keys.index(event)],
                      (sol["carry"][:keys.index(event)+1] if a!="carry" else official[:keys.index(event)]))
            assert s['shadow']==([event] if a=="window_ema" else [])
            if a=="window_ema":
                equal(rs[:keys.index(event)+1],official[:keys.index(event)+1])
                stop=next(i for i,k in enumerate(keys) if sec(k)>=start+60)
                equal(rs[:stop],sol["ema"][:stop])
            if a=="new_sat_window":
                assert s['events'][0][0]==event
                equal(rs[:keys.index(event)+1],rows(parent.P/(l+"_new_sat")/"solution.csv")[:keys.index(event)+1])
            if a in ("carry_ema","carry_block","window_ema","carry_floor","new_sat_window"):
                assert all(sec(event)<sec(k)<start+60 for k,sv,sg,f in s["weights"])
            verification[l][a]=dict(raw=len(keys),q6=len(pos[a]),common=len(common),changed_Q=sum(r["Q"]!=o["Q"] for r,o in zip(rs,official)),
                first_q6_s=float(sec(min(pos[a]))-raw0),max_closure_m=s["bound"],max_row_Kv_error_m=s["row_error"],max_model_closure_m=s["model_error"],
                observation_and_correction_hash_match=True,archive_control_14_fields=a in ARMS[:4],restored_vertical_epochs=s["restore"],consensus_epochs=s["agree"],
                synchronized_arcs=s["lifts"],matched_sham_events=len(s["shadow"]),
                sham_matches_full_ema_through_window=True if a=="window_ema" else None,solution_sha256=sha(p/"solution.csv"))
            for w,ks in wins.items():
                vals=[pos[a][k] for k in ks]
                M.append(dict(session=l,arm=a,window=w,n=len(ks),H_RMS_m=math.sqrt(mean(e*e+n*n for e,n,u in vals)),
                     U_RMS_m=math.sqrt(mean(u*u for e,n,u in vals)),U_mean_m=mean(u for e,n,u in vals),first_U_m=vals[0][2],last_U_m=vals[-1][2]))
            for w,ks in [('rebound',[rebound]),('late',wins['late'])]:
                sums=[math.fsum(s["cls"][k][c] for k in ks) for c in range(5)];prior=common[common.index(ks[0])-1]
                du=pos[a][ks[-1]][2]-pos[a][prior][2]
                budget.append(dict(session=l,arm=a,window=w,change_m=du,code_m=sums[1],phase_m=sums[2],ionex_m=sums[3],trop_m=sums[4],other_rows_m=sums[0],other_between_m=du-sum(sums)))
            late=set(wins["late"]);early=set(wins["first60"])
            counts=Counter((sv,sg) for k,sv,sg,f in s["weights"] if k in late)
            for (sv,sg),net in sorted(s["code"].items()):
                signals.append(dict(session=l,arm=a,satellite=sv,signal=sg,late_net_code_U_m=net,
                    late_extra_weight_rows=counts[sv,sg] if a!="ema" else ""))
            if a in ("carry_ema","soft_floor","memory_floor","window_ema","carry_floor","new_sat_window"):
                weighted.extend(dict(session=l,arm=a,elapsed_raw_s=float(sec(k)-raw0),satellite=sv,signal=sg,
                    effective_variance_ratio=f) for k,sv,sg,f in s["weights"])
            for w,ks in [('first60',early),('late',late),('all',set(common)),('rebound',{rebound})]:
                weights=[(k,sv,sg,f) for k,sv,sg,f in s["weights"] if k in ks]
                native=a=="ema"
                if native:assert set(s["native_counts"])==set(pos[a])
                A.append(dict(session=l,arm=a,window=w,additional_code_rows=sum(s["native_counts"][k] for k in ks) if native else len(weights),
                    affected_epochs=sum(s["native_counts"][k]>0 for k in ks) if native else len(set(z[0] for z in weights)),
                    C33_B1I_actions='' if native else sum(sv=="C33" and sg=="2I" for k,sv,sg,f in weights),C33_late_net_m=s['code'].get(('C33','2I'),0) if w=="late" else '',
                    E27_actions='' if native else sum(sv=="E27" for k,sv,sg,f in weights),E15_actions='' if native else sum(sv=="E15" for k,sv,sg,f in weights)))
            for k in common:
                if k in early or l=="2221":
                    T.append(dict(session=l,arm=a,elapsed_raw_s=float(sec(k)-raw0),elapsed_first_Q6_s=float(sec(k)-start),
                        H_m=math.hypot(*pos[a][k][:2]),U_m=pos[a][k][2],signed_U_delta_original_m=pos[a][k][2]-pos["original"][k][2]))
        if l=="2236":
            for arm in arms:
                for (sv,sg),m in S[arm]["model"].items():
                    b=S["original"]["model"].get((sv,sg))
                    if not b:continue
                    terms=[(x-y)*sign for x,y,sign in zip(m["terms"],b["terms"],(1,-1,-1,-1,-1,-1,-1))]
                    dv=m["v"]-b["v"];dku=m["ku"]-b["ku"];respart=dv*(m["ku"]+b["ku"])*.5;gainpart=dku*(m["v"]+b["v"])*.5
                    assert abs(sum(terms)-dv)<2e-7 and abs(respart+gainpart-(m["contribution"]-b["contribution"]))<1e-9
                    diag.append(dict(arm=arm,satellite=sv,signal=sg,v_m=m["v"],R_m2=m["R"],Ku=m["ku"],U_contribution_m=m["contribution"],scalar_z=m["scalar_z"],same_sat_dof=m["df"],same_sat_chi2=m["chi2"],block_z=m["block_z"],additional_factor=m["factor"] if arm!="ema" else "",
                        delta_v_m=dv,measurement_term_m=terms[0],geometry_term_m=terms[1],receiver_clock_term_m=terms[2],
                        sat_clock_term_m=terms[3],trop_term_m=terms[4],ion_term_m=terms[5],bias_term_m=terms[6],
                        change_from_gain_m=gainpart,change_from_innovation_m=respart))
        if l=="2221":
            orig,sel=S["original"],S["selective"]
            diff={k:pos["selective"][k][2]-pos["original"][k][2] for k in common}
            middle=wins["late"][0];pre=[k for k in common if k<=middle];peak=max(pre,key=diff.get)
            def first_after(thresh,after):
                return next(k for k in pre if k>after and diff[k]<=thresh)
            sustain=pre[1+max(i for i,k in enumerate(pre) if diff[k]>=0.)]
            for name,k in [('first_weight',min(x[0] for x in sel['weights'])),('first_lower_1cm',first_after(-.01,pre[0])),
                        ('first_lower_10cm',first_after(-.1,pre[0])),('early_trough',min(pre[:pre.index(peak)],key=diff.get)),
                        ('positive_peak',peak),('sustained_negative_until_midpoint',sustain),('persistent_cross_5cm',first_after(-.05,sustain)),
                        ('persistent_cross_10cm',first_after(-.1,sustain)),('first_second_half_Q6',middle)]:
                onsets.append(dict(mark=name,elapsed_raw_s=float(sec(k)-raw0),elapsed_first_Q6_s=float(sec(k)-start),signed_U_delta_m=diff[k]))
            def interval(name,startk,endk):
                ks=[k for k in pre if startk<k<=endk];cd=[math.fsum(sel["cls"][k][i]-orig["cls"][k][i] for k in ks) for i in range(5)]
                actual=diff[endk]-diff[startk];growth.append(dict(interval=name,from_raw_s=float(sec(startk)-raw0),to_raw_s=float(sec(endk)-raw0),n=len(ks),
                    start_delta_m=diff[startk],end_delta_m=diff[endk],change_m=actual,code_m=cd[1],phase_m=cd[2],ionex_m=cd[3],trop_m=cd[4],other_m=actual-sum(cd)))
                rr=defaultdict(float)
                for a,sign in ((sel,1),(orig,-1)):
                    for k in ks:
                        for (c,sv,sg),u in a["byrow"][k].items():
                            if c==1:rr[sv,sg]+=sign*u
                for (sv,sg),u in sorted(rr.items(),key=lambda p:p[1]):contributors.append(dict(interval=name,satellite=sv,signal=sg,delta_code_U_m=u))
            k10=first_after(-.1,sustain)
            for name,x,y in [('peak_to_mid',peak,middle),('peak_to_zero',peak,sustain),('zero_to_minus10cm',sustain,k10),('minus10cm_to_mid',k10,middle)]:interval(name,x,y)
    by={(r["session"],r["arm"],r["window"]):r for r in M}
    for r in M:
        for a in ("original","ema","selective","carry"):
            for f in ("H_RMS_m","U_RMS_m"):r["delta_"+a+"_"+f]=r[f]-by[r["session"],a,r["window"]][f]
    for n,r in (("accuracy.csv",M),("matched_errors.csv",T),("actions.csv",A),("rebound_model.csv",diag),("vertical_budget.csv",budget),
                ("midpoint_onset.csv",onsets),("midpoint_intervals.csv",growth),("midpoint_signals.csv",contributors),
                ("late_code_signals.csv",signals),("weighted_codes.csv",weighted)):write(n,r)
    (D/"verification.json").write_text(json.dumps(dict(guards=len(guards()),guard_digest=sha(D/"guards_local.json"),
        experiment_binaries={p.name:sha(p/"replay.exe") for p in (B,B2,B3,B4,B5,B6,B7,B8)},sessions=verification),indent=2)+"\n")
if __name__=="__main__":compute()
