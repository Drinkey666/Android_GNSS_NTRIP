
import csv,math,sys
from collections import defaultdict,Counter
from pathlib import Path
from statistics import mean,median
from run_replays import OUT,ROOT,DATASETS,CANDIDATES,baseline,old_a,args_for,read,rows,save,sha

sys.path.insert(0,str(ROOT/'tools'))
from evaluate_solution import enu,reference_ecef

LABEL=dict(zip(DATASETS,('11:20 vivo','11:20 小米','10:04 vivo','10:04 小米','10/31 小米 V1','10/31 小米 V2')))
TARGET={'1120_vivo':('E27 1C','C19 2I','G03 1C'),'1004_xiaomi':('G10 1C','G25 1C','G28 1C')}
DISPLAY={'Baseline':'基线','A':'Step6 A','M1_v4_std':'std','M1_v4_tight':'tight','M1_v4_sf_only':'sf_only'}

def ref(d):
    if d.startswith('1031'):
        return read(ROOT/'validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json')['reference']
    args=args_for(d)
    return read(Path(args[args.index('--stream-session')+1])/'capture.json')['reference']
def key(week,tow):
    return int(week),round(float(tow))
def close(a,b):
    return math.isclose(a,b,rel_tol=3e-15,abs_tol=1e-13)
def xyz_to_enu(x,y,z,latitude,longitude):
    sl,cl=math.sin(longitude),math.cos(longitude)
    sp,cp=math.sin(latitude),math.cos(latitude)
    return (-sl*x+cl*y,-sp*cl*x-sp*sl*y+cp*z,cp*cl*x+cp*sl*y+sp*z)
def coordinates(rs,reference):
    q={}
    assert reference_ecef(reference)[-1]
    for r in rs:
        if r['Q']!='6':continue
        t=key(r['week'],r['tow'])
        assert t not in q
        q[t]=(int(r['week'])*604800+float(r['tow']),*enu([float(r[k]) for k in ('x_m','y_m','z_m')],reference))
    return q
def measures(d,c,q):
    def stats(points):
        pts=list(points)
        v={a+'_mean_m':mean(p[i] for p in pts) for i,a in enumerate('ENU',1)}
        v.update(n=len(pts),H_rms_m=math.sqrt(mean(p[1]**2+p[2]**2 for p in pts)),
                 U_rms_m=math.sqrt(mean(p[3]**2 for p in pts)))
        return v
    end=list(q.values())[-1][0]
    return dict(dataset=d,scheme=c,**{
        label+'_'+k:v for label,part in [('all',q.values()),('tail60',[p for p in q.values() if end-p[0]<60.0])]
        for k,v in stats(part).items()})
def write_csv(name,rs):
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)
def check_file(d,c,base,data):
    assert [(r['week'],r['tow']) for r in data]==[(r['week'],r['tow']) for r in base],(d,c)
    assert set(r['Q'] for r in data)<={'0','5','6'}
    path=OUT/'runs'/d/c
    assert all(sha(path/f)==sha(baseline(d)/f) for f in ('observations.csv','corrections.csv'))
    if c=='A':
        ref_a=rows(old_a(d)/'solution.csv')
        without_time=lambda rs:[{k:v for k,v in r.items() if k!='processing_ms'} for r in rs]
        assert without_time(data)==without_time(ref_a),(d,'A coordinates differ')
        assert sha(path/'solution.stat')==sha(old_a(d)/'solution.stat'),(d,'A states differ')
    return [r['Q'] for r in data]==[r['Q'] for r in base]
def parse_baseline(path,q,d,reference):
    if d not in TARGET:return []
    watch=set(TARGET[d])
    focus=[]
    latitude,longitude,_,_=reference_ecef(reference)
    with path.open(encoding='utf-8',errors='replace') as handle:
        for line in handle:
            if '$S5_ROW,' not in line:continue
            w,t,trial,cl,sat,signal,slot,x,y,z,*values=line.strip().split('$S5_ROW,',1)[1].split(',')
            idx=key(w,t)
            label=f'{sat} {signal}'
            if cl!='1' or idx not in q or label not in watch:continue
            e,n,u=xyz_to_enu(*map(float,(x,y,z)),latitude,longitude)
            focus.append(dict(week=idx[0],second=idx[1],signal=label,codes='',has_phase='',peers='',df_peers='',gim='',
                              checked='',scale='',center='',gate='',dev='',multiplier=1.,E=e,N=n,U=u))
    return focus
def thresholds(c,codes,phase,scale):
    if c=='A':return max(3.,2.5*scale) if phase else 2.
    if codes>=2:return max(3.,2.3*scale) if c=='M1_v4_tight' else max(3.2,2.5*scale)
    if not phase:return max(2.,1.8*scale)
    return max(2.4,2.*scale) if c=='M1_v4_tight' else max(2.6,2.2*scale)
def audit_groups(groups,c):
    for items in groups.values():
        votes={}
        for row in items:
            votes.setdefault(row['sat'],row)
        n=len(votes)
        dual=[r['checked'] for r in votes.values() if r['codes']>=2]
        allv=[r['checked'] for r in votes.values()]
        assert all(r['peers']==n and r['df']==len(dual) for r in items)
        if n<4:continue
        sample=dual if c=='A' and len(dual)>=2 else allv
        center=median(sample)
        if c!='A' and len(dual)>=4:center=(center+median(dual))*0.5
        mad=1.4826*median(abs(s-center) for s in sample)
        lo=1.2 if c=='A' else 1.1
        hi=2.2 if c=='A' else 1.5 if c=='M1_v4_tight' else 1.6
        scale=min(hi,max(lo,mad))
        for r in items:
            assert close(r['center'],center) and close(r['scale'],scale)
def parse_case(path,q,c,d,reference):
    focus=[]
    watch=set(TARGET.get(d,()))
    latitude,longitude,_,_=reference_ecef(reference)
    groups=defaultdict(list)
    closure={}
    counts=Counter()
    seen=set()
    with path.open(encoding='utf-8',errors='replace') as handle:
        for line in handle:
            assert '$S7_INVALID_PROFILE' not in line
            if '$S7_CLOSURE,' in line:
                w,t,*diff=line.strip().split('$S7_CLOSURE,',1)[1].split(',')
                idx=key(w,t)
                assert idx not in closure
                closure[idx]=max(abs(float(v)) for v in diff)
            if '$S7_CODE,' not in line:continue
            fields=line.strip().split('$S7_CODE,',1)[1].split(',')
            assert len(fields)==22
            w,t,sat,sig,slot,codes,phase,peers,df,gim,*rest=fields
            slot,codes,phase,peers,df,gim=map(int,(slot,codes,phase,peers,df,gim))
            idx=key(w,t)
            assert idx in q and (idx,sat,sig,slot) not in seen
            seen.add((idx,sat,sig,slot))
            v,checked,center,scale,gate,dev,mult,old,R,x,y,z=map(float,rest)
            is_ref=slot==0 and (sat[0] in 'GE' and sig=='1C' or sat[0]=='C' and sig=='2I')
            assert close(old*mult,R)
            if not is_ref:
                assert gim==0 and v==checked and mult==1.
                counts['untouched_nonreference_rows']+=1
            if c=='A' and codes>1:
                assert gim==0 and checked==v
            if c=='M1_v4_sf_only' and codes>1:assert mult==1.
            if is_ref:
                counts['reference_rows']+=1
                groups[(idx,sat[0],sig)].append(dict(sat=sat,codes=codes,checked=checked,center=center,scale=scale,peers=peers,df=df))
                if peers>=4:
                    assert close(gate,thresholds(c,codes,phase,scale))
                    assert close(abs(checked-center),dev)
                else:assert mult==1.
            eligible=(codes==1 or not phase) if c=='A' else (c!='M1_v4_sf_only' or codes==1)
            expected=min(36.,(dev/gate)**2) if is_ref and peers>=4 and eligible and dev>gate else 1.
            assert close(mult,expected)
            counts['triggers']+=mult>1.
            counts['dual_ref_triggers']+=is_ref and codes>=2 and mult>1.
            counts['dual_ref_iono_corrected']+=is_ref and codes>=2 and gim
            label=f'{sat} {sig}'
            if label in watch:
                e,n,u=xyz_to_enu(x,y,z,latitude,longitude)
                focus.append(dict(week=idx[0],second=idx[1],signal=label,codes=codes,has_phase=phase,peers=peers,
                    df_peers=df,gim=gim,checked=checked,scale=scale,center=center,gate=gate,dev=dev,multiplier=mult,
                    E=e,N=n,U=u))
    assert q.keys()==closure.keys() and max(closure.values())<1e-7,(d,c)
    audit_groups(groups,c)
    return focus,dict(max_kv_xyz_closure_m=max(closure.values()),**counts)
def contribution(d,c,q,detail):
    records=[]
    all_times=list(q)
    for label in TARGET.get(d,()):
        series=[r for r in detail if r['signal']==label]
        for win,ts in [('all',all_times),('first20',all_times[:20]),('first60',all_times[:60])]:
            tset=set(ts)
            filtered=[r for r in series if (r['week'],r['second']) in tset]
            inflations=[r['multiplier'] for r in filtered if r['multiplier']>1.]
            v=[sum(r[a] for r in filtered) for a in 'ENU']
            records.append(dict(dataset=d,scheme=c,signal=label,window=win,rows=len(filtered),
                triggered=len(inflations),trigger_mean=mean(inflations) if inflations else None,
                trigger_max=max(inflations) if inflations else None,E_Kv_m=v[0],N_Kv_m=v[1],U_Kv_m=v[2],
                H_vector_norm_m=math.hypot(*v[:2])))
    return records
def htable(headers, data):
    return '\n'.join('| '+' | '.join(map(str,r))+' |' for r in (headers,['---']*len(headers),*data))
def seq(r,scope,axes,suffix):
    return '/'.join(f"{r[scope+'_'+a+'_'+suffix]:.3f}" for a in axes)
def main():
    guard=read(OUT/'input_guard_sha256.json')
    assert all(sha(Path(p))==h for p,h in guard.items())
    global_accuracy,all_contrib,detail_rows,checks=[],[],[],[]
    for d in DATASETS:
        base=rows(baseline(d)/'solution.csv')
        reference=ref(d)
        q=coordinates(base,reference)
        global_accuracy.append(measures(d,'Baseline',q))
        basic=parse_baseline(baseline(d)/'solution.trace',q,d,reference)
        all_contrib+=contribution(d,'Baseline',q,basic)
        for c in CANDIDATES:
            path=OUT/'runs'/d/c
            data=rows(path/'solution.csv')
            same_q=check_file(d,c,base,data)
            solution=coordinates(data,reference)
            logs,audit=parse_case(path/'solution.trace',solution,c,d,reference)
            global_accuracy.append(measures(d,c,solution))
            all_contrib+=contribution(d,c,solution,logs)
            detail_rows.extend(dict(dataset=d,scheme=c,**r) for r in logs)
            checks.append(dict(dataset=d,scheme=c,same_q=same_q,q6=len(solution),**audit))
    a_rows={(r['dataset'],r['signal'],r['window']):r for r in all_contrib if r['scheme']=='A'}
    for r in all_contrib:
        a=a_rows[r['dataset'],r['signal'],r['window']]
        for d in ('E_Kv_m','N_Kv_m','U_Kv_m','H_vector_norm_m'):
            r[f'delta_vs_A_{d}']=r[d]-a[d]
    write_csv('accuracy_all_and_last60.csv',global_accuracy)
    write_csv('target_gain_actions.csv',all_contrib)
    write_csv('target_committed_rows.csv',detail_rows)
    save(OUT/'verification.json',dict(new_replays=len(checks),baseline_reused=6,A_exact_reproduced_except_processing_ms=6,
         guard_files=len(guard),observations_and_ssr_verified=True,no_production_changes=True,
         reference_used_only_after_replay=True,used_if=False,used_ar=False,verified_cases=checks,
         max_Kv_closure_m=max(x['max_kv_xyz_closure_m'] for x in checks),
         private_source_sha256={n:sha(OUT/n) for n in ('step7_weights.inc','step7_private.patch')}))
    scores=htable(['数据集','方案','Q6','全段 E/N/U 均值','全段 H/U RMS','末60秒 E/N/U 均值','末60秒 H/U RMS'],
           [[LABEL[r['dataset']],DISPLAY[r['scheme']],r['all_n'],seq(r,'all','ENU','mean_m'),seq(r,'all','HU','rms_m'),
             seq(r,'tail60','ENU','mean_m'),seq(r,'tail60','HU','rms_m')] for r in global_accuracy])
    index={(r['dataset'],r['scheme'],r['signal'],r['window']):r for r in all_contrib}
    action=[]
    vec=lambda r:'/'.join(f"{r[a+'_Kv_m']:+.3f}" for a in 'ENU')
    for d,labels in TARGET.items():
        for label in labels:
            for c in ('Baseline',*CANDIDATES):
                r,p20,p60=[index[d,c,label,w] for w in ('all','first20','first60')]
                avg='—' if r['trigger_mean'] is None else f"{r['trigger_mean']:.2f}"
                action.append([LABEL[d],label,DISPLAY[c],f"{r['triggered']}/{r['rows']}",avg,
                               vec(p20),vec(p60),f"{p20['H_vector_norm_m']:.3f}/{p60['H_vector_norm_m']:.3f}"])
    evidence=htable(['数据集','星信号','方案','触发/码行','平均倍率','前20 E/N/U','前60 E/N/U','前20/60 水平向量模'],action)
    text='# 全段及末段精度（m）\n\n'+scores+'\n\n# 最终 Q6 码行的动作与 K·v（m）\n\n'+evidence+'\n'
    (OUT/'TERMINAL_TABLES.md').write_text(text,encoding='utf-8')
    print(text)
    print('Verified',len(checks),'new replays, 6 saved baselines and',len(guard),'source/input SHA guards.')
if __name__=='__main__':
    main()
