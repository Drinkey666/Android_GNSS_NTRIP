
from pathlib import Path
import difflib,subprocess
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
CORE=ROOT/'core'
def rewrite(name, pairs):
    source=(CORE/name).read_text(encoding='utf-8-sig')
    after=source
    for old,new in pairs:
        assert after.count(old)==1,(name,old,after.count(old))
        after=after.replace(old,new)
    (OUT/f'private_{name}').write_text(after,encoding='utf-8')
    return ''.join(difflib.unified_diff(source.splitlines(True),after.splitlines(True),
        fromfile=f'a/core/{name}',tofile=f'b/core/{name}'))

patch=rewrite('ppp.c',[
    ('static int ppp_res(int post,','#include "step5_weights.inc"\n\nstatic int ppp_res(int post,'),
    ('ppp_innovation_meta_t *row_meta,unsigned char *robust_gnss)\n{',
     'ppp_innovation_meta_t *row_meta,unsigned char *robust_gnss,step5_weight_t *weights)\n{'),
    ('        int sat_has_phase = 0;','        int sat_has_phase = 0, step5_phase=0;'),
    ('        /* stack phase and code residuals', '''        if(!post && step5_gate>0.0) {
            const ssat_t *ss=&rtk->ssat[sat-1];
            for(j=0;j<NF(opt) && j<NFREQ;j++) {
                const int row=i*2*NFREQ+2*j;
                if(L[j]!=0.0 && ppp_signal_supported(sys,j,obs[i].code[j],opt) &&
                    !((ss->slip[j]|obs[i].LLI[j])&LLI_SLIP) &&
                    (!mexc || !mexc[row]) && !ppp_phase_quarantined(ss,j,obs[i].time))step5_phase=1;
            }
        }
        /* stack phase and code residuals'''),
    ('            frq = j / 2;\n\n            if (!ppp_signal_supported', '''            frq = j / 2;
            if (code && sys==step5_remove_sys) continue;

            if (!ppp_signal_supported'''),
    ('''            if(opt->ppp_baseline==MODE_C_NEW_ROBUST)
                trace(3,"$PPP_R_PRE_HUBER''','''            if(!post && weights) {
                step5_weight_t w={0};
                w.before=var[nv];
                w.geom_factor=w.huber_factor=1.0;
                if(code && step5_gate>0.0 && !step5_phase && !rtk->ppp_code_warmup) {
                    w.geom_factor=4.0;
                    var[nv]*=w.geom_factor;
                }
                weights[nv]=w;
            }
            if(opt->ppp_baseline==MODE_C_NEW_ROBUST)
                trace(3,"$PPP_R_PRE_HUBER'''),
    ('c->R,c->azel,NULL,NULL,c->meta,NULL);','c->R,c->azel,NULL,NULL,c->meta,NULL,NULL);'),
    ('    ppp_diag_epoch_t diag, evidence;','    ppp_diag_epoch_t diag, evidence;\n    step5_weight_t weights[STEP5_ROWS]={0};\n    double step5_before[3];'),
    ('    /* 第 6 步：按开关处理地影和潮汐。','''    step5_config();
    if(opt->ionoopt!=IONOOPT_EST || opt->modear!=ARMODE_OFF ||
        !ppp_verified_joseph(opt) || opt->ppp_iekf) {
        trace(2,"$S5_INVALID_PROFILE\\n");
        rtk->ppp_failure=FILTER_BAD_DIM;
        goto cleanup;
    }
    /* 第 6 步：按开关处理地影和潮汐。'''),
    ('if(!row_meta && (smartphone_ppp_policy(opt).common_clock || opt->ppp_iekf)) {','if(!row_meta) {'),
    ('azel, NULL, product_use, row_meta,robust_gnss))<=0)','azel, NULL, product_use, row_meta,robust_gnss,weights))<=0)'),
    ('v,H,R,azel,NULL,product_use,row_meta,robust_gnss);','v,H,R,azel,NULL,product_use,row_meta,robust_gnss,weights);'),
    ('        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.',
     '''        if(step5_gate>0.0)step5_pool_weights(rtk,obs,n,nav,xp,dr,azel,v,R,row_meta,nv,weights);
        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.'''),
    ('        if(opt->ppp_iekf) {\n            ppp_iekf_context_t ctx;', '''        memcpy(step5_before,xp,sizeof(step5_before));
        step5_gain_count=nv;
        if(opt->ppp_iekf) {
            ppp_iekf_context_t ctx;'''),
    ('            filter(xp,Pp,H,v,R,rtk->nx,nv);\n','            filter(xp,Pp,H,v,R,rtk->nx,nv);\n        step5_gain_count=0;\n'),
    ('&diag, NULL, NULL,NULL);','&diag, NULL, NULL,NULL,NULL);'),
    ('            rtk->ppp_clock_time=obs[0].time;\n            stat = SOLQ_PPP;',
     '''            rtk->ppp_clock_time=obs[0].time;
            step5_report(rtk,obs,nv,i,row_meta,R,step5_before,&diag,weights);
            stat = SOLQ_PPP;'''),
    ('azel, NULL, NULL, NULL,NULL)>0','azel, NULL, NULL, NULL,NULL,NULL)>0'),
])
patch+=rewrite('rtkcmn.c',[
    ('static int filter_(const double *x,','''extern void step5_active_indices(const int *ix,int n);
extern void step5_capture_gain(const double *K,const double *v,int n,int m);
static int filter_(const double *x,'''),
    ('        matmul("NN",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */','''        matmul("NN",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */
        step5_capture_gain(K,v,n,m);'''),
    ('    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);','''    step5_active_indices(ix,k);
    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);'''),
])
(OUT/'step5_private.patch').write_text(patch,encoding='utf-8')
build=(ROOT/'build/build.cmd').read_text(encoding='utf-8-sig').splitlines()
lines=build[:2]
link=next(l for l in build if l.startswith('link ') and 'ppp_ssr_replay.exe' in l)
for name in ('ppp','rtkcmn'):
    source=str(CORE/(name+'.c'))
    old=str(ROOT/'build'/f'{name}.obj')
    new=str(OUT/f'private_{name}.obj')
    cmd=next(l for l in build if l.startswith('cl ') and f'"{source}"' in l)
    lines.extend([cmd.replace(source,str(OUT/f'private_{name}.c')).replace(old,new),'if errorlevel 1 exit /b 1'])
    link=link.replace(old,new)
lines.append(link.replace(str(ROOT/'bin/ppp_ssr_replay.exe'),str(OUT/'step5_probe.exe')))
path=OUT/'build_private.cmd'
path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
with (OUT/'build_private.log').open('wb') as log:
    subprocess.run(['cmd','/c',str(path)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,check=True)
