
from pathlib import Path
import difflib,subprocess
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
CORE=ROOT/'core'
def rewrite(name,changes):
    orig=(CORE/name).read_text(encoding='utf-8-sig')
    new=orig
    for old,result in changes:
        assert new.count(old)==1,(name,old,new.count(old))
        new=new.replace(old,result)
    (OUT/f'private_{name}').write_text(new,encoding='utf-8')
    return ''.join(difflib.unified_diff(orig.splitlines(True),new.splitlines(True),
                  fromfile=f'a/core/{name}',tofile=f'b/core/{name}'))

patch=rewrite('ppp.c',[
    ('static void udbias_ppp(rtk_t* rtk, const obsd_t* obs, int n, const nav_t* nav)',
     'static void udbias_ppp(rtk_t* rtk, const obsd_t* obs, int n, const nav_t* nav,int seed_source[MAXSAT][NFREQ])'),
    ('    char tstr[40];\n\n    trace(3, "udbias', '    int used_rcb[MAXOBS]={0};\n    char tstr[40];\n\n    trace(3, "udbias'),
    ('            bias[i] = 0.0;\n            slip[i] = 0;',
     '            bias[i] = 0.0;\n            slip[i] = 0;\n            used_rcb[i]=0;'),
    ('                bias[i] = L[f] - P_clean + gamma * dion;',
     '''                bias[i] = L[f] - P_clean + gamma * dion;
                if(f>0 && seed_frequency==f && id_ifb>=0 && id_ifb<rtk->nx &&
                    rtk->x[id_ifb]==1E-6)used_rcb[i]=ifb_slot+1;'''),
    ('                initx(rtk, bias[i], VAR_BIAS, j);',
     '                initx(rtk, bias[i], VAR_BIAS, j);\n                seed_source[sat-1][f]=used_rcb[i];'),
    ('static void udstate_ppp(rtk_t* rtk, const obsd_t* obs, int n, const nav_t* nav)',
     'static void udstate_ppp(rtk_t* rtk, const obsd_t* obs, int n, const nav_t* nav,int seed_source[MAXSAT][NFREQ])'),
    ('    udbias_ppp(rtk, obs, n, nav);','    udbias_ppp(rtk, obs, n, nav,seed_source);'),
    ('static int ppp_res(int post,',
     '#include "../brain_step7_m1v4_refinement/step7_weights.inc"\n#include "step8_seed.inc"\n\nstatic int ppp_res(int post,'),
    ('    ppp_diag_epoch_t diag, evidence;',
     '''    ppp_diag_epoch_t diag, evidence;
    int seed_source[MAXSAT][NFREQ]={{0}};
    s8_trial_t seed_audit;
    double s8_before[3];
    const int with_A=s8_with_A();'''),
    ('    udstate_ppp(rtk, obs, n, nav);','    udstate_ppp(rtk, obs, n, nav,seed_source);'),
    ('    /* 第 6 步：按开关处理地影和潮汐。','''    if(opt->ionoopt!=IONOOPT_EST || opt->modear!=ARMODE_OFF ||
        !ppp_verified_joseph(opt) || opt->ppp_iekf || ND(opt)>S8_RCB_SLOTS) {
        trace(2,"$S8_INVALID_PROFILE\\n");
        rtk->ppp_failure=FILTER_BAD_DIM;
        goto cleanup;
    }
    /* 第 6 步：按开关处理地影和潮汐。'''),
    ('if(!row_meta && (smartphone_ppp_policy(opt).common_clock || opt->ppp_iekf)) {','if(!row_meta) {'),
    ('        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.', '''        {
            s8_prior_t before[MAXSAT+3];
            memset(&seed_audit,0,sizeof(seed_audit));
            seed_audit.pseudo_count=s8_prior_rows(row_meta,v,R,nv,before);
            if(s8_isb(rtk,xp,v,row_meta,nv,&seed_audit)) {
                nv=ppp_res(0,obs,n,rs,dts,var,svh,dr,exc,mexc,nav,xp,rtk,
                    v,H,R,azel,NULL,product_use,row_meta,robust_gnss);
                if(nv<=0){if(!rtk->ppp_failure)rtk->ppp_failure=PPP_FAILURE_NO_OBS;break;}
            }
            if(s8_rcb(rtk,xp,v,row_meta,nv,seed_source,&seed_audit)) {
                nv=ppp_res(0,obs,n,rs,dts,var,svh,dr,exc,mexc,nav,xp,rtk,
                    v,H,R,azel,NULL,product_use,row_meta,robust_gnss);
                if(nv<=0){if(!rtk->ppp_failure)rtk->ppp_failure=PPP_FAILURE_NO_OBS;break;}
            }
            seed_audit.p_unchanged=!memcmp(Pp,rtk->P,(size_t)rtk->nx*rtk->nx*sizeof(double));
            seed_audit.pseudo_unchanged=s8_same_priors(before,seed_audit.pseudo_count,row_meta,v,R,nv);
            if(!seed_audit.p_unchanged || !seed_audit.pseudo_unchanged) {
                trace(2,"$S8_SEED_INVARIANT_FAILURE\\n");
                rtk->ppp_failure=FILTER_BAD_DIM;
                break;
            }
        }
        if(with_A) {
            s7_row_t weights[S7_ROWS];
            s7_apply(S7_A,rtk,obs,n,nav,xp,dr,azel,v,R,row_meta,nv,weights);
        }
        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.'''),
    ('        if(opt->ppp_iekf) {\n            ppp_iekf_context_t ctx;', '''        memcpy(s8_before,xp,sizeof(s8_before));
        s7_gain_count=nv;
        if(opt->ppp_iekf) {
            ppp_iekf_context_t ctx;'''),
    ('            filter(xp,Pp,H,v,R,rtk->nx,nv);\n','            filter(xp,Pp,H,v,R,rtk->nx,nv);\n        s7_gain_count=0;\n'),
    ('            rtk->ppp_clock_time=obs[0].time;\n            stat = SOLQ_PPP;',
     '''            rtk->ppp_clock_time=obs[0].time;
            s8_report(rtk,obs,nv,i,row_meta,s8_before,&seed_audit);
            stat = SOLQ_PPP;'''),
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
(OUT/'step8_private.patch').write_text(patch,encoding='utf-8')
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
lines.append(link.replace(str(ROOT/'bin/ppp_ssr_replay.exe'),str(OUT/'step8_probe.exe')))
cmd=OUT/'build_private.cmd'
cmd.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with (OUT/'build_private.log').open('wb') as log:
    subprocess.run(['cmd','/c',str(cmd)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,check=True)
