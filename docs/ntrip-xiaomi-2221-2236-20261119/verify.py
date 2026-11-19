"""Verify exact epoch pairing, product provenance, field gaps and independent position estimates."""
import collections,csv,datetime,hashlib,json,math,statistics
from decimal import Decimal
from pathlib import Path
from analyze import arm,d,err,key,metrics,rows,runs
from experiments import BIA,ROOT
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def flags(rs):return [(key(x),x['Q']) for x in rs]
def positions(rs):return [tuple(x[k] for k in ('week','tow','Q','ns','nobs','x_m','y_m','z_m')) for x in rs]
def measure(a,keys):return metrics([a[t] for t in keys if t in a])
def closure(path):
    out={}
    with path.open() as f:
        for line in f:
            if '$S13_CLOSURE,' not in line:continue
            _,w,t,_,x,y,z=line.strip().split(',')
            out[int(w)*604800+Decimal(t)]=math.hypot(float(x),float(y),float(z))
    return out
def put(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def write_csv(p,records):
    with p.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
def main():
    result={}; epochs=[];summary=[]
    binaries=load(ROOT/'validation/build.json')['binaries']
    assert all(sha(ROOT/'bin'/f)==v for f,v in binaries.items())
    for label in ['2221','2236']:
        s=d/label;i=s/'imported';ref=load(i/'capture.json')['reference']
        p=load(s/'SSR/replay.json');m=load(i/'capture.json');software=load(i/'software.json')
        assert all(sha(Path(p['input_files'][f]))==v for f,v in p['input_sha256'].items())
        assert sha(next(s.glob('*.zip')))==load(i/'import.json')['archive_sha256']
        sol=rows(s/'SSR/solution.csv');ph=rows(i/'solutions.csv');ee=rows(i/'epochs.csv');cr=rows(s/'SSR/corrections.csv')
        assert len(sol)==len(ee)==len(cr)
        assert flags([r for r in sol if r['Q']!='0'])==flags(ph)
        assert all(key(a)==key(b) and abs(key(a)-key(c))<Decimal('0.00000001') and int(c['records_released'])==int(b['applied_seq'])+1 for a,b,c in zip(sol,ee,cr))
        assert sha(s/'SSR/observations.csv')==sha(i/'observations.csv')
        for mode in ('audit_v2','control_v2'):
            assert positions(sol)==positions(rows(s/mode/'solution.csv'))
        for name,old in [('FILE_checked','FILE'),('FILE_checked_same_start','FILE_same_start')]:
            assert positions(rows(s/name/'solution.csv'))==positions(rows(s/old/'solution.csv'))
            assert 'reason=PCVS_APPLIED,model=IGS20.ATX' in (s/name/'preflight.log').read_text()
            assert 'errors=0' in (s/name/'preflight.log').read_text()
        for name in ('B1_ema_only_v2','control_v2','checkpoint','ema_gap_v2','file_gap_v2','file_all_v2'):
            cs=rows(s/name/'corrections.csv')
            assert len(cs)==len(cr)
            assert all(a['records_released']==b['records_released'] for a,b in zip(cr,cs))
        for name in ('B1_ema_only_v2','control_v2','audit_v2'):
            for file in ('corrections.csv','observations.csv'):assert sha(s/name/file)==sha(s/'SSR'/file)
        paths={'live':s/'SSR/solution.csv','gap_primary':s/'recovered.csv','ema':s/'B1_ema_only_v2/solution.csv','ema_gap':s/'ema_recovered.csv','full_file':s/'FILE_checked/solution.csv','file_same_start':s/'FILE_checked_same_start/solution.csv','replace_code':s/'file_all_v2/solution.csv','gap_inline':s/'file_gap_v2/solution.csv','checkpoint':s/'checkpoint/solution.csv'}
        arms={n:arm(path,ref) for n,path in paths.items()};live=arms['live'];ks=list(map(key,ee));k0=ks[0]
        assert all(list(map(key,rows(path)))==ks for path in paths.values())
        corrected=[r for r in rows(s/'recovered.csv') if r['solution_source']=='WHU_FILE_CODE_GAP'];new={key(r) for r in corrected}
        assert {key(r) for r in rows(s/'ema_recovered.csv') if r['solution_source']=='WHU_FILE_CODE_GAP'}==new
        assert set(live)==set(arms['ema'])==set(arms['checkpoint'])
        assert set(arms['gap_primary'])==set(arms['ema_gap'])==set(live)|new
        assert all(arms['gap_primary'][k]==v and arms['ema_gap'][k]==arms['ema'][k] for k,v in live.items())
        assert all(r['Q']=='0' for r in sol if key(r) in new)
        clocks={}; outcomes={}
        for n in ('B1_ema_only_v2','ema_gap_v2'):
            val=closure(s/n/'solution.trace')
            assert set(val)==set(arm(s/n/'solution.csv',ref)) and max(val.values())<1e-8
            clocks[n]=max(val.values())
        common=sorted(set(live)&set(arms['full_file'])&set(arms['file_same_start']))
        for name,a in arms.items():
            basekeys=sorted(set(a)&set(live));pair=measure(a,basekeys)
            summary.append(dict(session=label,method=name,q6=len(a),raw=len(ks),first_q6_s=float(min(a)-k0),paired_live_n=len(basekeys),paired_live_h_m=pair['h'],paired_live_u_m=pair['u'],common_n=len(common),common_h_m=measure(a,common)['h'],common_u_m=measure(a,common)['u'],all_h_m=measure(a,sorted(a))['h'],all_u_m=measure(a,sorted(a))['u']))
            tail=sorted(t for t in a if t>ks[-1]-60)
            outcomes[name]=dict(all=measure(a,sorted(a)),common_all_methods=measure(a,common),paired=pair,live_on_same_keys=measure(live,basekeys),tail60s=measure(a,tail),added=measure(a,sorted(set(a)-set(live))))
        for k,row in zip(ks,sol):
            line={'session':label,'elapsed_s':round(float(k-k0),5),'phone_q':row['Q'],'osb_gap_filled':int(k in new)}
            for n in ('live','gap_primary','ema_gap','full_file','file_same_start'):
                v=arms[n].get(k)
                line[n+'_h_m']=round(math.hypot(*v[:2]),5) if v else ''
                line[n+'_u_m']=round(v[2],5) if v else ''
            epochs.append(line)
        labels=collections.Counter()
        with (s/'file_gap_v2/sat_gate.csv').open() as f:
            for w,t,sv,why in csv.reader(f):
                if int(w)*604800+Decimal(t) in new:labels[why]+=1
        bias_delta=[abs(float(r[-1])) for r in csv.reader((s/'file_all_v2/bias_pairs.csv').open())]
        transitions={}
        for n in ('ema_gap','gap_primary'):
            rr=rows(paths[n]);transitions[n]=[round(math.dist(err(a,ref),err(b,ref)),6) for a,b in zip(rr,rr[1:]) if a['Q']==b['Q']=='6' and a['solution_source']!=b['solution_source']]
        gaps=[dict(start_s=float(g[0]-k0),last_s=float(g[-1]-k0),n=len(g)) for g in runs(sorted(new))]
        reasons=collections.Counter(r['status'].split(';')[0] for r in ee if key(r) in new)
        phone=arm(i/'solutions.csv',ref)
        receipt=load(i/'import.json');transport={r['mount']:{k:r[k] for k in ('connection_count','crc_failures','valid_rtcm_frames')} for r in m['streams']}
        arrival=rows(i/'arrivals.csv')
        transport_issues=[dict(channel=int(r['channel']),elapsed_s=round(int(r['elapsed_ns'])/1e9,2),event=r['reason']) for r in arrival if r['event']=='CLOSED']
        within=[sum(int(a['length']) for a in arrival if a['event']=='DATA' and int(a['channel'])==ch and int(cr[ks.index(min(new))-1]['records_released'])<=int(a['seq'])<int(cr[ks.index(max(new))]['records_released'])) for ch in range(3)]
        result[label]=dict(archive=Path(receipt['archive']).name,archive_sha256=receipt['archive_sha256'],device_model=software['model'],apk_sha256=software['apk_sha256'],raw_epochs=len(ks),phone_q=p['Q'],q5_q6_keys_match=True,q0_from_epoch_ledger=True,phone_max_q6_xyz_delta_m=max(math.dist(live[k],phone[k]) for k in live),formal_inputs_checked=len(p['input_sha256']),release_prefix_checks=len(cr),observation_bytes_match=True,formal_control_position_fields_equal=True,frozen_ema_observations_and_corrections_sha_match=True,clock_header_change_position_fields_equal=True,metrics=outcomes,transport=transport,transport_issues=transport_issues,filled_intervals=gaps,osb_gap_phone_message_counts=dict(reasons),osb_gap_observed_satellite_reason_counts=dict(labels),osb_gap_received_bytes_in_prefixes=within,confirmed_code_bias_difference_m={'rows':len(bias_delta),'median_abs':statistics.median(bias_delta),'max_abs':max(bias_delta)},switch_3d_m=transitions,max_kv_closure_m=clocks)
    productdir=d/'products'
    products=list(productdir.glob('pride_*.CLK'))+list(productdir.glob('pride_*.BIA'))+list(productdir.glob('pride_*.SP3'))+[BIA,productdir/'igs20.atx',productdir/'BRDC00WRD_S_20263230000_01D_MN.rnx']
    put(d/'verification.json',dict(sessions=result,product_sha256={p.name:sha(p) for p in products},formal_bin_sha256_checked=len(binaries),reference_use='post_solution_ENU_only',algorithm='B_VERIFIED, uncombined ionosphere estimation, float ambiguities, Joseph',scope='PC private replay'))
    write_csv(d/'summary.csv',summary);write_csv(d/'epochs_paired.csv',epochs)
if __name__=='__main__':main()
