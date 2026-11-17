
from pathlib import Path
import difflib,subprocess
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
CORE=ROOT/'core'
def rewrite(name,pairs):
    source=(CORE/name).read_text(encoding='utf-8-sig')
    result=source
    for old,new in pairs:
        assert result.count(old)==1,(name,old,result.count(old))
        result=result.replace(old,new)
    (OUT/f'private_{name}').write_text(result,encoding='utf-8')
    return ''.join(difflib.unified_diff(source.splitlines(True),result.splitlines(True),
            fromfile=f'a/core/{name}',tofile=f'b/core/{name}'))

patch=rewrite('ppp.c',[
    ('static int ppp_res(int post,','#include "step7_weights.inc"\n\nstatic int ppp_res(int post,'),
    ('    ppp_diag_epoch_t diag, evidence;',
     '    ppp_diag_epoch_t diag, evidence;\n    s7_row_t step7_weights[S7_ROWS];\n    const int step7_mode=s7_scheme();\n    double s7_before[3];'),
    ('    /* 第 6 步：按开关处理地影和潮汐。','''    if(!step7_mode || opt->ionoopt!=IONOOPT_EST || opt->modear!=ARMODE_OFF ||
        !ppp_verified_joseph(opt) || opt->ppp_iekf) {
        trace(2,"$S7_INVALID_PROFILE\\n");
        rtk->ppp_failure=FILTER_BAD_DIM;
        goto cleanup;
    }
    /* 第 6 步：按开关处理地影和潮汐。'''),
    ('if(!row_meta && (smartphone_ppp_policy(opt).common_clock || opt->ppp_iekf)) {','if(!row_meta) {'),
    ('        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.',
     '''        s7_apply(step7_mode,rtk,obs,n,nav,xp,dr,azel,v,R,row_meta,nv,step7_weights);
        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.'''),
    ('        if(opt->ppp_iekf) {\n            ppp_iekf_context_t ctx;', '''        memcpy(s7_before,xp,sizeof(s7_before));
        s7_gain_count=nv;
        if(opt->ppp_iekf) {
            ppp_iekf_context_t ctx;'''),
    ('            filter(xp,Pp,H,v,R,rtk->nx,nv);\n','            filter(xp,Pp,H,v,R,rtk->nx,nv);\n        s7_gain_count=0;\n'),
    ('        update_stat(rtk, obs, n, stat);\n',
     '''        update_stat(rtk, obs, n, stat);
        if(rtk->sol.stat==SOLQ_PPP)s7_report(rtk,obs,nv,row_meta,v,R,s7_before,step7_weights);
'''),
])
patch+=rewrite('rtkcmn.c',[
    ('static int filter_(const double *x,','''extern void s7_active_indices(const int *ix,int n);
extern void s7_capture_gain(const double *K,const double *v,int n,int m);
static int filter_(const double *x,'''),
    ('        matmul("NN",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */','''        matmul("NN",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */
        s7_capture_gain(K,v,n,m);'''),
    ('    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);','''    s7_active_indices(ix,k);
    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);'''),
])
(OUT/'step7_private.patch').write_text(patch,encoding='utf-8')
script=(ROOT/'build/build.cmd').read_text(encoding='utf-8-sig').splitlines()
lines=script[:2]
link=next(l for l in script if l.startswith('link ') and 'ppp_ssr_replay.exe' in l)
for source in ('ppp','rtkcmn'):
    c=str(CORE/f'{source}.c')
    obj=str(ROOT/'build'/f'{source}.obj')
    new=str(OUT/f'private_{source}.obj')
    line=next(l for l in script if l.startswith('cl ') and f'"{c}"' in l)
    lines.extend([line.replace(c,str(OUT/f'private_{source}.c')).replace(obj,new),
                  'if errorlevel 1 exit /b 1'])
    link=link.replace(obj,new)
lines.append(link.replace(str(ROOT/'bin/ppp_ssr_replay.exe'),str(OUT/'step7_probe.exe')))
cmd=OUT/'build_private.cmd'
cmd.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with (OUT/'build_private.log').open('wb') as log:
    subprocess.run(['cmd','/c',str(cmd)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,check=True)
