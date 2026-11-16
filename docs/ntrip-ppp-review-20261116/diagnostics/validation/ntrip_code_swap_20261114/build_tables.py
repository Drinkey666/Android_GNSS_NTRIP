"""Build paired, clock-centred pseudorange transfers from saved raw-code probes."""
import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


OUT = Path(__file__).resolve().parent
V = OUT.parent


def rows(path):
    with path.open(newline='', encoding='utf8') as f:
        return list(csv.DictReader(f))


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def model(directory):
    out = {}
    for r in rows(directory/'model.csv'):
        if r['cbias_status']!='2' or not math.isfinite(float(r['code_closure'])):
            continue
        if any(r[k]!='1' for k in ('signal_pco_ok','signal_pcv_ok','ref_status')):
            continue
        key = (int(r['week']), round(float(r['tow'])), r['sat'], r['signal'])
        assert key not in out
        out[key] = r
    return out


def same_product(a, b):
    for k in ('orbit_iod','clock_iod','bias_iod','orbit_provider','clock_provider','bias_provider',
              'orbit_solution','clock_solution','bias_solution','ssr_iode','ref_code1','ref_code2','hz'):
        if a[k]!=b[k]:
            return False
    dt = float(a['tow'])-float(b['tow'])
    if abs(dt)>.005 or abs(float(a['cbias'])-float(b['cbias']))>1e-6:
        return False
    return all(abs(float(a[k])-float(b[k])-dt)<1e-6 for k in ('orbit_age_s','clock_age_s','bias_age_s'))


def select_model_pair(window, a, b):
    refs = [load(x/'imported/products.json')['products'] for x in (a,b)]
    assert {k:v['sha256'] for k,v in refs[0].items()} == {k:v['sha256'] for k,v in refs[1].items()}
    x = V/'android_capture_20261114/accuracy_gap'/('11_20' if window=='1120' else '10_04')
    y = V/'vivo_capture_20261114/error_attribution' if window=='1120' else V/'ntrip_code_history_20261114/vivo_1004'
    return x,y


def tables(window, xcase, vcase, output):
    x, y = map(model, select_model_pair(window,xcase,vcase))
    same = x.keys() & y.keys()
    accepted = defaultdict(list)
    rejected = 0
    for key in sorted(same):
        a, b = x[key], y[key]
        if not same_product(a,b):
            rejected += 1
            continue
        week, second, sat, sig = key
        diff = float(b['code_closure'])-float(a['code_closure'])
        accepted[week,second,sat[0],sig].append((key,diff))
    records = []
    gross = 0
    for pairs in accepted.values():
        if len(pairs)<4:
            continue
        center = median(delta for _,delta in pairs)
        clean = [(key,delta) for key,delta in pairs if abs(delta-center)<=100]
        gross += len(pairs)-len(clean)
        if len(clean)<4:
            continue
        center = median(delta for _,delta in clean)
        for key, delta in clean:
            records.append((key, delta-center, center))
    counts = Counter(k[2][0]+':'+k[3] for k,_,_ in records)
    for side, lookup, sign in (('xiaomi',x,1),('vivo',y,-1)):
        with (output/f'{window}_{side}.csv').open('x',newline='',encoding='ascii') as f:
            w = csv.writer(f)
            w.writerow(('week','second','sat','signal','target_tow','target_P_m','delta_m','group_common_removed_m'))
            for key, delta, center in sorted(records):
                r=lookup[key]
                w.writerow((*key,r['tow'],r['raw_p'],f'{sign*delta:.9f}',f'{sign*center:.9f}'))
    return dict(window=window,xiaomi=str(xcase),vivo=str(vcase), common_probe_rows=len(same),
                product_or_epoch_mismatch_rows=rejected, gross_mismatch_rows=gross, transferred_rows=len(records),
                transferred_epochs=len({k[:2] for k,_,_ in records}), transferred_by_group=dict(counts),
                max_epoch_dt_s=max(abs(float(x[k]['tow'])-float(y[k]['tow'])) for k,_,_ in records),
                max_abs_delta_m=max(abs(d) for _,d,_ in records))


if __name__=='__main__':
    output = OUT / sys.argv[1]
    output.mkdir(exist_ok=False)
    x=V/'android_capture_20261114'
    y=V/'vivo_capture_20261114'
    result=[tables(tag,next(x.glob('Capture_20261114_'+a+'*')),next(y.glob('Capture_20261114_'+b+'*')),output)
            for tag,a,b in (('1120','112003','111957'),('1004','100413','100411'))]
    (output/'pairing.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))
