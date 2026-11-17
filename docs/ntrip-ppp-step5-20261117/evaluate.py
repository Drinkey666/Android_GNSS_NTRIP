
import csv,json,math,sys
from collections import defaultdict,Counter
from pathlib import Path
from statistics import mean

from run_replays import OUT,ROOT,DATASETS,MASKS,CANDIDATES,baseline,args_for,read,rows,save,sha
sys.path.insert(0,str(ROOT/'tools'))
from evaluate_solution import enu,reference_ecef

NAMES=dict(zip(DATASETS,('11:20 vivo','11:20 小米','10:04 vivo','10:04 小米','10/31 小米 V1','10/31 小米 V2')))
GROUPS=('GPS 1C','GPS 5Q','GAL 1C','GAL 5Q','BDS 2I','BDS 7I','BDS 5P',
        'Phase','IONEX','VMF3','Other')
SYS={'G':'GPS','E':'GAL','C':'BDS'}
CLASS={0:'Other',2:'Phase',3:'IONEX',4:'VMF3'}
MASK_SYS=dict(zip(MASKS,('C','E','G')))
FOCUS=(('E27','1C'),('C19','2I'),('G03','1C'))

def key(week,tow):
    return (int(week),round(float(tow)))
def dataset_reference(d):
    if d.startswith('1031'):
        return read(ROOT/'validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json')['reference']
    args=args_for(d)
    return read(Path(args[args.index('--stream-session')+1])/'capture.json')['reference']
def project(lat,lon,x,y,z):
    sp,cp,sl,cl=math.sin(lat),math.cos(lat),math.sin(lon),math.cos(lon)
    return -sl*x+cl*y,-sp*cl*x-sp*sl*y+cp*z,cp*cl*x+cp*sl*y+sp*z
def solve(data,reference):
    q={}
    for r in data:
        if r['Q']!='6':continue
        t=key(r['week'],r['tow'])
        assert t not in q
        q[t]=(int(r['week'])*604800+float(r['tow']),*enu([float(r[k]) for k in ('x_m','y_m','z_m')],reference))
    return q
def tail(q):
    last=next(reversed(q.values()))[0] if q else 0
    return {t:p for t,p in q.items() if last-p[0]<60.0}
def stats(q):
    pts=list(q.values())
    out={'n':len(pts)}
    for i,k in enumerate('ENU',1):
        out[k+'_mean_m']=mean(p[i] for p in pts) if pts else None
    out['H_RMS_m']=math.sqrt(mean(p[1]**2+p[2]**2 for p in pts)) if pts else None
    out['U_RMS_m']=math.sqrt(mean(p[3]**2 for p in pts)) if pts else None
    return out
def tablefile(name,data):
    with (OUT/name).open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
def read_trace(path,sol,ref,scheme):
    lat,lon,_,vertical=reference_ecef(ref)
    assert vertical
    logs=[]
    closures={}
    other_errors=Counter()
    with path.open(encoding='utf-8',errors='replace') as inp:
        for line in inp:
            if '$PPP_FAILURE,' in line:
                other_errors[line.split('reason=',1)[-1].split(',',1)[0].strip()]+=1
            assert '$S5_INVALID_PROFILE' not in line
            if '$S5_CLOSURE,' in line:
                w,t,*xyz=line.strip().split('$S5_CLOSURE,',1)[1].split(',')
                idx=key(w,t)
                assert idx not in closures
                closures[idx]=max(abs(float(v)) for v in xyz)
            if '$S5_ROW,' not in line:
                continue
            w,t,it,klass,sat,signal,slot,*values=line.strip().split('$S5_ROW,',1)[1].split(',')
            idx=key(w,t)
            cl=int(klass)
            if idx not in sol:continue
            x,y,z,post,post_m,g,h,old,new,dev,gim=map(float,values)
            e,n,u=project(lat,lon,x,y,z)
            if cl==1:
                assert math.isclose(old*g*h,new,rel_tol=2e-15,abs_tol=1e-12)
                if scheme in CANDIDATES:
                    gate=3.0 if scheme.endswith('3.0') else 2.5
                    assert g in (1.0,4.0) and 1.0<=h<=(25 if gate==3 else 36)
                    assert (h>1.0)==(dev>gate)
                else:
                    assert g==h==1.0
                group=f'{SYS.get(sat[0],"Other")} {signal}'
            else:
                group=CLASS[cl]
            logs.append(dict(week=idx[0],second=idx[1],sat=sat,signal=signal,slot=int(slot)+1,
                 trial=int(it),cls=cl,group=group,E=e,N=n,U=u,postP_m=post_m if post else None,
                 no_phase_factor=g,hub_factor=h,hub_dev_m=dev,gim=bool(gim)))
    maxc=max(closures.values(),default=0.)
    assert sol.keys()<=closures.keys() and maxc<1e-7,(path,maxc)
    return logs,maxc,other_errors
def push(one,win):
    selected=[r for r in one if (r['week'],r['second']) in win]
    return {f'{axis}_Kv_m':sum(x[axis] for x in selected) for axis in 'ENU'}|{'rows':len(selected)}
def report_signal(d,logs,q):
    first=set(list(q)[:60])
    last=set(tail(q))
    all_group=sorted(set(r['group'] for r in logs)-set(GROUPS))
    results=[]
    for group in (*GROUPS,*all_group):
        selects=[r for r in logs if r['group']==group]
        pm=[r['postP_m'] for r in selects if (r['week'],r['second']) in last and r['postP_m'] is not None]
        result={'dataset':d,'group':group,'tail60_meanP_m':mean(pm) if pm else None,'tail60_meanP_count':len(pm)}
        for label,window in (('all',q),('first60',first),('tail60',last)):
            result.update({label+'_'+k:v for k,v in push(selects,window).items()})
        results.append(result)
    return results
def state_budget(d,logs,q):
    start=next(iter(q))
    last=next(reversed(q))
    first=push(logs,{start})
    all_update=push(logs,q)
    out={'dataset':d}
    for i,direction in enumerate('ENU',1):
        k=direction+'_Kv_m'
        initial_prior=q[start][i]-first[k]
        other=q[last][i]-initial_prior-all_update[k]
        out.update({direction+'_first_q6_before_measurement_m':initial_prior,
                    direction+'_all_q6_measurement_Kv_m':all_update[k],
                    direction+'_between_q6_terms_m':other,
                    direction+'_last_q6_m':q[last][i]})
    return out

def counts(part):
    gh=[row['hub_factor'] for row in part if row['hub_factor']>1.]
    gg=[row['no_phase_factor'] for row in part if row['no_phase_factor']>1.]
    return dict(rows=len(part),hub_trigger=len(gh),hub_avg=mean(gh) if gh else None,
                hub_max=max(gh) if gh else None,no_phase_trigger=len(gg),
                either_trigger=sum(r['hub_factor']>1. or r['no_phase_factor']>1. for r in part),
                gim_rows=sum(r['gim'] for r in part))
def focused(d,c,logs,q):
    result=[]
    tail_keys=set(tail(q))
    first=set(list(q)[:60])
    selectors=[(f'{sat} {sig}',[r for r in logs if (r['sat'],r['signal'])==(sat,sig)]) for sat,sig in FOCUS]
    selectors.extend([(group,[r for r in logs if r['group']==group]) for group in GROUPS[:7]])
    selectors.append(('ALL_CODE',logs))
    for name,series in selectors:
        for label,subset in [('all',series),('first60',[r for r in series if (r['week'],r['second']) in first]),
                             ('tail60',[r for r in series if (r['week'],r['second']) in tail_keys])]:
            result.append(dict(dataset=d,scheme=c,scope=label,group=name,**counts(subset)))
    return result
def summary(d,c,q):
    m={f'{label}_{k}':v for label,sub in [('all',q),('tail60',tail(q))] for k,v in stats(sub).items()}
    return dict(dataset=d,scheme=c,**m)
def strval(x):
    return '—' if x is None else f'{x:.3f}'
def xyz(r,scope,suffix):
    return '/'.join(strval(r[f'{scope}_{k}_{suffix}']) for k in 'ENU')
def hu(r,scope):
    return '/'.join(strval(r[f'{scope}_{k}_RMS_m']) for k in 'HU')
def markdown(headers,lines):
    return '\n'.join('| '+' | '.join(map(str,r))+' |' for r in (headers,['---']*len(headers),*lines))
def table_metrics(rs):
    return markdown(['数据集','方案','Q6','全段 E/N/U 均值','全段 H/U RMS','末60秒 E/N/U 均值','末60秒 H/U RMS'],
                  [[NAMES[r['dataset']],r['scheme'],r['all_n'],xyz(r,'all','mean_m'),hu(r,'all'),
                    xyz(r,'tail60','mean_m'),hu(r,'tail60')] for r in rs])
def main():
    guard=read(OUT/'input_guard_sha256.json')
    assert all(sha(Path(k))==v for k,v in guard.items())
    signal,phasemasks,common,focus,allq,proof,focusrows,budget=[],[],[],[],[],[],[],[]
    for d in DATASETS:
        ref=dataset_reference(d)
        old=baseline(d)
        baserows=rows(old/'solution.csv')
        q0=solve(baserows,ref)
        t0=tail(q0)
        base_logs=None
        for c in ('Baseline',*MASKS,*CANDIDATES):
            if d=='1031_xiaomi_V1' and c in MASKS:continue
            folder=OUT/'runs'/d/c
            data=rows(folder/'solution.csv')
            assert [(r['week'],r['tow']) for r in data]==[(r['week'],r['tow']) for r in baserows]
            assert set(x['Q'] for x in data)<={'0','5','6'}
            assert all(sha(old/name)==sha(folder/name) for name in ('observations.csv','corrections.csv'))
            if c=='Baseline':
                assert sha(old/'solution.stat')==sha(folder/'solution.stat')
                assert [{k:v for k,v in r.items() if k!='processing_ms'} for r in data]==[
                    {k:v for k,v in r.items() if k!='processing_ms'} for r in baserows]
            q=solve(data,ref)
            logs,closure,errors=read_trace(folder/'solution.trace',q,ref,c)
            allq.append(summary(d,c,q))
            proof.append(dict(dataset=d,scheme=c,q6=len(q),same_q=all(r['Q']==s['Q'] for r,s in zip(data,baserows)),
                              max_kv_xyz_closure_m=closure,trace_failures=dict(errors),
                              same_observations=True,same_ssr_corrections=True))
            if c=='Baseline':
                base_logs=logs
                if d!='1031_xiaomi_V1':
                    signal+=report_signal(d,logs,q)
                    budget.append(state_budget(d,logs,q))
            else:
                for label,window in ('all',q0),('baseline_tail60',t0):
                    ts=[t for t in window if t in q]
                    a,b=stats({t:q0[t] for t in ts}),stats({t:q[t] for t in ts})
                    common.append(dict(dataset=d,scheme=c,scope=label,**{f'base_{k}':v for k,v in a.items()},
                                       **{f'candidate_{k}':v for k,v in b.items()}))
            if c in MASKS:
                shared=q.keys()&q0.keys()
                fs=lambda records:sum(r['cls']==2 and r['sat'].startswith(MASK_SYS[c]) and
                                       (r['week'],r['second']) in shared for r in records)
                phasemasks.append(dict(dataset=d,scheme=c,common_q6=len(shared),
                             baseline_target_constellation_phase_rows=fs(base_logs),
                             ablation_target_constellation_phase_rows=fs(logs)))
            if c in CANDIDATES:
                focus.extend(focused(d,c,logs,q))
                for row in logs:
                    if (row['sat'],row['signal']) in FOCUS or (d=='1004_xiaomi' and row['hub_factor']>1.):
                        focusrows.append(dict(dataset=d,scheme=c,**row))
    tablefile('signal_group_gain_and_meanP.csv',signal)
    tablefile('state_transition_budget.csv',budget)
    tablefile('all_epoch_accuracy.csv',allq)
    tablefile('matched_baseline_windows.csv',common)
    tablefile('masked_constellation_phase_retention.csv',phasemasks)
    tablefile('m1v2_action_summary.csv',focus)
    tablefile('m1v2_focused_code_rows.csv',focusrows)
    proof_summary=dict(cases=len(proof),guards=len(guard),guard_hashes_all_equal=True,code_changes_in_production=False,
                 max_kv_xyz_closure_m=max(r['max_kv_xyz_closure_m'] for r in proof),cases_detail=proof,
                 private_source_sha256={name:sha(OUT/name) for name in ('step5_private.patch','step5_weights.inc')},
                 used_if=False,used_ar=False,reference_used_after_replay=True)
    save(OUT/'verification.json',proof_summary)
    t1=table_metrics([r for r in allq if r['scheme'] not in CANDIDATES and r['dataset']!='1031_xiaomi_V1'])
    t2=table_metrics([r for r in allq if r['scheme'] not in MASKS])
    t3=markdown(['数据集','信号组','末60 meanP','码残差数','前60 E/N/U K·v','全段 E/N/U K·v'],
                [[NAMES[r['dataset']],r['group'],strval(r['tail60_meanP_m']),r['tail60_meanP_count'],
                  xyz(r,'first60','Kv_m'),xyz(r,'all','Kv_m')] for r in signal])
    t4=markdown(['数据集','方案','卫星/组','Q6 码行','Huber 触发','无相位触发'],
                [[NAMES[r['dataset']],r['scheme'],r['group'],r['rows'],r['hub_trigger'],r['no_phase_trigger']]
                 for r in focus if r['scope']=='all' and r['dataset'] in ('1120_vivo','1004_xiaomi') and
                 (r['group'] in [f'{sat} {sig}' for sat,sig in FOCUS] or r['group']=='ALL_CODE')])
    terminal='\n\n'.join(['# 基线信号组',t3,'# 星座码消融',t1,'# M1_v2',t2,'# 重点动作',t4])+'\n'
    (OUT/'TERMINAL_TABLES.md').write_text(terminal,encoding='utf-8')
    print(terminal)

if __name__=='__main__':
    main()
