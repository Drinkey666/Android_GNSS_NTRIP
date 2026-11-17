
from pathlib import Path
import difflib,re,subprocess,sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[1]
CORE=ROOT/'core'
SRC=ROOT/'src'
def rewrite(src,dest,replacements):
    text=src.read_text(encoding='utf-8-sig')
    after=text
    for old,new in replacements:
        n=after.count(old)
        if n!=1:raise ValueError((src,old,n))
        after=after.replace(old,new)
    (OUT/dest).write_text(after,encoding='utf-8')
    return ''.join(difflib.unified_diff(text.splitlines(True),after.splitlines(True),
                   fromfile=f'a/core/{src.name}',tofile=f'b/core/{src.name}'))

patch=rewrite(CORE/'ppp.c','private_ppp.c',[
    ('static void invalidate_arc_ppp(rtk_t *rtk, int sat, int f, const char *reason)\n{',
     'static void step4_forget_arc(int sat,int f);\n\nstatic void invalidate_arc_ppp(rtk_t *rtk, int sat, int f, const char *reason)\n{'),
    ('    if(j<0 || j>=rtk->nx)return;\n    if(!ss->ppp_arc_reset[f]) {',
     '    if(j<0 || j>=rtk->nx)return;\n    step4_forget_arc(sat,f);\n    if(!ss->ppp_arc_reset[f]) {'),
    ('            if (old_code != CODE_NONE) {\n                j = IB(sat, f, &rtk->opt);',
     '            if (old_code != CODE_NONE) {\n                step4_forget_arc(sat,f);\n                j = IB(sat, f, &rtk->opt);'),
    ('static int ppp_res(int post,', '#include "step4_weights.inc"\n\nstatic int ppp_res(int post,'),
    ('ppp_innovation_meta_t *row_meta,unsigned char *robust_gnss)\n{',
     'ppp_innovation_meta_t *row_meta,unsigned char *robust_gnss,step4_trial_t *probe)\n{'),
    ('        int sat_has_phase = 0;\n', '''        int sat_has_phase=0, step4_phase=0, step4_code_freqs=0, step4_gim=0;
        double raw_p[NFREQ]={0}, step4_dion=dion;
'''),
    ('        applydoppsm_ppp(rtk, obs + i, P);\n\n        /* stack phase', '''        if(!post && probe && (probe->mask&STEP4_M3)) {
            double ion,var_gim;
            memcpy(raw_p,P,sizeof(raw_p));
            step4_gim=ionex_vertical_prior(obs[i].time,nav,pos,azel+i*2,opt,&ion,&var_gim);
            step4_dion=step4_gim ? ppp_iono_mapf(nav,pos,azel+i*2)*ion : dion;
        }
        applydoppsm_ppp(rtk, obs + i, P);
        if(!post && probe && (probe->mask&STEP4_M2)) {
            const ssat_t *ss=&rtk->ssat[sat-1];
            for(j=0;j<NF(opt) && j<NFREQ;j++) {
                const int row=i*2*NFREQ+2*j;
                if(!ppp_signal_supported(sys,j,obs[i].code[j],opt))continue;
                if(P[j]!=0.0 && !ss->ppp_code_bad[j] && (!mexc || !mexc[row+1]) &&
                    ppp_code_modelled(sys,j,obs[i].code[j],opt))step4_code_freqs++;
                if(L[j]!=0.0 && !((ss->slip[j]|obs[i].LLI[j])&LLI_SLIP) &&
                    (!mexc || !mexc[row]) && !ppp_phase_quarantined(ss,j,obs[i].time))step4_phase=1;
            }
        }

        /* stack phase'''),
    ('''            if(opt->ppp_baseline==MODE_C_NEW_ROBUST)
                trace(3,"$PPP_R_PRE_HUBER''','''            if(!post && probe && code) {
                const ssat_t *ss=&rtk->ssat[sat-1];
                step4_weight_t *w=probe->rows+nv;
                memset(w,0,sizeof(*w));
                w->r_before=var[nv];
                w->m1=w->m2=w->m3=1.0;
                if(probe->mask&STEP4_M2) {
                    if(step4_code_freqs==1)w->m2*=3.0;
                    if(!step4_phase && !rtk->ppp_code_warmup)w->m2*=4.0;
                }
                if((probe->mask&STEP4_M3) && L[frq]!=0.0 && raw_p[frq]!=0.0 &&
                    step4_arc_matches(&step4_arcs[sat-1][frq],ss,obs+i,frq,step4_gim)) {
                    const double cmc=raw_p[frq]-L[frq]-2.0*C*step4_dion;
                    w->cmc_drift=fabs(cmc-step4_arcs[sat-1][frq].anchor);
                    w->m3_gim=step4_gim;
                    if(w->cmc_drift>1.8)w->m3=MIN(36.0,SQR(w->cmc_drift/1.8));
                }
                if(w->m2>1.0 || w->m3>1.0)var[nv]*=w->m2*w->m3;
            }
            if(opt->ppp_baseline==MODE_C_NEW_ROBUST)
                trace(3,"$PPP_R_PRE_HUBER'''),
    ('c->R,c->azel,NULL,NULL,c->meta,NULL);','c->R,c->azel,NULL,NULL,c->meta,NULL,NULL);'),
    ('    ppp_diag_epoch_t diag, evidence;\n','    ppp_diag_epoch_t diag, evidence;\n    step4_trial_t probe;\n    double step4_before[3];\n'),
    ('    /* 第 6 步：按开关处理地影和潮汐。','''    probe.mask=step4_mask();
    if(opt->ionoopt!=IONOOPT_EST || opt->modear!=ARMODE_OFF ||
        !ppp_verified_joseph(opt) || opt->ppp_iekf) {
        trace(2,"$STEP4_INVALID_PROFILE\\n");
        rtk->ppp_failure=FILTER_BAD_DIM;
        goto cleanup;
    }

    /* 第 6 步：按开关处理地影和潮汐。'''),
    ('if(!row_meta && (smartphone_ppp_policy(opt).common_clock || opt->ppp_iekf)) {','if(!row_meta) {'),
    ('azel, NULL, product_use, row_meta,robust_gnss))<=0)', 'azel, NULL, product_use, row_meta,robust_gnss,&probe))<=0)'),
    ('v,H,R,azel,NULL,product_use,row_meta,robust_gnss);','v,H,R,azel,NULL,product_use,row_meta,robust_gnss,&probe);'),
    ('        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.', '''        if(probe.mask&STEP4_M1)step4_prefit_gim(rtk,obs,n,nav,xp,dr,azel,v,R,row_meta,nv,&probe);
        /* Snapshot pre-fit diagnostics before filter mutates xp/Pp.'''),
    ('        if(opt->ppp_iekf) {\n            ppp_iekf_context_t ctx;', '''        memcpy(step4_before,xp,sizeof(step4_before));
        step4_gain_count=nv;
        if(opt->ppp_iekf) {
            ppp_iekf_context_t ctx;'''),
    ('            filter(xp,Pp,H,v,R,rtk->nx,nv);\n','            filter(xp,Pp,H,v,R,rtk->nx,nv);\n        step4_gain_count=0;\n'),
    ('&diag, NULL, NULL,NULL);','&diag, NULL, NULL,NULL,NULL);'),
    ('            rtk->ppp_clock_time=obs[0].time;\n            stat = SOLQ_PPP;', '''            rtk->ppp_clock_time=obs[0].time;
            step4_report(rtk,obs,nv,i,row_meta,v,R,step4_before,&probe);
            if(probe.mask&STEP4_M3)step4_save_arcs(rtk,obs,n,nav,dr,azel,&diag);
            stat = SOLQ_PPP;'''),
    ('azel, NULL, NULL, NULL,NULL)>0','azel, NULL, NULL, NULL,NULL,NULL)>0')
])
patch+=rewrite(CORE/'rtkcmn.c','private_rtkcmn.c',[
    ('static int filter_(const double *x,', '''extern void step4_active_indices(const int *ix,int n);
extern void step4_capture_gain(const double *K,const double *v,int n,int m);
static int filter_(const double *x,'''),
    ('        matmul("NN",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */','''        matmul("NN",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */
        step4_capture_gain(K,v,n,m);'''),
    ('    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);','''    step4_active_indices(ix,k);
    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);'''),
])
(OUT/'step4_private.patch').write_text(patch,encoding='utf-8')
build=(ROOT/'build/build.cmd').read_text(encoding='utf-8-sig').splitlines()
header=build[:2]
link=next(l for l in build if l.startswith('link ') and 'ppp_ssr_replay.exe' in l)
commands=[*header]
for name in ('ppp','rtkcmn'):
    pattern=str(CORE/(name+'.c'))
    line=next(l for l in build if l.startswith('cl ') and f'"{pattern}"' in l)
    line=line.replace(pattern,str(OUT/f'private_{name}.c')).replace(
        str(ROOT/'build'/f'{name}.obj'),str(OUT/f'private_{name}.obj'))
    commands.extend((line,'if errorlevel 1 exit /b 1'))
    link=link.replace(str(ROOT/'build'/f'{name}.obj'),str(OUT/f'private_{name}.obj'))
commands.extend((link.replace(str(ROOT/'bin/ppp_ssr_replay.exe'),str(OUT/'step4_probe.exe')),
                  'exit /b %errorlevel%'))
path=OUT/'build_private.cmd'
path.write_text('\n'.join(commands)+'\n',encoding='utf-8')
with (OUT/'build_private.log').open('wb') as log:
    subprocess.run(['cmd','/c',str(path)],cwd=OUT,stdout=log,stderr=subprocess.STDOUT,check=True)
