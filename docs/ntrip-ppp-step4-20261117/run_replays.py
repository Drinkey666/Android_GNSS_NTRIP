
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import csv,json,hashlib,os,re,subprocess,sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
V=ROOT/'validation'
SWAP=V/'ntrip_code_swap_20261114/replays'
OCT=V/'whu_first_complete_20261114'
PAIR=json.loads((SWAP.parent/'matched/pairing.json').read_text(encoding='utf-8-sig'))
HIST={f'{r["window"]}_{dev}':Path(r[dev])/'pc_replay' for r in PAIR for dev in ('vivo','xiaomi')}
DATASETS={
    '1120_vivo':(SWAP/'1120_vivo/command.json',HIST['1120_vivo']),
    '1120_xiaomi':(SWAP/'1120_xiaomi/command.json',HIST['1120_xiaomi']),
    '1004_vivo':(SWAP/'1004_vivo/command.json',HIST['1004_vivo']),
    '1004_xiaomi':(SWAP/'1004_xiaomi/command.json',HIST['1004_xiaomi']),
    '1031_xiaomi_V1':(OCT/'v1_control/replay.json',OCT/'v1_control'),
    '1031_xiaomi_V2':(OCT/'replay/replay.json',OCT/'replay'),
}
CONFIGS={'Baseline':0,'M1':1,'M2':2,'M3':4,'M123':7}
OUTPUTS={'--result-file':'solution.csv','--ssr-diagnostic':'corrections.csv','--state-dump':'solution.stat',
         '--obs-dump':'observations.csv','--trace':'solution.trace'}

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()
def rows(path):
    with path.open(newline='',encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))
def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def arguments(dataset):
    data=read(DATASETS[dataset][0])
    return (data['args'] if 'args' in data else data['command']).copy()
def capture(dataset):
    args=arguments(dataset)
    return Path(args[args.index('--stream-session')+1])
def environment(run,mask):
    prefixes=('RTK_PPP_','NTRIP_PRIVATE_','STEP2_','STEP4_','WHU_EAST_PROBE','AUDIT_')
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(prefixes)}
    env.update(TEMP=str(run),TMP=str(run),STEP4_BIAS_MASK=str(mask))
    return env
def run_case(job):
    dataset,case,exe,mask=job
    run=OUT/'runs'/dataset/case
    run.mkdir(parents=True)
    args=arguments(dataset)
    args[0]=str(exe)
    for key,name in OUTPUTS.items():
        args[args.index(key)+1]=str(run/name)
    assert '--reference' not in args and '--ru' not in args
    save(run/'command.json',{'args':args,'step4_mask':mask,'exe_sha256':sha(exe)})
    with (run/'console.log').open('wb') as log:
        subprocess.run(args,cwd=run,env=environment(run,mask),stdout=log,stderr=subprocess.STDOUT,check=True)
    data=rows(run/'solution.csv')
    print(dataset,case,'epochs',len(data),'Q6',sum(r['Q']=='6' for r in data),flush=True)
def inputs():
    result={}
    for dataset in DATASETS:
        args=arguments(dataset)
        root=capture(dataset)
        files=[Path(args[args.index(key)+1]) for key in ('--txt','--ionex','--vmf0','--vmf6','--orog','--atx')]
        files.extend(root/n for n in ('ssr.rtcm3','broadcast.rtcm3','bias.rtcm3','arrivals.csv',
                                      'epochs.csv','capture.json','profile.txt'))
        for file in files:
            if file.is_file() and str(file) not in result:
                result[str(file)]=sha(file)
    for file in [*sorted((ROOT/'core').glob('*.[ch]')),*sorted((ROOT/'src').glob('*.[ch]')),
                 *sorted((ROOT/'src').glob('*.cpp')),*sorted((ROOT/'tests').glob('ntrip*test.cpp')),
                 ROOT/'bin/ppp_ssr_replay.exe',ROOT/'bin/ntrip_ssr_test.exe',ROOT/'bin/ntrip_phase_osb_test.exe',
                 *sorted((V/'brain_step3_final_audit_20261116').glob('whu*.csv'))]:
        result[str(file)]=sha(file)
    return result

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='formal':
        save(OUT/'input_guard_sha256.json',inputs())
        jobs=[(d,'FormalControl',ROOT/'bin/ppp_ssr_replay.exe',0) for d in DATASETS]
    else:
        assert mode=='private'
        jobs=[(d,c,OUT/'step4_probe.exe',m) for d in DATASETS for c,m in CONFIGS.items()]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run_case,jobs))
