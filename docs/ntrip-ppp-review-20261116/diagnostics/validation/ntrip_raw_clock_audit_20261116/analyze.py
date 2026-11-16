"""Trace exchanged GPS/Galileo pseudoranges back to Android raw fields."""
import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from statistics import median


HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'ntrip_code_swap_20261114'
WEEK_NS = 604800_000_000_000
METRES_PER_NS = Decimal('0.299792458')


def rows(path):
    with path.open(newline='', encoding='utf-8-sig') as source:
        return list(csv.DictReader(source))


def raw_index(case):
    imported = case / 'imported'
    anchors = rows(imported / 'clock_anchors.csv')
    clocks = {}
    previous = None
    for row in anchors:
        time = int(row['time_nanos'])
        hcdc = int(row['hcdc'])
        if previous is None or time < previous[0] or hcdc != previous[1]:
            anchor = None
        previous = time, hcdc
        if anchor is None and row['full_bias_nanos']:
            anchor = int(row['full_bias_nanos']), Decimal(row['bias_nanos'] or '0')
        if anchor is not None:
            assert (time, hcdc) not in clocks
            clocks[time, hcdc] = anchor
    output = defaultdict(list)
    with next(imported.glob('RawData_*.txt')).open(newline='', encoding='utf-8-sig') as source:
        for line, r in enumerate(csv.reader(source), start=1):
            if len(r) < 37 or r[0] != 'Raw' or r[28] not in ('1','6') or not r[14] or not r[22]:
                continue
            frequency = float(r[22])
            if abs(frequency - 1575420000) < 10000 and r[35] == 'C':
                signal = '1C'
            elif abs(frequency - 1176450000) < 10000 and r[35] == 'Q' and r[28] == '6':
                signal = '5Q'
            else:
                continue
            time, hcdc = int(r[2]), int(r[10])
            if (time,hcdc) not in clocks:
                continue
            full_bias, bias = clocks[time,hcdc]
            offset = Decimal(r[12] or '0')
            rx = Decimal(time - full_bias) - bias + offset
            week = int(rx // WEEK_NS)
            tow = rx - week * WEEK_NS
            travel = tow - int(r[14])
            if travel > WEEK_NS // 2:
                travel -= WEEK_NS
            if travel < -WEEK_NS // 2:
                travel += WEEK_NS
            sat = ('G' if r[28] == '1' else 'E') + f'{int(r[11]):02d}'
            output[(week, round(tow / 1_000_000_000), sat, signal)].append(dict(
                line=line, code_m=float(travel * METRES_PER_NS), state=int(r[13]), adr_state=int(r[19]),
                tx_ns=int(r[14]), offset_ns=float(offset), uncertainty_ns=float(r[15]) if r[15] else None,
                cn0=float(r[16]), clock_segment_count=hcdc, tow_s=float(tow / 1_000_000_000)))
    return output


def key(r):
    return int(r['week']), int(r['second']), r['sat'], r['signal']


def lookup(index, r):
    candidates = index[key(r)]
    err = lambda a: abs(a['code_m'] - float(r['target_P_m']))
    return min(candidates,key=err) if candidates else None


def audit(window, side, case):
    plan = rows(BASE/'matched'/f'{window}_{side}.csv')
    plan = [r for r in plan if r['sat'].startswith(('G','E'))]
    index = raw_index(case)
    groups = defaultdict(list)
    unmatched = []
    for r in plan:
        raw = lookup(index, r)
        if raw is None or abs(raw['code_m'] - float(r['target_P_m'])) > .0001:
            unmatched.append(dict(key=key(r), matched_raw=raw))
            continue
        groups[r['sat'][0]+':'+r['signal']].append(raw | dict(delta_m=float(r['delta_m'])))
    stats = {}
    for name,g in groups.items():
        stats[name] = dict(rows=len(g), median_cn0=median(r['cn0'] for r in g),
                           median_tx_uncertainty_ns=median(r['uncertainty_ns'] for r in g if r['uncertainty_ns'] is not None),
                           states=dict(Counter(r['state'] for r in g)),
                           adr_valid_no_reset_or_slip_ratio=sum((r['adr_state'] & 7)==1 for r in g)/len(g),
                           nonzero_offsets=sum(r['offset_ns']!=0 for r in g), distinct_hcdc=sorted({r['clock_segment_count'] for r in g}))
    error = [abs(lookup(index,r)['code_m']-float(r['target_P_m'])) for r in plan
             if index.get(key(r))]
    before = rows(BASE/f'{window}_{side}.csv')
    anomalies = []
    for r in before:
        if abs(float(r['delta_m'])) <= 100:
            continue
        raw = lookup(index, r)
        anomalies.append(dict(key=key(r), relative_delta_m=float(r['delta_m']),
                              replay_p_m=float(r['target_P_m']), matched_raw=raw))
    return dict(planned=len(plan), matched=len(plan)-len(unmatched), max_absolute_formula_difference_m=max(error),
                unmatched=unmatched, by_signal=stats, excluded_gross_rows=anomalies)


if __name__=='__main__':
    result = {t['window']+'_'+side:audit(t['window'],side,Path(t[side]))
              for t in json.loads((BASE/'matched/pairing.json').read_text(encoding='utf8')) for side in ('vivo','xiaomi')}
    (HERE/'results.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    for name,r in result.items():
        print(name,{k:v for k,v in r.items() if k!='unmatched'})
        print('unmatched examples',r['unmatched'][:2])
