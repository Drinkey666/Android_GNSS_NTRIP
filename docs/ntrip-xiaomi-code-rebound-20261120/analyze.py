"""After-solution row attribution, conditional innovation and paired gain/residual decomposition."""
from probe import D,P,SRC,ROOT,ARMS,LABELS,guards,read,sha,B
from score_rows import rows,equal,epoch,sec,key,projection
from evaluate_solution import enu
import csv,json,math,statistics as st
from collections import defaultdict,Counter
from decimal import Decimal
def write(name,rs):
    with (D/name).open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]));w.writeheader();w.writerows(rs)
def parse(run,q6,common,late,up,special,base):
    touched=Counter();actions=[];effects={};focus=defaultdict(dict);reb={};net=defaultdict(float)
    classes=defaultdict(lambda:[0.]*5);events=[];lift=[];closures={};known={};rmap={}
    rowmax=0.;count=0
    with (run/"solution.trace").open(encoding="utf8",errors="replace") as stream:
        for line in stream:
            if "$REASON," in line:
                w,t,tr,i,c,sv,sig,*vs=line.partition("$REASON,")[2].strip().split(",")
                k=key(w,t);c=int(c);idx=int(i);tr=int(tr)
                v,R,peer,pv,z,cond,prec,f,gx,gy,gz,pk,l=map(float,vs)
                ku=math.fsum(x*y for x,y in zip(up,(gx,gy,gz)))
                ku_v=ku*v
                assert k in q6 and R>0 and 1<=f<=4 and abs(cond*math.sqrt(prec)-z)<1e-9
                if k not in rmap:rmap[k]={}
                assert idx not in rmap[k];rmap[k][idx]=(tr,ku_v)
                if k not in common:continue
                if f>1:
                    assert c==1 and R<=peer
                    touched[k]+=1
                    actions.append(dict(week=w,tow=t,satellite=sv,signal=sig,factor=f))
                if k in late and c==1:
                    if math.isfinite(pk) and pk>0 and math.isfinite(peer) and math.isfinite(pv):
                        # Exact 4R rank-one counterfactual at the frozen prior for an unmodified arm.
                        extra=3*R;four=-ku*extra/(1+extra*prec)*cond*prec
                        focus[(sv,sig)][k]=dict(v=v,k=ku,kuv=ku_v,cond=cond,z=z,R=R,effective_R=R*f,peer=peer,pv=pv,peer_k=pk,
                            gain_ratio=abs(ku)/pk,f=f,four=four,precision=prec)
                    net[sv,sig]+=ku_v
                if k==special:
                    rk=c,sv,sig
                    assert rk not in reb;reb[rk]=dict(U=ku_v,v=v,k=ku,r=R*f)
            elif "$NEW_ROW," in line:
                w,t,tr,i,c,sv,sig,slot,hz,g,*xyz=line.partition("$NEW_ROW,")[2].strip().split(",")
                k=key(w,t);i=int(i);c=int(c);tr=int(tr);u=math.fsum(a*float(b) for a,b in zip(up,xyz))
                assert known.setdefault(k,tr)==tr
                if c in (1,2):
                    it,v=rmap[k].pop(i);assert it==tr;rowmax=max(rowmax,abs(v-u));count+=1
                if k in common and (k in late or k==special):classes[k][c]+=u
            elif "$S13_CLOSURE," in line:
                w,t,b,*v=line.partition("$S13_CLOSURE,")[2].strip().split(",")
                k=key(w,t);assert b=="1" and k not in closures;closures[k]=math.hypot(*map(float,v))
            elif "$NEW_EVENT," in line:
                w,t,q,it,n,var,b,post,leak=line.partition("$NEW_EVENT,")[2].strip().split(",")
                assert q=="6";events.append(dict(week=w,tow=t,trial=int(it),n=int(n),shift=float(b)))
            elif "$REASON_LIFT," in line:
                w,t,tr,n=line.partition("$REASON_LIFT,")[2].strip().split(",");lift.append(int(n))
    assert set(q6)==set(closures)==set(known) and not any(rmap.values()) and max(closures.values())<1e-8 and rowmax<1e-10
    return focus,reb,net,classes,events,lift,actions,dict(max_closure_m=max(closures.values()),max_row_Kv_difference_m=rowmax,paired_real_rows=count)
def main():
    assert guards()==read(D/"guards_local.json")
    metrics=[];diagnostics=[];effects=[];rd=[];actions=[];timeline=[];budgets=[];qstats={};factor_summary=[];blocks=[]
    for label in LABELS:
        src=SRC/label;reference=read(src/"imported/capture.json")["reference"];up=projection(reference)
        official=rows(src/"SSR/solution.csv");keys=[epoch(r) for r in official]
        assert keys==sorted(set(keys))
        t0,te=sec(keys[0]),sec(keys[-1])
        ps={};data={};qstats[label]={}
        for a in ARMS:
            p=D/(label+"_"+a);rs=rows(p/"solution.csv");assert [epoch(r) for r in rs]==keys
            if a in ("original","ema","new_sat"):equal(rs,rows(P/(label+"_"+a)/"solution.csv"))
            for n in ("observations.csv","corrections.csv"):assert sha(p/n)==sha(src/"SSR"/n)
            ps[a]={epoch(r):enu([float(r[j]) for j in ("x_m","y_m","z_m")],reference) for r in rs if r["Q"]=="6"}
            data[a]=rs
        keys6=sorted(set.intersection(*(set(m) for m in ps.values())));start=sec(min(ps["original"]))
        windows=dict(first_q6=keys6[:1],first60=[k for k in keys6 if start<=sec(k)<start+60],late=[k for k in keys6 if sec(k)>=(t0+te)/2],
                     tail60=[k for k in keys6 if sec(k)>te-60],all=keys6)
        ev=next(r for r in rows(P/"startup_events.csv") if r["session"]==label)
        event=key(ev["week"],ev["tow"]);j=keys6.index(event);nextkey=keys6[j+1];assert abs(sec(nextkey)-sec(event)-1)<Decimal("0.01")
        focusall={};rball={};late=set(windows["late"])
        for a in ARMS:
            focus,rb,net,classes,events,lifts,act,stats=parse(D/(label+"_"+a),set(ps[a]),set(keys6),late,up,nextkey,t0)
            if a in ("carry","new_sat"):
                assert len(events)==1 and epoch(events[0])==event
                prefix=keys.index(event);equal(data[a][:prefix],official[:prefix])
            else:assert not events
            if a=="carry":assert len(lifts)==1 and lifts[0]>0
            if a!="selective":assert not act
            qstats[label][a]=dict(**stats,raw=len(keys),q6=len(ps[a]),common_q6=len(keys6),
                changed_Q=sum(x["Q"]!=y["Q"] for x,y in zip(data[a],official)),
                first_q6_after_s=float(sec(min(ps[a]))-t0),events=events,lifts=lifts,
                archived_control_match=a in ("original","ema","new_sat"),obs_corrections_match=True)
            focusall[a]=focus;rball[a]=rb
            for win,ks in windows.items():
                p=[ps[a][k] for k in ks]
                metrics.append(dict(session=label,arm=a,window=win,n=len(p),
                    H_RMS_m=math.sqrt(st.mean(e*e+n*n for e,n,u in p)),U_RMS_m=math.sqrt(st.mean(u*u for e,n,u in p)),
                    U_mean_m=st.mean(u for e,n,u in p),U_start_m=p[0][2],U_end_m=p[-1][2]))
            for k in keys6:
                if sec(k)>=start+60:break
                timeline.append(dict(session=label,arm=a,elapsed_from_first_Q6_s=float(sec(k)-start),up_m=ps[a][k][2],H_m=math.hypot(*ps[a][k][:2])))
            counts=Counter((x["satellite"],x["signal"]) for x in act if epoch(x) in late)
            factor_summary.append(dict(session=label,arm=a,all_affected_rows=len(act),late_affected_rows=sum(counts.values()),
                late_affected_epochs=len({epoch(x) for x in act if epoch(x) in late}),late_C13=counts["C13","2I"],late_G06=counts["G06","1C"],late_C33=counts["C33","2I"]))
            actions.extend(dict(session=label,**x) for x in act)
            for win,ks in (("rebound",[nextkey]),("late",windows["late"])):
                sums=[math.fsum(classes[k][i] for k in ks) for i in range(5)]
                oldkey=keys6[keys6.index(ks[0])-1];du=ps[a][ks[-1]][2]-ps[a][oldkey][2]
                budgets.append(dict(session=label,arm=a,window=win,n=len(ks),U_change_m=du,code_m=sums[1],phase_m=sums[2],
                    ionex_m=sums[3],vmf3_m=sums[4],other_m=sums[0],between_commits_m=du-sum(sums)))
            if label=="2221":
                for (sv,sig),vv in focus.items():
                    rs=list(vv.values())
                    av=lambda c:st.mean(r[c] for r in rs)
                    md=lambda c:st.median(r[c] for r in rs)
                    if (sv,sig) in (("C13","2I"),("G06","1C"),("C33","2I")):
                        mid=(t0+te)/2
                        for block in range(4):
                            sel=[r for t,r in vv.items() if min(3,int(4*(sec(t)-mid)/(te-mid)))==block]
                            if sel:blocks.append(dict(arm=a,satellite=sv,signal=sig,quarter=block+1,n=len(sel),
                                conditional_median_m=st.median(r["cond"] for r in sel),signed_z_median=st.median(r["z"] for r in sel),
                                signed_Ku_median=st.median(r["k"] for r in sel),net_U_m=math.fsum(r["kuv"] for r in sel)))
                    diagnostics.append(dict(arm=a,satellite=sv,signal=sig,n=len(rs),net_all_rows_m=net[sv,sig],v_mean_m=av("v"),v_median_m=md("v"),
                        loo_z_rms=math.sqrt(st.mean(r["z"]**2 for r in rs)),loo_z_sd=st.pstdev(r["z"] for r in rs),
                        centered_v_median_m=st.median(r["v"]-r["pv"] for r in rs),loo_median_m=md("cond"),loo_z_median=md("z"),
                        loo_positive_fraction=st.mean(r["z"]>0 for r in rs),loo_abs_z_gt2=sum(abs(r["z"])>2 for r in rs),
                        R_median_m2=md("R"),effective_R_median_m2=md("effective_R"),peer_R_median_m2=md("peer"),R_peer_ratio=st.median(r["R"]/r["peer"] for r in rs),
                        Ku_median=md("k"),abs_Ku_peer_ratio=md("gain_ratio"),affected_rows=counts[sv,sig],
                        fixed_prior_4R_sum_delta_m=math.fsum(r["four"] for r in rs) if a in ("original","ema") else ""))
        if label=="2221":
            for a in ("ema","selective"):
                for sg in focusall["original"]:
                    x=focusall["original"][sg];y=focusall[a].get(sg,{})
                    overlap=x.keys()&y.keys()
                    if not overlap:continue
                    gain=math.fsum((y[k]["k"]-x[k]["k"])*(y[k]["v"]+x[k]["v"])/2 for k in overlap)
                    res=math.fsum((y[k]["v"]-x[k]["v"])*(y[k]["k"]+x[k]["k"])/2 for k in overlap)
                    unmatched=sum(y[k]["kuv"] for k in y.keys()-x.keys())-sum(x[k]["kuv"] for k in x.keys()-y.keys())
                    delta=sum(r["kuv"] for r in y.values())-sum(r["kuv"] for r in x.values())
                    assert abs(gain+res+unmatched-delta)<1e-10
                    effects.append(dict(arm=a,satellite=sg[0],signal=sg[1],common_rows=len(overlap),gain_term_m=gain,innovation_term_m=res,
                        unmatched_m=unmatched,total_delta_m=delta))
        if label=="2236":
            for sig in sorted(set.union(*(set(s) for s in rball.values()))):
                r=dict(kind="code" if sig[0]==1 else "phase",satellite=sig[1],signal=sig[2])
                for a in ARMS:
                    data_row=rball[a].get(sig,{})
                    for c in ("U","v","k","r"):r[a+"_"+c]=data_row.get(c,"")
                for a,b in (("new_sat","original"),("carry","original"),("carry","new_sat"),("ema","original")):
                    r[a+"_minus_"+b]=(r[a+"_U"] or 0)-(r[b+"_U"] or 0)
                rd.append(r)
    by={(m["session"],m["arm"],m["window"]):m for m in metrics}
    for m in metrics:
        for b in ("original","ema","new_sat"):
            for f in ("H_RMS_m","U_RMS_m"):m["delta_"+b+"_"+f]=m[f]-by[m["session"],b,m["window"]][f]
    for name,r in (("accuracy.csv",metrics),("target_diagnostics.csv",diagnostics),("gain_vs_innovation.csv",effects),("rebound_rows.csv",rd),
                   ("actions.csv",actions),("action_summary.csv",factor_summary),("startup_epochs.csv",timeline),("vertical_budget.csv",budgets),("target_quarters.csv",blocks)):
        write(name,r)
    (D/"verification.json").write_text(json.dumps(dict(guards=len(guards()),guard_digest=sha(D/"guards_local.json"),probe_digest=sha(B/"replay.exe"),sessions=qstats),indent=2)+"\n")
if __name__=="__main__":main()
