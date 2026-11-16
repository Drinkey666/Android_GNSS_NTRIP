import hashlib
import json
import math

from analyze import HERE, read, rows


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def check(table, side, run, input_path):
    from pathlib import Path

    old=Path(table[side])/'pc_replay'
    base,test=[rows(p/'solution.csv') for p in (old,run)]
    assert [(r['week'],r['tow'],r['Q']) for r in base]==[(r['week'],r['tow'],r['Q']) for r in test]
    assert (old/'corrections.csv').read_bytes()==(run/'corrections.csv').read_bytes()
    a,b=[rows(p/'observations.csv') for p in (old,run)]
    assert len(a)==len(b)
    receipt=read(old/'replay.json')
    assert all(sha(Path(v))==receipt['input_sha256'][k] for k,v in receipt['input_files'].items())
    if input_path is None:
        assert a==b and all(all(x[k]==y[k] for k in x if k!='processing_ms') for x,y in zip(base,test))
        return dict(control=True,epochs=len(test),observations=len(b))
    planned, applied=[rows(p) for p in (input_path,run/'applied.csv')]
    assert len(planned)==len(applied)
    key=lambda r: (r['week'],r['tow'],r['sat'],r['signal'])
    deltas={}
    for p,r in zip(planned,applied):
        assert (p['week'],p['target_tow'],p['sat'],p['signal'])==key(r)
        assert float(p['delta_m'])==float(r['delta_m'])
        assert abs(float(r['transferred_P_m'])-float(r['original_P_m'])-float(r['delta_m']))<1e-8
        assert key(r) not in deltas
        deltas[key(r)]=float(r['delta_m'])
    for x,y in zip(a,b):
        assert all(x[k]==y[k] for k in x if k!='P_m')
        delta=deltas.get(key(x),0.0)
        assert abs(float(y['P_m'])-float(x['P_m'])-delta)<0.000101
    markers=('filter error','FILTER_NAN','FILTER_NOT_PSD','PRIVATE_CODE_SWAP_INPUT_MISMATCH')
    with (run/'solution.trace').open() as f:
        failures=sum(any(k in l for k in markers) for l in f)
    assert not failures
    return dict(epochs=len(test),observations=len(b),applied=len(applied),
                printed_code_values_changed=sum(x['P_m']!=y['P_m'] for x,y in zip(a,b)),
                numeric_failure_lines=failures,ssr_diagnostics_byte_identical=True,only_P_m_changed=True)


if __name__=='__main__':
    tables=read(HERE/'matched/pairing.json')
    result={}
    for table in tables:
        for side in ('vivo','xiaomi'):
            stem=table['window']+'_'+side
            result[stem]=check(table,side,HERE/'replays'/stem,HERE/'matched'/f'{stem}.csv')
            if table['window']=='1120':
                for group in ('bds','gps_galileo'):
                    p=HERE/'group_split'/group/stem
                    result[group+'_'+stem]=check(table,side,p,p/'input.csv')
    result['1120_vivo_control']=check(tables[0],'vivo',HERE/'replays/1120_vivo_control',None)
    (HERE/'verified.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(result))
