
import csv,math,sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

from run_replays import OUT,ROOT,STEP5,DATASETS,CANDIDATES,baseline,args_for,read,rows,save,sha
sys.path.insert(0,str(ROOT/'tools'))
from evaluate_solution import enu,reference_ecef

NAMES=dict(zip(DATASETS,('11:20 vivo','11:20 小米','10:04 vivo','10:04 小米','10/31 小米 V1','10/31 小米 V2')))
WANTED={'E27 1C','C19 2I','G03 1C','G10 1C','G25 1C','G28 1C','G13 1C','G32 1C'}
def key(w,t):
    return int(w),round(float(t))
def reference(d):
    if d.startswith('1031'):
        return read(ROOT/'validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json')['reference']
    args=args_for(d)
    return read(Path(args[args.index('--stream-session')+1])/'capture.json')['reference']
def solutions(data,ref):
    q={}
    assert reference_ecef(ref)[-1]
    for r in data:
        if r['Q']!='6':continue
        t=key(r['week'],r['tow'])
        assert t not in q
        q[t]=(int(r['week'])*604800+float(r['tow']),*enu([float(r[k]) for k in ('x_m','y_m','z_m')],ref))
    return q
def stats(q):
    pts=list(q)
    out={'n':len(pts)}
    for i,k in enumerate('ENU',1):
        out[k+'_mean_m']=mean(p[i] for p in pts)
    out['H_RMS_m']=math.sqrt(mean(p[1]**2+p[2]**2 for p in pts))
    out['U_RMS_m']=math.sqrt(mean(p[3]**2 for p in pts))
    return out
def metrics(d,c,q):
    end=next(reversed(q.values()))[0]
    m={f'{label}_{k}':v for label,sub in [('all',q.values()),('tail60',[p for p in q.values() if end-p[0]<60.0])]
       for k,v in stats(sub).items()}
    return dict(dataset=d,scheme=c,**m)
def write(name,data):
    with (OUT/name).open('w',encoding='utf-8',newline='') as h:
        w=csv.DictWriter(h,fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)
def check_trace(path,c,q):
    epoch={}
    details=[]
    count=defaultdict(int)
    seen=set()
    first=next(iter(q))
    with path.open(encoding='utf-8',errors='replace') as stream:
        for line in stream:
            assert '$S6_INVALID_PROFILE' not in line
            if '$S6_EPOCH,' in line:
                week,tow,n,earlier=line.strip().split('$S6_EPOCH,',1)[1].split(',')
                time=key(week,tow)
                assert time not in epoch
                epoch[time]=(int(n),bool(int(earlier)))
                assert epoch[time][1]==(time!=first)
                continue
            if '$S6_CODE,' not in line:continue
            fields=line.strip().split('$S6_CODE,',1)[1].split(',')
            assert len(fields)==20
            w,tow,sat,sig,slot,codes,phase,peers,df,gim,v,checked,center,scale,gate,dev,hub,gps,base,R=fields
            time=key(w,tow)
            slot,codes,phase,peers,df,gim=map(int,(slot,codes,phase,peers,df,gim))
            v,checked,center,scale,gate,dev,hub,gps,base,R=map(float,(v,checked,center,scale,gate,dev,hub,gps,base,R))
            assert (time,sat,sig,slot) not in seen
            seen.add((time,sat,sig,slot))
            nphase,earlier=epoch[time]
            is_ref=slot==0 and ((sat[0] in 'GE' and sig=='1C') or (sat[0]=='C' and sig=='2I'))
            gps_single=is_ref and sat.startswith('G') and codes==1
            expected_gps=2.5 if gps_single and c=='B' else 3.0 if gps_single and c=='C' and earlier and nphase>=6 else 1.
            assert gps==expected_gps
            assert math.isclose(base*hub*gps,R,rel_tol=2e-15,abs_tol=1e-12)
            if not is_ref:
                assert hub==gps==1. and gim==0 and checked==v
                count['nonreference_code_rows_preserved']+=1
            if codes>=2:
                assert gim==0 and checked==v and gps==1.
                if phase:
                    assert hub==1.
                    count['dual_code_with_phase_preserved']+=1
                elif hub>1:
                    count['dual_code_no_phase_rule2']+=1
            if is_ref and peers>=4:
                assert 1.2<=scale<=2.2 and df<=peers
                assert math.isclose(abs(checked-center),dev,rel_tol=1e-12,abs_tol=1e-13)
                assert gate==(max(3.,2.5*scale) if phase else 2.)
            expected_hub=min(36.,(dev/gate)**2) if is_ref and peers>=4 and (codes==1 or not phase) and dev>gate else 1.
            assert math.isclose(expected_hub,hub,rel_tol=2e-15)
            count['rule2_rows']+=hub>1.
            count['rule3_rows']+=gps>1.
            count['code_rows']+=1
            if f'{sat} {sig}' in WANTED:
                details.append(dict(week=time[0],second=time[1],sat=sat,signal=sig,slots=codes,has_phase=phase,
                                     phase_sat=nphase,peers=peers,df_peers=df,gim=gim,dev_m=dev,gate_m=gate,
                                     rule2_factor=hub,rule3_factor=gps))
    assert set(epoch)==set(q),(path,len(epoch),len(q))
    return details,count
def actions(d,c,q,details):
    result=[]
    first20=set(list(q)[:20])
    for target in sorted(WANTED):
        focus=[r for r in details if f"{r['sat']} {r['signal']}"==target]
        for window,selection in [('all_Q6',focus),('first20_Q6',[r for r in focus if (r['week'],r['second']) in first20])]:
            a=[r['rule2_factor'] for r in selection if r['rule2_factor']>1.]
            b=[r['rule3_factor'] for r in selection if r['rule3_factor']>1.]
            result.append(dict(dataset=d,scheme=c,window=window,signal=target,
                               code_rows=len(selection),single_code_rows=sum(r['slots']==1 for r in selection),
                               paired_center_rows=sum(r['peers']>=4 and r['df_peers']>=2 for r in selection),
                               single_gim_rows=sum(r['gim'] for r in selection),
                               rule2_trigger=len(a),rule3_trigger=len(b),rule2_max=max(a) if a else None,
                               rule3_max=max(b) if b else None))
    return result
def markdown(headers, lines):
    return '\n'.join('| '+' | '.join(map(str,r))+' |' for r in (headers,['---']*len(headers),*lines))
def triplet(r,w,axes,suffix):
    return '/'.join(f"{r[f'{w}_{a}_{suffix}']:.3f}" for a in axes)
def main():
    guard=read(OUT/'input_guard_sha256.json')
    assert all(sha(Path(k))==v for k,v in guard.items())
    score,proof,trigger,detail=[],[],[],[]
    for d in DATASETS:
        ref=reference(d)
        old=baseline(d)
        original=rows(old/'solution.csv')
        for c in ('Baseline',*CANDIDATES):
            path=OUT/'runs'/d/c
            assert all(sha(old/n)==sha(path/n) for n in ('observations.csv','corrections.csv'))
            data=rows(path/'solution.csv')
            assert [(r['week'],r['tow']) for r in data]==[(r['week'],r['tow']) for r in original]
            assert set(r['Q'] for r in data)<={'0','5','6'}
            same_q=[r['Q'] for r in data]==[r['Q'] for r in original]
            if c=='Baseline':
                assert sha(old/'solution.stat')==sha(path/'solution.stat')
                no_t=lambda rs:[{k:v for k,v in r.items() if k!='processing_ms'} for r in rs]
                assert no_t(data)==no_t(original)
            q=solutions(data,ref)
            score.append(metrics(d,c,q))
            totals={}
            if c!='Baseline':
                inspected,totals=check_trace(path/'solution.trace',c,q)
                trigger.extend(actions(d,c,q,inspected))
                detail.extend(dict(dataset=d,scheme=c,**r) for r in inspected)
            proof.append(dict(dataset=d,scheme=c,epochs=len(data),same_q=same_q,q6=len(q),**totals))
    write('accuracy_all_and_last60.csv',score)
    write('m1v3_triggers.csv',trigger)
    write('m1v3_target_rows.csv',detail)
    save(OUT/'verification.json',dict(cases=len(score),guard_count=len(guard),production_code_changed=False,
        baselines_match_exactly_except_processing_ms=6,common_observations_and_ssr_all_cases=True,
        reference_used_after_replay=True,details=proof,
        source_sha256={n:sha(OUT/n) for n in ('step6_private.patch','step6_weights.inc')}))
    mt=markdown(['数据集','方案','Q6','全段 E/N/U 均值','全段 H/U RMS','末60秒 E/N/U 均值','末60秒 H/U RMS'],
                [[NAMES[r['dataset']],r['scheme'],r['all_n'],triplet(r,'all','ENU','mean_m'),triplet(r,'all','HU','RMS_m'),
                  triplet(r,'tail60','ENU','mean_m'),triplet(r,'tail60','HU','RMS_m')] for r in score])
    ct=markdown(['数据集','方案','E27 规则2/3','C19 规则2/3','G03 规则2/3'],
                [[NAMES[d],c,*[next(f"{r['rule2_trigger']}/{r['rule3_trigger']}" for r in trigger if
                  (r['dataset'],r['scheme'],r['signal'],r['window'])==(d,c,t,'all_Q6'))
                  for t in ('E27 1C','C19 2I','G03 1C')]] for d in DATASETS for c in CANDIDATES])
    text='# 方案精度对照（m）\n\n'+mt+'\n\n# 全段最终 Q6 触发码行\n\n'+ct+'\n'
    (OUT/'TERMINAL_TABLES.md').write_text(text,encoding='utf-8')
    print(text)
if __name__=='__main__':
    main()
