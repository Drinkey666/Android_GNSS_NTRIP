
import csv,math,sys
from collections import defaultdict,Counter
from pathlib import Path
from statistics import mean
from run_replays import OUT,ROOT,STEP7,DATASETS,CANDIDATES,baseline,old_a,args_for,read,rows,save,sha

sys.path.insert(0,str(ROOT/'tools'))
from evaluate_solution import enu,reference_ecef

LABEL=dict(zip(DATASETS,('11:20 vivo','11:20 小米','10:04 vivo','10:04 小米','10/31 小米 V1','10/31 小米 V2')))
SCHEMES=('Baseline','A',*CANDIDATES)
DISPLAY={'Baseline':'基线','A':'Step6 A','S1S2':'S1+S2','S1S2A':'S1+S2+A'}
TARGET=('1120_vivo','1004_xiaomi')
GROUP={'G':'GPS','E':'GAL','C':'BDS'}
ISB_NAMES={1:'GLO',2:'GAL',3:'BDS',4:'IRN'}
RCB_NAMES={0:'GPS 5Q',1:'GAL 5Q',2:'BDS 7I',3:'BDS 5P',4:'BDS 1P',5:'GAL 7Q'}
def key(w,t):
    return int(w),round(float(t))
def reference(d):
    if d.startswith('1031'):
        return read(ROOT/'validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json')['reference']
    args=args_for(d)
    return read(Path(args[args.index('--stream-session')+1])/'capture.json')['reference']
def xyz_to_enu(x,y,z,lat,lon):
    sl,cl=math.sin(lon),math.cos(lon)
    sp,cp=math.sin(lat),math.cos(lat)
    return -sl*x+cl*y,-sp*cl*x-sp*sl*y+cp*z,cp*cl*x+cp*sl*y+sp*z
def q6(rows,ref):
    assert reference_ecef(ref)[-1]
    result={}
    for row in rows:
        if row['Q']!='6':continue
        idx=key(row['week'],row['tow'])
        assert idx not in result
        result[idx]=(int(row['week'])*604800+float(row['tow']),*enu([float(row[k]) for k in ('x_m','y_m','z_m')],ref))
    return result
def summarize(d,c,q):
    pts=list(q.values())
    end=pts[-1][0]
    out=dict(dataset=d,scheme=c,q6=len(pts),first_q6_week=next(iter(q))[0],first_q6_second=next(iter(q))[1])
    out.update({f'first_{a}_m':pts[0][i] for i,a in enumerate('ENU',1)})
    for label,window in [('first20',pts[:20]),('all',pts),('tail60',[p for p in pts if end-p[0]<60.0])]:
        out.update({f'{label}_{a}_mean_m':mean(row[i] for row in window) for i,a in enumerate('ENU',1)})
        out.update({f'{label}_H_rms_m':math.sqrt(mean(e*e+n*n for _,e,n,u in window)),
                    f'{label}_U_rms_m':math.sqrt(mean(u*u for _,e,n,u in window)),f'{label}_n':len(window)})
    return out
def write(name,rs):
    with (OUT/name).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rs[0]))
        w.writeheader()
        w.writerows(rs)
def sum_gains(path,kind,timekeys,lat,lon):
    result=defaultdict(list)
    tags={'Baseline':'$S5_ROW,','A':'$S7_CODE,','New':'$S8_CODE,'}
    mark=tags[kind]
    with path.open(encoding='utf-8',errors='replace') as f:
        for line in f:
            if mark not in line:continue
            r=line.strip().split(mark,1)[-1].split(',')
            if key(*r[:2]) not in timekeys:continue
            if kind=='Baseline':
                if r[3]!='1':continue
                sat,sig=r[4:6]
                xyz=r[7:10]
            else:
                sat,sig=r[2:4]
                xyz=r[-3:]
            sys=GROUP.get(sat[0])
            if sys:result[sys].append(xyz_to_enu(*map(float,xyz),lat,lon))
    return result

def audit(path,d,c,q):
    commits={}
    seeds=[]
    first=next(iter(q))
    qkeys=set(q)
    slots=defaultdict(set)
    counts=Counter()
    with path.open(encoding='utf-8',errors='replace') as h:
        for line in h:
            assert '$S8_INVALID_PROFILE' not in line and '$S8_SEED_INVARIANT_FAILURE' not in line
            if '$S8_CLOSURE,' in line:
                w,t,i,P,prior,n,*diff=line.strip().split('$S8_CLOSURE,',1)[1].split(',')
                idx=key(w,t)
                assert idx not in commits and P==prior=='1'
                commits[idx]=(int(i),int(n),max(abs(float(y)) for y in diff))
            if '$S8_SEED,' not in line:continue
            w,t,i,kind,slot,peers,eligible,used,old,mid,change,new,P,amb=line.strip().split('$S8_SEED,',1)[1].split(',')
            idx=key(w,t)
            slot,peers,eligible,used,amb=map(int,(slot,peers,eligible,used,amb))
            old,mid,change,new,P=map(float,(old,mid,change,new,P))
            assert used==int(eligible and peers>=3)
            assert eligible==int(abs(old)<=1e-5 and P>0.)
            assert (kind=="RCB" and used) or amb==0
            assert math.isclose(new-old,change,rel_tol=3e-15,abs_tol=1e-14)
            if used:
                expected=1e-6 if old+mid==0. else old+mid
                assert math.isclose(new,expected,rel_tol=3e-15,abs_tol=1e-14)
            else:assert old==new and change==mid==0.
            assert (kind,slot) not in slots[idx]
            slots[idx].add((kind,slot))
            if used or idx==first:
                names=ISB_NAMES if kind=='ISB' else RCB_NAMES
                seeds.append(dict(dataset=d,scheme=c,week=idx[0],second=idx[1],trial=int(i),first_q6=idx==first,
                                  is_q6=idx in qkeys,kind=kind,slot=slot,state=names[slot],peers=peers,eligible=eligible,
                                  used=used,old_m=old,median_m=mid,applied_shift_m=change,new_m=new,prior_variance_m2=P,
                                  ambiguity_seeds_shifted=amb))
            counts['used_isb']+=kind=='ISB' and used
            counts['used_rcb']+=kind=='RCB' and used
            counts['ambiguity_seeds_shifted']+=amb
    assert qkeys<=commits.keys() and set(commits)==set(slots)
    expected_slots={('ISB',i) for i in (1,2,3,4)}|{('RCB',i) for i in range(5)}
    assert all(s==expected_slots for s in slots.values())
    max_close=max(x[2] for x in commits.values())
    assert max_close<1e-7
    return seeds,dict(covariance_preserved=True,prior_rows_preserved=True,commits=len(commits),
                       max_kv_xyz_closure_m=max_close,**counts)
def csv_quality(rs):
    return [(r['week'],r['tow'],r['Q']) for r in rs]
def fmt(x):return f'{x:+.3f}'
def triplet(r,p,axes,suffix):return '/'.join(f"{r[f'{p}_{a}_{suffix}']:.3f}" for a in axes)
def table(headers,rows):
    return '\n'.join('| '+' | '.join(map(str,r))+' |' for r in (headers,['---']*len(headers),*rows))
def main():
    guard=read(OUT/'input_guard_sha256.json')
    assert all(sha(Path(p))==h for p,h in guard.items())
    accuracy,events,gains,checked=[],[],[],[]
    step5=OUT.parent/'brain_step5_east_and_m1v2'
    for d in DATASETS:
        ref=reference(d)
        lat,lon,*_=reference_ecef(ref)
        stock=rows(baseline(d)/'solution.csv')
        standard_a=rows(old_a(d)/'solution.csv')
        for c in SCHEMES:
            if c=='Baseline':
                data=stock
                trace=baseline(d)/'solution.trace'
            elif c=='A':
                data=standard_a
                a=STEP7/'runs'/d/c
                assert all({k:v for k,v in a1.items() if k!='processing_ms'}=={k:v for k,v in a2.items() if k!='processing_ms'}
                    for a1,a2 in zip(data,rows(a/'solution.csv'),strict=True))
                assert sha(old_a(d)/'solution.stat')==sha(a/'solution.stat')
                trace=a/'solution.trace'
            else:
                p=OUT/'runs'/d/c
                data=rows(p/'solution.csv')
                trace=p/'solution.trace'
                assert all(sha(p/f)==sha(baseline(d)/f) for f in ('corrections.csv','observations.csv'))
            same=csv_quality(data)==csv_quality(stock)
            assert [(r['week'],r['tow']) for r in data]==[(r['week'],r['tow']) for r in stock]
            assert set(r['Q'] for r in data)<={'0','5','6'}
            q=q6(data,ref)
            accuracy.append(summarize(d,c,q))
            if c in CANDIDATES:
                shifts,check=audit(trace,d,c,q)
                events.extend(shifts)
                checked.append(dict(dataset=d,scheme=c,same_q=same,q6=len(q),**check))
            if d not in TARGET:continue
            groups=sum_gains(trace,c if c in ('Baseline','A') else 'New',set(list(q)[:20]),lat,lon)
            for sys in ('BDS','GAL','GPS'):
                values=groups[sys]
                gains.append(dict(dataset=d,scheme=c,group=sys,code_rows=len(values),
                                   **{a+'_Kv_m':sum(v[i] for v in values) for i,a in enumerate('ENU')}))
    keys={(r['dataset'],r['scheme'],r['group']):r for r in gains}
    for r in gains:
        for b in ('Baseline','A'):
            other=keys[r['dataset'],b,r['group']]
            for axis in 'ENU':
                k=axis+'_Kv_m'
                r['delta_vs_'+b+'_'+k]=r[k]-other[k]
    write('accuracy_first_and_full.csv',accuracy)
    write('seed_events.csv',events)
    write('first20_code_gain_by_system.csv',gains)
    save(OUT/'verification.json',dict(new_replays=len(checked),saved_baselines=6,saved_step6_A=6,
         checked_files=len(guard),compared_raw_and_ssr_equal=True,formal_sources_changed=False,
         after_replay_reference_only=True,no_if_or_ar=True,cases=checked,
         compiled_sources_sha256={n:sha(OUT/n) for n in ('step8_seed.inc','step8_private.patch')},
         borrowed_A_observer_sha256=sha(STEP7/'step7_weights.inc')))
    scores=table(['数据集','方案','Q6','第1期 E/N/U','前20 H/U RMS','全段 E/N/U 均值','全段 H/U RMS','末60秒 E/N/U 均值','末60秒 H/U RMS'],
                 [[LABEL[r['dataset']],DISPLAY[r['scheme']],r['q6'],'/'.join(fmt(r['first_'+a+'_m']) for a in 'ENU'),
                   triplet(r,'first20','HU','rms_m'),triplet(r,'all','ENU','mean_m'),triplet(r,'all','HU','rms_m'),
                   triplet(r,'tail60','ENU','mean_m'),triplet(r,'tail60','HU','rms_m')] for r in accuracy])
    seeds=table(['数据集','方案','状态','首期有效码行','实际位移 m','新模糊度同步数'],
                [[LABEL[r['dataset']],DISPLAY[r['scheme']],r['kind']+' '+r['state'],r['peers'],
                  fmt(r['applied_shift_m']) if r['used'] else '—',r['ambiguity_seeds_shifted']]
                 for r in events if r['dataset'] in TARGET and r['first_q6'] and
                    (r['kind']=='RCB' or r['state'] in ('GAL','BDS'))])
    contributions=table(['数据集','方案','北斗 E/N/U','Galileo E/N/U','GPS E/N/U'],
        [[LABEL[d],DISPLAY[c],*['/'.join(fmt(keys[d,c,sys][a+'_Kv_m']) for a in 'ENU') for sys in ('BDS','GAL','GPS')]]
         for d in TARGET for c in SCHEMES])
    terminal='\n\n'.join(['# 解算精度（m）',scores,'# 首个 Q6 中位数位移',seeds,
                          '# 前20期实际位置 K·v（m）',contributions])+'\n'
    (OUT/'TERMINAL_TABLES.md').write_text(terminal,encoding='utf-8')
    print(terminal)
    print(f'Verified {len(checked)} new replays, 12 reused solutions, {len(guard)} input/source SHA guards')
if __name__=='__main__':
    main()
