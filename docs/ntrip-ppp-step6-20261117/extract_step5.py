
"""Extract fifth-stage committed rows and bootstrap evidence without replay."""
import csv,sys,math
from collections import defaultdict
from pathlib import Path

OUT=Path(__file__).resolve().parent
STEP5=OUT.parent/'brain_step5_east_and_m1v2'
sys.path.insert(0,str(STEP5))
from evaluate import dataset_reference,solve,read_trace,key
from run_replays import rows
from evaluate_solution import enu

def write(name,data):
    with (OUT/name).open('w',newline='',encoding='utf-8') as h:
        writer=csv.DictWriter(h,fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)
def startup():
    summary=[]
    for b in rows(STEP5/'state_transition_budget.csv'):
        d=b['dataset']
        if float(b['E_first_q6_before_measurement_m'])<=0:continue
        base=STEP5/'runs'/d/'Baseline'
        data=rows(base/'solution.csv')
        i=next(i for i,row in enumerate(data) if row['Q']=='6')
        first=data[i]
        first_idx=key(first['week'],first['tow'])
        prior=[r for r in data[:i] if r['Q']=='5']
        count_success=0
        bootstrap=0
        with (base/'solution.trace').open(encoding='utf-8',errors='replace') as f:
            for line in f:
                if '$SPP_CLOCK_CANDIDATE,ok=1,used_for_bootstrap=1' in line:
                    bootstrap+=1
                if '$S5_CLOSURE,' in line:
                    w,t,*_=line.split('$S5_CLOSURE,',1)[-1].strip().split(',')
                    if key(w,t)==first_idx:break
                    count_success+=1
        qp=prior[-1] if prior else None
        ref=dataset_reference(d)
        last_q5_e=enu([float(qp[k]) for k in ('x_m','y_m','z_m')],ref)[0] if qp else None
        e=float(b['E_first_q6_before_measurement_m'])
        summary.append(dict(dataset=d,week=first_idx[0],first_q6_second=first_idx[1],
          E_before_first_Q6_m=e,prior_exported_Q5=len(prior),committed_PPP_trials_before_Q6=count_success,
          bootstrap_spp_success_lines=bootstrap,last_Q5_E_m=last_q5_e,
          E_from_last_Q5_to_Q6_prior_m=e-last_q5_e if last_q5_e is not None else None,
          attribution_to_one_SPP_constellation='unavailable; no saved SPP accepted normal equations'))
    return summary

def gps():
    d='1004_xiaomi'
    base=STEP5/'runs'/d/'Baseline'
    reference=dataset_reference(d)
    q=solve(rows(base/'solution.csv'),reference)
    first=dict(list(q.items())[:60])
    trace,closure,_=read_trace(base/'solution.trace',first,reference,'Baseline')
    codes=defaultdict(set)
    data=defaultdict(list)
    for r in trace:
        if r['cls']==1 and r['sat'].startswith('G'):
            codes[(r['sat'],r['week'],r['second'])].add(r['signal'])
            if r['signal']=='1C':
                data[r['sat']].append(r)
    sums=[]
    for sat,records in data.items():
        df=sum('5Q' in codes[(sat,r['week'],r['second'])] for r in records)
        n=len(records)
        result=dict(sat=sat,rows_1C=n,single_1C_rows=n-df,dual_1C_5Q_rows=df)
        xyz=[sum(r[k] for r in records) for k in 'ENU']
        result.update(dict(zip(('E_Kv_m','N_Kv_m','U_Kv_m'),xyz)),norm_Kv_m=math.hypot(*xyz))
        sums.append(result)
    group=next(r for r in rows(STEP5/'signal_group_gain_and_meanP.csv') if r['dataset']==d and r['group']=='GPS 1C')
    for k in 'ENU':
        assert abs(sum(r[k+'_Kv_m'] for r in sums)-float(group['first60_'+k+'_Kv_m']))<1e-12
    ranking=sorted(sums,key=lambda r:-r['norm_Kv_m'])
    direction=[]
    for k,sign in [('E',1),('N',1),('U',-1)]:
        v=k+'_Kv_m'
        eligible=[r for r in sums if r[v]*sign>0]
        for i,r in enumerate(sorted(eligible,key=lambda r:-r[v]*sign)[:5],1):
            direction.append(dict(direction={('E',1):'E+',('N',1):'N+',('U',-1):'U-'}[k,sign],
                                  rank=i,**r))
    return [dict(rank_vector=i,**r) for i,r in enumerate(ranking,1)],direction

def main():
    starts=startup()
    ranking,direction=gps()
    write('pre_q6_init.csv',starts)
    write('gps1c_first60_satellites.csv',ranking)
    write('gps1c_first60_directional_rank.csv',direction)
    lines=['# 四包首个 Q6 更新前的东偏',
           '', '| 数据集 | 先验 E (m) | 首个 Q6 前 Q5 | 首个 Q6 前已提交 PPP | 最后 Q5 的 E (m) |',
           '|---|---:|---:|---:|---:|']
    for r in starts:
        e='—' if r['last_Q5_E_m'] is None else f"{r['last_Q5_E_m']:+.3f}"
        lines.append(f"| {r['dataset']} | {r['E_before_first_Q6_m']:+.3f} | {r['prior_exported_Q5']} | {r['committed_PPP_trials_before_Q6']} | {e} |")
    lines.extend(['','记录能区分 SPP 启动与已提交 Q5 的时间顺序。第五轮保存的逐行增益记录只覆盖 PPP，不能细分 SPP 多系统首码的东向贡献。正式启动 SPP 采用 GPS 1C、Galileo 1C 和北斗 2I 等通过准入的首槽码。', '',
           '# 10:04 小米 GPS 1C 前 60 个 Q6（按累计 ENU 向量模）','',
           '| 卫星 | 1C 单频期 | 1C+5Q 双频期 | E/N/U 的 K·v (m) |','|---|---:|---:|---:|'])
    for r in ranking[:5]:
        enu='/'.join(f"{r[k+'_Kv_m']:+.3f}" for k in 'ENU')
        lines.append(f"| {r['sat']} | {r['single_1C_rows']} | {r['dual_1C_5Q_rows']} | {enu} |")
    lines.extend(['','全部 GPS 1C 的逐星 E/N/U 求和与第五轮 +1.781/+3.106/−3.859 m 闭合。'])
    text='\n'.join(lines)+'\n'
    (OUT/'DIAGNOSIS.md').write_text(text,encoding='utf-8')
    print(text)

if __name__=='__main__':
    main()
