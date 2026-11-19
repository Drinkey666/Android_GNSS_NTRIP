from pathlib import Path
import os,json,sys,subprocess,concurrent.futures
D=Path(__file__).resolve().parent
ROOT=D.parents[1]
FROZEN=D.parent/'xiaomi_1120_startup_admission_20261119/private/checkpoint.exe'
BIA=D.parent/'vivo_1852_product_comparison_20261119/products/WUM0MGXRTS_20263230000_01D_05M_OSB.BIA'
def launch(pair):
    label,name=pair
    if name not in ('B1_ema_only','checkpoint','control','ema_gap','audit','file_gap','file_all'):
        raise ValueError('Unknown diagnostic mode: '+name)
    src=D/label
    dest=src/(name if name=='checkpoint' else name+'_v2')
    dest.mkdir()
    args=json.loads((src/'SSR/replay.json').read_text())['command']
    args[0]=str(FROZEN if name=='checkpoint' else D/'private_final/replay.exe')
    if name=='B1_ema_only':
        args[0]=str(D.parent/'brain_step13_adaptive_refine/step13_probe.exe')
    if name in ('ema_gap','control'):
        args[0]=str(D/'ema_build/replay.exe')
    for flag in ('--ssr-diagnostic','--result-file','--state-dump','--obs-dump','--trace'):
        i=args.index(flag)+1
        args[i]=str(dest/Path(args[i]).name)
    env={k:v for k,v in os.environ.items() if not k.startswith(('RTK_PPP_','STEP','XIAOMI_','FIELD_'))}
    env.update(TMP=str(dest),TEMP=str(dest))
    if name=='checkpoint':env.update(XIAOMI_GATE='checkpoint',STEP5_SCHEME='Baseline')
    elif name in ('ema_gap','control'):
        env.update(STEP13_SCHEME='B1_ema_only' if name=='ema_gap' else 'CONTROL_NO_R_CHANGE',FIELD_CASE='file_gap' if name=='ema_gap' else 'audit',FIELD_BIA=str(BIA))
    elif name=='B1_ema_only':
        env['STEP13_SCHEME']=name
    else:
        env.update(FIELD_CASE=name,FIELD_BIA=str(BIA))
    assert all(v not in args for v in ('--reference','--ru'))
    with (dest/'console.log').open('wb') as out:
        subprocess.run(args,cwd=dest,env=env,check=True,stdout=out,stderr=subprocess.STDOUT)
    print(label,name,'complete',flush=True)
if __name__=='__main__':
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        list(pool.map(launch,[(label,name) for name in sys.argv[1:] for label in ('2221','2236')]))
