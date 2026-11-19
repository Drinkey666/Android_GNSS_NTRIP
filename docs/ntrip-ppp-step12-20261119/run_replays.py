"""One independent process and a fresh output directory for each saved run."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
from guard import OUT, read, save, sha

DATASETS=("1120_xiaomi","1120_vivo","1004_xiaomi","1004_vivo","1031_xiaomi_V1","1031_xiaomi_V2")
SCHEMES=("A1_outlier_gim_mad","A2_stoch_ema_r","A3_kf_amb_anneal","A4_pure_kf_anneal")
def baseline(d):
    return OUT.parent/"brain_step5_east_and_m1v2"/"runs"/d/"Baseline"
def launch(job):
    d,s=job
    dest=OUT/"runs"/d/s
    dest.mkdir(parents=True,exist_ok=False)
    args=read(baseline(d)/"command.json")["args"][:]
    args[0]=str(OUT/"step12_probe.exe")
    for option,f in {"--result-file":"solution.csv","--ssr-diagnostic":"corrections.csv",
                     "--state-dump":"solution.stat","--obs-dump":"observations.csv","--trace":"solution.trace"}.items():
        args[args.index(option)+1]=str(dest/f)
    assert not any(k in args for k in ("--reference","--ru"))
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(("RTK_PPP_","NTRIP_PRIVATE_","STEP","WHU_EAST_PROBE","AUDIT_"))}
    env.update(STEP12_SCHEME=s,TMP=str(dest),TEMP=str(dest))
    save(dest/"command.json",dict(args=args,scheme=s,exe_sha256=sha(args[0])))
    with (dest/"console.log").open("wb") as log:
        subprocess.run(args,cwd=dest,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    print(d,s,"complete",flush=True)
if __name__=="__main__":
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(launch,((d,s) for s in SCHEMES for d in DATASETS)))
