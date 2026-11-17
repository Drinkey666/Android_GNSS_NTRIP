
from collections import Counter,defaultdict
from math import cos,sin,isclose,sqrt,isfinite
from pathlib import Path
from statistics import mean
import csv,re,sys

from run_replays import OUT,ROOT,DATASETS,CONFIGS,arguments,capture,read,save,sha,rows
sys.path.insert(0,str(ROOT/'tools'))
from evaluate_solution import enu, reference_ecef

RUNS=OUT/'runs'
FOCUS={
    '1120_vivo': [('G03','1C'),('G10','1C'),('E27','1C'),('C19','2I'),('G25','1C')],
    '1031_xiaomi_V1':[('G25','1C')], '1031_xiaomi_V2':[('G25','1C')],
}
XYZ=('x_m','y_m','z_m')
MODES=('M1','M2','M3')

def write_csv(name,results):
    with (OUT/name).open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)

def key(s):
    return int(s['week'])*604800+round(float(s['tow']))

def untimed(data):
    return [{k:v for k,v in r.items() if k!='processing_ms'} for r in data]

def ref(dataset):
    if dataset.startswith('1031'):
        path=ROOT/'validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json'
    else:
        path=capture(dataset)/'capture.json'
    value=read(path)['reference']
    assert reference_ecef(value)[-1], dataset
    return value

def q6_only(data,reference):
    result={}
    for s in data:
        if s['Q']!='6':
            continue
        t=key(s)
        assert t not in result
        result[t]=(int(s['week'])*604800+float(s['tow']),*enu([float(s[k]) for k in XYZ],reference))
    return result

def window(points):
    e,n,u=list(zip(*(x[1:] for x in points))) if points else ((),(),())
    return dict(n=len(points), E_mean_m=mean(e) if e else None, N_mean_m=mean(n) if n else None,
                U_mean_m=mean(u) if u else None,
                H_rms_m=sqrt(mean(a*a+b*b for a,b in zip(e,n))) if e else None,
                U_rms_m=sqrt(mean(a*a for a in u)) if u else None)

def metrics(points):
    pts=list(points)
    end=pts[-1][0] if pts else None
    tail=[p for p in pts if end-p[0]<60.0] if end is not None else []
    groups={'first20':window(pts[:20]),'all':window(pts),'last60':window(tail)}
    return dict(q6=len(pts), first20_H_rms_m=groups['first20']['H_rms_m'],
                first20_U_rms_m=groups['first20']['U_rms_m'],U_at_q6_20_m=pts[19][3] if len(pts)>=20 else None,
                all_H_rms_m=groups['all']['H_rms_m'],all_U_rms_m=groups['all']['U_rms_m'],
                **{f'last60_{k}':v for k,v in groups['last60'].items()})

def actions(path, q6, mask, reference):
    satrows=[]
    closure={}
    profile_errors=0
    unexpected_fix=0
    failures=Counter()
    phi,lam,_,_=reference_ecef(reference)
    up=(cos(phi)*cos(lam), cos(phi)*sin(lam), sin(phi))
    with path.open(encoding='utf-8',errors='replace') as trace:
        for line in trace:
            if '$PPP_FAILURE,' in line:
                reason=re.search(r'reason=([^,]+)',line)
                failures[reason.group(1) if reason else 'unknown']+=1
            if '$STEP4_INVALID_PROFILE' in line:
                profile_errors+=1
            if '$STEP4_CLOSURE,' in line:
                fields=line.strip().split('$STEP4_CLOSURE,',1)[1].split(',')
                t=int(fields[0])*604800+round(float(fields[1]))
                assert t not in closure, (path,t)
                closure[t]=max(abs(float(x)) for x in fields[3:])
            if '$STEP4_CODE,' not in line:
                continue
            fields=line.strip().split('$STEP4_CODE,',1)[1].split(',')
            assert len(fields)==18,(path,fields)
            week, tow, trial, sat, sig, slot, v, base, effective, m1, m2, m3, m1_gim, drift, m3_gim, *dxyz=fields
            t=int(week)*604800+round(float(tow))
            a,b,c=map(float,(m1,m2,m3))
            assert all(f>=1. for f in (a,b,c))
            assert (mask&1 or a==1.) and (mask&2 or b==1.) and (mask&4 or c==1.)
            assert a<=64. and b in (1.,3.,4.,12.) and c<=36.
            assert isclose(float(base)*a*b*c,float(effective),rel_tol=2e-15,abs_tol=1e-12)
            assert (float(drift)>1.8)==(c>1.)
            if t in q6:
                satrows.append(dict(epoch=t,week=int(week),tow=float(tow),sat=sat,signal=sig,slot=int(slot)+1,
                    trial=int(trial),v_P_m=float(v),R_before_m2=float(base),R_effective_m2=float(effective),
                    M1=a,M2=b,M3=c,total_multiplier=a*b*c, M1_uses_gim=bool(int(m1_gim)),
                    cmc_drift_m=float(drift),M3_uses_gim=bool(int(m3_gim)),
                    Kv_U_m=sum(x*float(y) for x,y in zip(up,dxyz))))
    assert profile_errors==0
    assert set(q6)<=closure.keys(), (path,set(q6)-closure.keys())
    maximum=max(closure.values(),default=0.)
    assert maximum<1e-7,(path,maximum)
    assert len({(r['epoch'],r['sat'],r['signal'],r['slot']) for r in satrows})==len(satrows)
    return satrows,dict(max_abs_xyz_kv_closure_m=maximum,committed_updates=len(closure),
                        trace_failure_reasons=dict(failures),audited_code_rows_in_Q6=len(satrows))

def action_summary(datasets, weight):
    summary=[]
    row_detail=[]
    for dataset,signals in FOCUS.items():
        history={c:list(datasets[dataset,c]) for c in ('Baseline','M123')}
        common=[t for t in history['Baseline'] if t in datasets[dataset,'M123']][:20]
        for sat,signal in signals:
            results={}
            for c in ('Baseline','M123'):
                series=[r for r in weight[dataset,c] if (r['sat'],r['signal'])==(sat,signal)]
                ordinal={t:i+1 for i,t in enumerate(history[c])}
                for r in series:
                    row_detail.append(dict(dataset=dataset,scheme=c,q6_index=ordinal[r['epoch']],**r))
                first=[r for r in series if ordinal[r['epoch']]<=20]
                simultaneous=[r for r in series if r['epoch'] in common]
                results[c]=dict(all_rows=len(series),first20_rows=len(first),first20_Kv_U_m=sum(r['Kv_U_m'] for r in first),
                                common_first20_rows=len(simultaneous),common_first20_Kv_U_m=sum(r['Kv_U_m'] for r in simultaneous))
                if c=='M123':
                    for window_label,window_rows in [('all',series),('first20',first)]:
                        for mode in MODES:
                            jump=[r[mode] for r in window_rows if r[mode]>1.]
                            results[c].update({f'{window_label}_{mode}_count':len(jump),
                                f'{window_label}_{mode}_mean':mean(jump) if jump else None,
                                f'{window_label}_{mode}_max':max(jump) if jump else None})
                        total=[r['total_multiplier'] for r in window_rows if r['total_multiplier']>1.]
                        results[c].update({f'{window_label}_any_count':len(total),
                            f'{window_label}_total_mean':mean(total) if total else None,
                            f'{window_label}_total_max':max(total) if total else None})
            row={'dataset':dataset,'sat':sat,'signal':signal,'first20_common_q6':len(common)}
            for c,fields in results.items():
                row.update({f'{c}_{k}':v for k,v in fields.items()})
            row['first20_Kv_U_delta_m']=row['M123_first20_Kv_U_m']-row['Baseline_first20_Kv_U_m']
            summary.append(row)
    return summary,row_detail

LABELS={
    '1120_vivo':'11/14 11:20 vivo', '1120_xiaomi':'11/14 11:20 小米',
    '1004_vivo':'11/14 10:04 vivo', '1004_xiaomi':'11/14 10:04 小米',
    '1031_xiaomi_V1':'10/31 小米 V1', '1031_xiaomi_V2':'10/31 小米 V2',
}
def fmt(x):
    return '–' if x is None else f'{x:.3f}'

def markdown_metrics(data,scenario=True):
    title='| 数据集 | 方案 | Q6 | 前20 H/U | 第20 U | 全段 H/U | 末60秒 E/N/U 均值 | 末60秒 H/U |'
    alignment='|---|---|---:|---:|---:|---:|---:|---:|'
    lines=[title,alignment]
    for row in data:
        entry=[LABELS[row['dataset']], row['case'],str(row['q6']),
               '/'.join(fmt(row[k]) for k in ('first20_H_rms_m','first20_U_rms_m')),
               fmt(row['U_at_q6_20_m']),'/'.join(fmt(row[k]) for k in ('all_H_rms_m','all_U_rms_m')),
               '/'.join(fmt(row[f'last60_{k}_mean_m']) for k in 'ENU'),
               '/'.join(fmt(row[k]) for k in ('last60_H_rms_m','last60_U_rms_m'))]
        lines.append('| '+' | '.join(entry)+' |')
    return '\n'.join(lines)

def markdown_actions(data):
    begin=['| 数据集 | 星/信号 | M1 次数·均值/最大 | M2 次数·均值/最大 | M3 次数·均值/最大 | 前20期 U 基线→联合（m） |',
           '|---|---|---:|---:|---:|---:|']
    for row in data:
        entry=[LABELS[row['dataset']],f"{row['sat']} {row['signal']}"]
        for m in MODES:
            n=row[f'M123_all_{m}_count']
            entry.append(str(n)+(f" · {row[f'M123_all_{m}_mean']:.2f}/{row[f'M123_all_{m}_max']:.2f}" if n else ''))
        entry.append(f"{row['Baseline_first20_Kv_U_m']:+.3f} → {row['M123_first20_Kv_U_m']:+.3f}")
        begin.append('| '+' | '.join(entry)+' |')
    return '\n'.join(begin)

def main():
    guard=read(OUT/'input_guard_sha256.json')
    assert all(sha(Path(p))==d for p,d in guard.items())
    statistics,common,baseline_cohort,audits,historical=[],[],[],[],[]
    q6_cache={}
    codes={}
    refs={d:ref(d) for d in DATASETS}
    for d,(command,historical_path) in DATASETS.items():
        control=RUNS/d/'FormalControl'
        csol=rows(control/'solution.csv')
        ssr_sha,obs_sha=(sha(control/p) for p in ('corrections.csv','observations.csv'))
        assert sorted({r['Q'] for r in csol}) in (['0','6'],['0','5','6'])
        old=rows(historical_path/'solution.csv')
        hq=q6_only(old,refs[d])
        historical.append(dict(dataset=d,historical_solution_equal=untimed(old)==untimed(csol),**metrics(hq.values())))
        for c,mask in CONFIGS.items():
            path=RUNS/d/c
            data=rows(path/'solution.csv')
            counts=Counter(r['Q'] for r in data)
            assert set(counts)<= {'0','5','6'}, (d,c,counts)
            assert [(r['week'],r['tow']) for r in data]==[(r['week'],r['tow']) for r in csol]
            assert ssr_sha==sha(path/'corrections.csv') and obs_sha==sha(path/'observations.csv')
            identical=untimed(csol)==untimed(data)
            if c=='Baseline':
                assert identical, (d,c)
                assert sha(path/'solution.stat')==sha(control/'solution.stat')
            q6=q6_only(data,refs[d])
            q6_cache[d,c]=q6
            codes[d,c],audit=actions(path/'solution.trace',q6,mask,refs[d])
            audits.append(dict(dataset=d,case=c,quality=dict(counts),causal_prefix_identical=True,
                               observations_identical=True,formal_solution_equal=identical,**audit))
            statistics.append(dict(dataset=d,case=c,Q0=counts['0'],Q5=counts['5'],**metrics(q6.values())))
    for window in ('1120','1004'):
        devices=[window+'_'+d for d in ('vivo','xiaomi')]
        base_common=set(q6_cache[devices[0],'Baseline'])&set(q6_cache[devices[1],'Baseline'])
        for c in CONFIGS:
            ts=sorted(set(q6_cache[devices[0],c])&set(q6_cache[devices[1],c]))
            for d in devices:
                common.append(dict(dataset=d,case=c,**metrics(q6_cache[d,c][t] for t in ts)))
                ts_matched=[t for t in ts if t in base_common]
                baseline_cohort.append(dict(dataset=d,case=c,**metrics(q6_cache[d,c][t] for t in ts_matched)))
    action,detail=action_summary(q6_cache,codes)
    write_csv('accuracy_all_q6.csv',statistics)
    write_csv('accuracy_dual_common_q6.csv',common)
    write_csv('accuracy_dual_baseline_and_candidate_common_q6.csv',baseline_cohort)
    write_csv('mechanism_action_summary.csv',action)
    write_csv('target_committed_code_actions.csv',detail)
    write_csv('historical_baseline_comparison.csv',historical)
    save(OUT/'verification.json',dict(formal_input_guard_files=len(guard),formal_baseline_exact_cases=6,
          raw_and_ssr_equal_all_cases=True,probe_sha256=sha(OUT/'step4_probe.exe'),
          observation_uses_reference=False,replay_count=len(audits),audits=audits))
    tables='# 各方案 Q6 精度（m）\n\n'+markdown_metrics(statistics)
    tables+='\n\n# 11/14 双机共有 Q6 精度（m）\n\n'+markdown_metrics(common)
    tables+='\n\n# 联合方案动作与实际高程增量\n\n'+markdown_actions(action)+'\n'
    (OUT/'TERMINAL_TABLES.md').write_text(tables,encoding='utf-8')
    print(tables)
    print(f'PASS: {len(audits)} cases, 6 exact formal controls and {len(guard)} input/source guards')

if __name__=='__main__':
    main()
