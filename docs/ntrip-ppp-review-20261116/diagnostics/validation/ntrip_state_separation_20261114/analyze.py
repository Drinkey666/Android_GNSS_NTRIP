"""Inspect committed uncombined PPP matrices without changing any estimate."""
import csv
import gzip
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]


def ecef(lat_deg, lon_deg, height):
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    a, e2 = 6378137.0, 6.6943799901413165e-3
    n = a / math.sqrt(1 - e2 * math.sin(lat)**2)
    return np.array([(n + height) * math.cos(lat) * math.cos(lon),
                     (n + height) * math.cos(lat) * math.sin(lon),
                     (n * (1 - e2) + height) * math.sin(lat)])


def geometry(lat, lon, height):
    a, b = math.radians(lat), math.radians(lon)
    return ecef(lat, lon, height), np.array([
        [-math.sin(b), math.cos(b), 0],
        [-math.sin(a)*math.cos(b), -math.sin(a)*math.sin(b), math.cos(a)],
        [math.cos(a)*math.cos(b), math.cos(a)*math.sin(b), math.sin(a)]])


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def commits(path):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf8') as stream:
        for line in stream:
            event = json.loads(line)
            name = event['event']
            if name == 'EPOCH':
                config, trials, stages = event, defaultdict(dict), {}
            elif name == 'COMMITTED':
                yield config, trials[event['trial']], stages, event
            elif 'data' in event:
                trials[event['trial']][name] = np.array(event['data']).reshape((event['nr'],event['nc']), order='F')
            elif name in ('ROWS', 'FILTER_CALL'):
                trials[event['trial']][name] = event
            elif 'x' in event and name != 'TRIAL_POSTERIOR':
                stages[name] = event


def projection(target, nuisance):
    if nuisance.shape[1] == 0:
        return target, 0
    u, singular, _ = np.linalg.svd(nuisance, full_matrices=False)
    rank = int(np.count_nonzero(singular > singular[0] * 1e-10)) if len(singular) else 0
    q = u[:, :rank]
    return target - q @ (q.T @ target), rank


def classify(meta):
    if meta['group'] == 'CLOCK':
        return ('GPS clock','GLO ISB','Galileo ISB','BeiDou ISB','IRNSS ISB')[meta['index'] - 3]
    if meta['group'] == 'RCB':
        return ('GPS 5Q','Galileo 5Q','BeiDou 7I','BeiDou 5P','BeiDou 1P')[meta['rcb_slot']]
    return meta['sat'] + (':' + meta['signal'] if meta['signal'] else '') or meta['group']


def examine(config, trial, stages, final, origin, rot, solution):
    active = trial['FILTER_CALL']['active_indices']
    states = [dict(config['states'][i]) for i in active]
    rcb0 = next(s['index'] for s in config['states'] if s['group'] == 'RCB')
    for s in states:
        if s['group'] == 'RCB':
            s['rcb_slot'] = s['index'] - rcb0
    p = [active.index(i) for i in range(3)]
    H, R, P, Pplus = (trial[k] for k in ('H_ACTIVE','R','P_MINUS_ACTIVE','P_PLUS_ACTIVE'))
    x, xp, v = (trial[k].ravel() for k in ('X_MINUS_ACTIVE','X_PLUS_ACTIVE','V'))
    tow = float(solution['tow'])
    assert final['time'].endswith(f'{round(tow,3)%60:06.3f}'), (final['time'], tow)
    assert np.linalg.norm(xp[p] - np.array([float(solution[k]) for k in ('x_m','y_m','z_m')])) < 1e-7
    dx = xp - x
    assert np.max(abs(dx - trial['K'] @ v)) < 1e-7
    items = trial['ROWS']['rows']
    measurement_classes = [r['class'] for r in items]
    group_indices = {name:[i for i,s in enumerate(states) if s['group']==name]
                     for name in ('CLOCK','ZTD','RCB','IONO','AMBIGUITY')}
    sigma = float(np.sqrt(rot[2] @ Pplus[np.ix_(p,p)] @ rot[2]))
    up_cross = Pplus[:,p] @ rot[2]
    # Conditional state displacement for +1 m in Up under the saved posterior.
    along_up = up_cross / sigma**2
    p_row = rot[2] @ trial['K'][p,:]
    # Frozen linearization: a shifted prior mean also shifts its prefit v.
    up_prior_response = -p_row @ H.T
    up_prior_response[p] += rot[2]
    response = {}
    for system, prefix in (('GPS','G'),('Galileo','E'),('BeiDou','C')):
        ion_idx = [i for i in group_indices['IONO'] if states[i]['sat'].startswith(prefix) and np.any(H[i,:])]
        response[system+'_ion_initial_m_per_m'] = float(sum(up_prior_response[ion_idx]))
        ion_rows = [j for j,row in enumerate(items) if row['class']=='IONO_PRIOR' and row['sat'].startswith(prefix)]
        response[system+'_ion_product_rows_m_per_m'] = float(sum(p_row[ion_rows]))
    for g in ('CLOCK','ZTD','RCB'):
        for i in group_indices[g]:
            if np.any(H[i,:]):
                response[classify(states[i])+'_initial_m_per_m'] = float(up_prior_response[i])
    active_rows = []
    for i,s in enumerate(states):
        if i in p or not np.any(H[i,:]):
            continue
        lab = classify(s)
        adjustment = {k:float(sum(trial['K'][i,j]*v[j] for j,c in enumerate(measurement_classes) if c==k))
                      for k in sorted(set(measurement_classes))}
        active_rows.append(dict(state=lab, group=s['group'], satellite=s['sat'], signal=s['signal'],
                                prior=float(x[i]), post=float(xp[i]), change=float(dx[i]),
                                prior_sigma=math.sqrt(P[i,i]), posterior_sigma=math.sqrt(Pplus[i,i]),
                                rho_up=float(up_cross[i]/sigma/math.sqrt(Pplus[i,i])) if Pplus[i,i]>0 else None,
                                conditional_change_per_up_m=float(along_up[i]), by_observation_class=adjustment))
    bands = defaultdict(set)
    for row in items:
        if row['class']=='GNSS_CODE':
            bands[row['sat']].add(row['signal'])
    phase_bands = {(r['sat'],r['signal']) for r in items if r['class']=='GNSS_PHASE'}
    single_band_ion_ambiguity_null = []
    for sat, signals in bands.items():
        if len(signals)!=1:
            continue
        jj = [j for j,r in enumerate(items) if r['sat']==sat and r['class'].startswith('GNSS_')]
        ion_i = next((i for i in group_indices['IONO'] if states[i]['sat']==sat),None)
        if ion_i is None:
            continue
        # Locally keep a +1 m Up move invisible to this satellite by letting
        # its ionosphere and carrier ambiguity offsets float freely.
        amb_i = [i for i in group_indices['AMBIGUITY'] if states[i]['sat']==sat]
        h_up = H[p,:].T @ rot[2]
        a = H[np.ix_([ion_i]+amb_i,jj)].T
        coeff = np.linalg.lstsq(a,-h_up[jj],rcond=1e-10)[0]
        single_band_ion_ambiguity_null.append(dict(sat=sat,code=next(iter(signals)),
            rows=len(jj),iono=float(coeff[0]),max_residual_m=float(max(abs(a @ coeff + h_up[jj])))))
    high = H[p,:].T @ rot.T
    combos = [(), ('CLOCK',), ('CLOCK','ZTD'), ('CLOCK','RCB'), ('CLOCK','ZTD','RCB'), ('CLOCK','ZTD','RCB','IONO'),
              ('CLOCK','ZTD','RCB','IONO','AMBIGUITY')]
    observability = {}
    for label,which in (('code', [i for i,k in enumerate(measurement_classes) if k=='GNSS_CODE']),
                        ('gnss', [i for i,k in enumerate(measurement_classes) if k.startswith('GNSS_')]),
                        ('including_product_rows', list(range(len(items))))):
        L = np.linalg.cholesky(R[np.ix_(which,which)])
        b = np.linalg.solve(L, high[which,2])
        en = np.linalg.solve(L, high[which,:2])
        aw = np.linalg.solve(L, H.T[which,:])
        full = np.linalg.norm(b)
        for groups in combos:
            free = [i for g in groups for i in group_indices[g]]
            res, rank = projection(b,np.column_stack((en,aw[:,free])))
            remaining = float(np.linalg.norm(res))
            observability[label+'|'+('+'.join(groups) or 'EN_ONLY')] = dict(
                fraction=float(remaining/full), weighted_up_sensitivity=remaining,
                nuisance_rank=rank, rows=len(which))
    return dict(tow=tow, epoch_index=config['epoch'],
                prior_enu=(rot @ (x[p]-origin)).tolist(), post_enu=(rot @ (xp[p]-origin)).tolist(),
                posterior_sigma_up=sigma, clock_from_before_seed=float(stages['BEFORE_CLOCK_SEED']['x'][3]),
                clock_filter_input=float(x[active.index(3)]), measurement_counts=dict(Counter(measurement_classes)),
                satellites_single_code=sum(len(v)==1 for v in bands.values()),
                satellites_multiple_codes=sum(len(v)>1 for v in bands.values()),
                multiple_code_satellites=sorted(k for k,v in bands.items() if len(v)>1),
                phase_satellite_signal_count=len(phase_bands),
                single_band_ion_ambiguity_null=single_band_ion_ambiguity_null,
                frozen_up_response=response,
                states=active_rows, observability=observability)


def main():
    v = ROOT/'validation'
    xiaomi = v/'android_capture_20261114/accuracy_gap'
    if len(sys.argv) != 2:
        raise SystemExit("usage: analyze.py references.json")
    references = read(Path(sys.argv[1]))
    datasets = {
        'vivo_1120': (v/'vivo_capture_20261114/error_attribution', references['vivo_1120'], 'gain.jsonl'),
        'xiaomi_1120': (xiaomi/'11_20_matrix', references['xiaomi_1120'], 'gain.jsonl'),
        'xiaomi_1004': (xiaomi/'10_04_matrix', references['xiaomi_1004'], 'gain.jsonl'),
        'xiaomi_1031': (v/'ntrip_formal_en_20261107_v3/run', references['xiaomi_1031'], 'gain.jsonl.gz'),
    }
    results = {}
    for name,(directory, ref, filename) in datasets.items():
        origin,rot = geometry(*ref)
        with (directory/'solution.csv').open(newline='') as f:
            valid = [r for r in csv.DictReader(f) if r['Q']=='6']
        entries = [examine(cfg,tr,st,end,origin,rot,valid[i])
                   for i,(cfg,tr,st,end) in enumerate(commits(directory/filename))]
        results[name] = entries
        for i in sorted({0,min(4,len(entries)-1),min(17,len(entries)-1),min(19,len(entries)-1)}):
            e=entries[i]
            print(name,i,e['tow'],'up',round(e['post_enu'][2],3), 'sigma', round(e['posterior_sigma_up'],3),
                  'codes 1+2',e['satellites_single_code'],e['satellites_multiple_codes'],
                  {k:round(s['fraction'],4) for k,s in e['observability'].items() if k.startswith('gnss')})
        print('first coupled states',name,[(s['state'],round(s['change'],3),round(s['rho_up'],3),round(s['conditional_change_per_up_m'],3))
                                           for s in entries[0]['states'] if s['group'] in ('CLOCK','ZTD','RCB')])
    (OUT/'states.json').write_text(json.dumps(results,indent=2),encoding='utf8')


if __name__=='__main__':
    main()
