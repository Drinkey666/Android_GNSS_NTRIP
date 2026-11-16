import csv
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path


HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
from evaluate_solution import enu


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def calc(entries):
    if not entries:
        return None
    return dict(count=len(entries),
                H_rms=math.sqrt(statistics.mean(e[0]**2+e[1]**2 for e in entries)),
                U_rms=math.sqrt(statistics.mean(e[2]**2 for e in entries)),
                mean_enu=[statistics.mean(v) for v in zip(*entries)],
                first_enu=entries[0],last_enu=entries[-1])


def evaluation(table, side, run_dir):
    case=Path(table[side]); original=case/'pc_replay'; run=run_dir/(table['window']+'_'+side)
    ref=read(case/'imported/capture.json')['reference']
    base, candidate=[rows(p/'solution.csv') for p in (original,run)]
    assert [(r['week'],r['tow']) for r in base]==[(r['week'],r['tow']) for r in candidate]
    field=lambda r: enu(tuple(float(r[k]) for k in ('x_m','y_m','z_m')),ref) if r['Q']=='6' else None
    paired=[(r['tow'],field(r),field(s)) for r,s in zip(base,candidate) if r['Q']==s['Q']=='6']
    any_edited={round(float(r['tow'])) for r in rows(run/'applied.csv')}
    only_edited=[x for x in paired if round(float(x[0])) in any_edited]
    first, last=map(float,(paired[0][0],paired[-1][0]))
    res=dict(counts=[dict(Counter(r['Q'] for r in data)) for data in (base,candidate)],
             changed_quality_epochs=sum(r['Q']!=s['Q'] for r,s in zip(base,candidate)),
             first_q6=[next(r['tow'] for r in data if r['Q']=='6') for data in (base,candidate)],
             paired={label:[calc([x[i] for x in group]) for i in (1,2)] for label,group in (
                 ('all',paired),('swapped_epochs',only_edited),('first20',paired[:20]),
                 ('first30_seconds',[x for x in paired if float(x[0])-first<30]),
                 ('last60',paired[-60:]),('last60_seconds',[x for x in paired if last-float(x[0])<60]))})
    return res


if __name__=='__main__':
    run=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else HERE/'replays'
    summary={t['window']:{side:evaluation(t,side,run) for side in ('vivo','xiaomi')}
             for t in read(HERE/'matched/pairing.json')}
    (run/'results.json').write_text(json.dumps(summary,indent=2),encoding='utf8')
    for window,sides in summary.items():
        for side,r in sides.items():
            print(window,side,'Q',r['counts'],'first',r['first_q6'])
            for k in ('all','swapped_epochs','first20','last60'):
                print(k,[(q['count'],round(q['H_rms'],3),round(q['U_rms'],3),round(q['mean_enu'][2],3),
                           round(q['first_enu'][2],3),round(q['last_enu'][2],3)) for q in r['paired'][k]])
