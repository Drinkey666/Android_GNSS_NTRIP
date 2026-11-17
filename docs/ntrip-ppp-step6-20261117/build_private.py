
from pathlib import Path
import difflib,subprocess
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
source=ROOT/'core/ppp.c'
orig=source.read_text(encoding='utf-8-sig')
s=orig
changes=[
    ('static int ppp_res(int post,','#include "step6_weights.inc"\n\nstatic int ppp_res(int post,'),
    ('    ppp_diag_epoch_t diag, evidence;',
     '    ppp_diag_epoch_t diag, evidence;\n    step6_row_t step6_weights[STEP6_ROWS];\n    char step6_mode;\n    int step6_phase_sat=0;'),
    ('    /* 第 6 步：按开关处理地影和潮汐。','''    step6_mode=step6_scheme();
    if(opt->ionoopt!=IONOOPT_EST || opt->modear!=ARMODE_OFF ||
        !ppp_verified_joseph(opt) || opt->ppp_iekf) {
        trace(2,"$S6_INVALID_PROFILE\\n");
        rtk->ppp_failure=FILTER_BAD_DIM;
        goto cleanup;
    }
    /* 第 6 步：按开关处理地影和潮汐。'''),
    ('if(!row_meta && (smartphone_ppp_policy(opt).common_clock || opt->ppp_iekf)) {','if(!row_meta) {'),
    ('        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.',
     '''        if(step6_mode)step6_phase_sat=step6_apply(step6_mode,rtk,obs,n,nav,xp,dr,azel,v,R,row_meta,nv,step6_weights);
        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.'''),
    ('        update_stat(rtk, obs, n, stat);\n',
     '''        update_stat(rtk, obs, n, stat);
        if(rtk->sol.stat==SOLQ_PPP) {
            if(step6_mode)step6_log(obs,nv,step6_phase_sat,v,R,row_meta,step6_weights);
            step6_seen_q6=1;
        }
'''),
]
for old,new in changes:
    assert s.count(old)==1,(old,s.count(old))
    s=s.replace(old,new)
private=OUT/'private_ppp.c'
private.write_text(s,encoding='utf-8')
patch=''.join(difflib.unified_diff(orig.splitlines(True),s.splitlines(True),fromfile='a/core/ppp.c',tofile='b/core/ppp.c'))
(OUT/'step6_private.patch').write_text(patch,encoding='utf-8')
build=(ROOT/'build/build.cmd').read_text(encoding='utf-8-sig').splitlines()
old_obj=str(ROOT/'build/ppp.obj')
new_obj=str(OUT/'private_ppp.obj')
compile=next(l for l in build if l.startswith('cl ') and f'"{source}"' in l)
link=next(l for l in build if l.startswith('link ') and 'ppp_ssr_replay.exe' in l)
lines=[*build[:2],compile.replace(str(source),str(private)).replace(old_obj,new_obj),
       'if errorlevel 1 exit /b 1',
       link.replace(old_obj,new_obj).replace(str(ROOT/'bin/ppp_ssr_replay.exe'),str(OUT/'step6_probe.exe'))]
path=OUT/'build_private.cmd'
path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with (OUT/'build_private.log').open('wb') as log:
    subprocess.run(['cmd','/c',str(path)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,check=True)
