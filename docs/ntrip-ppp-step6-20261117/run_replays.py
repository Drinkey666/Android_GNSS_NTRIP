
from concurrent.futures import ThreadPoolExecutor
import csv,hashlib,json,os,subprocess
from pathlib import Path

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
STEP5=OUT.parent/'brain_step5_east_and_m1v2'
DATASETS=('1120_vivo','1120_xiaomi','1004_vivo','1004_xiaomi','1031_xiaomi_V1','1031_xiaomi_V2')
CANDIDATES=('A','B','C')
OUTPUTS={'--result-file':'solution.csv','--ssr-diagnostic':'corrections.csv','--state-dump':'solution.stat',
         '--obs-dump':'observations.csv','--trace':'solution.trace'}
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))
def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()
def baseline(d):
    return STEP5/'runs'/d/'Baseline'
def args_for(d):
    return read(baseline(d)/'command.json')['args'].copy()
def launch(job):
    d,case=job
    output=OUT/'runs'/d/case
    output.mkdir(parents=True)
    args=args_for(d)
    args[0]=str(OUT/'step6_probe.exe')
    for option,name in OUTPUTS.items():
        args[args.index(option)+1]=str(output/name)
    assert '--reference' not in args and '--ru' not in args
    prefixes=('RTK_PPP_','NTRIP_PRIVATE_','STEP2_','STEP4_','STEP5_','STEP6_','WHU_EAST_PROBE','AUDIT_')
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(prefixes)}
    env.update(TEMP=str(output),TMP=str(output),STEP6_SCHEME=case)
    save(output/'command.json',dict(args=args,scheme=case,exe_sha256=sha(Path(args[0]))))
    with (output/'console.log').open('wb') as log:
        subprocess.run(args,cwd=output,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    data=rows(output/'solution.csv')
    print(d,case,len(data),sum(r['Q']=='6' for r in data),flush=True)
if __name__=='__main__':
    guard=read(STEP5/'input_guard_sha256.json')
    guard.update({str(baseline(d)/p):sha(baseline(d)/p) for d in DATASETS for p in OUTPUTS.values()})
    assert all(sha(Path(p))==s for p,s in guard.items())
    save(OUT/'input_guard_sha256.json',guard)
    jobs=[(d,c) for c in ('Baseline',*CANDIDATES) for d in DATASETS]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(launch,jobs))
