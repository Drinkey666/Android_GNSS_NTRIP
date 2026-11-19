"""Private PC build and causal replays, with the previous input and executable guards."""
from pathlib import Path
import sys
import os
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
D=Path(__file__).resolve().parent
V=D.parent
ROOT=V.parent
PREV=V/"xiaomi_2221_2236_isolated_fixes_20261119"
sys.path.insert(0,str(PREV))
import experiment as old
SRC=old.SOURCE
CMN=V/"brain_step13_adaptive_refine/core/rtkcmn.c"
B=D/"private"
ARMS=("original","ema","new_sat")
LABELS=("2221","2236")
read=old.read
sha=old.digest
replace=old.replace

def guards():
    pins=old.guard()
    assert pins==read(PREV/"guards_local.json")
    for p in [CMN,PREV/"seed.inc",PREV/"experiment.py",PREV/"verification.json",old.PARENT,
              V/"xiaomi_2221_2236_accuracy_origin_20261119/attribution.json"]:
        pins[p.relative_to(ROOT).as_posix()]=sha(p)
    for l in LABELS:
        f=V/"xiaomi_2221_2236_accuracy_origin_20261119"/l/"solution.trace"
        expected=read(V/"xiaomi_2221_2236_accuracy_origin_20261119/attribution.json")["sessions"][l]["trace_sha256"]
        assert sha(f)==expected
        pins[f.relative_to(ROOT).as_posix()]=expected
    return pins

def build():
    B.mkdir()
    p=old.PARENT.read_text(encoding="utf-8-sig")
    p=replace(p,"*Lc = *Pc = 0.0;","*Lc = *Pc = 0.0;\n    if(opt->ionoopt==IONOOPT_EST)return;")
    p=replace(p,"extern void s13_closure_begin",'''extern double fresh_sigma(void);
extern void fresh_prepare(gtime_t,int,const double*,const double*,const double*,int,int,const ppp_innovation_meta_t*,double,int);
extern void fresh_commit(gtime_t,int);
extern void s13_closure_begin''')
    # Metadata is required for per-row attribution on all three arms.
    p=replace(p,"if(ppp_innovation_log_enabled() || opt->ppp_baseline==MODE_C_NEW_ROBUST ||","if(opt->ionoopt==IONOOPT_EST || ppp_innovation_log_enabled() || opt->ppp_baseline==MODE_C_NEW_ROBUST ||")
    p=replace(p,"if(!row_meta && (smartphone_ppp_policy(opt).common_clock","if(!row_meta && (opt->ionoopt==IONOOPT_EST || smartphone_ppp_policy(opt).common_clock")
    p=replace(p,"        s13_closure_begin(xp);",'''        fresh_prepare(obs[0].time,i,xp,H,R,rtk->nx,nv,row_meta,fresh_sigma(),
                      getenv("FIELD_METHOD") && !strcmp(getenv("FIELD_METHOD"),"new_sat"));
        s13_closure_begin(xp);''')
    p=replace(p,"        s13_report(obs[0].time,rtk->sol.stat,i+1);","        fresh_commit(obs[0].time,rtk->sol.stat);\n        s13_report(obs[0].time,rtk->sol.stat,i+1);")
    (B/"ppp.c").write_text(p,encoding="utf-8")
    p=(ROOT/"core/pntpos.c").read_text(encoding="utf-8-sig")
    src=(PREV/"seed.inc").read_text(encoding="utf-8-sig")
    start=src.index("static double omission_up(");end=src.index("static void observe_seed(")
    p=replace(p,"static int pntpos_impl(",src[start:end]+'''
static int fresh_spp_ready;
static double fresh_spp_sigma;
double fresh_sigma(void){return fresh_spp_sigma;}
static int pntpos_impl(''')
    p=replace(p,"        estvel(obs,n,rs,dts,nav,&opt_,sol,azel_,vsat);",'''        if(startup && !fresh_spp_ready && getenv("FIELD_METHOD") && !strcmp(getenv("FIELD_METHOD"),"new_sat")){
            double pos[3],up[3];ecef2pos(sol->rr,pos);
            up[0]=cos(pos[0])*cos(pos[1]);up[1]=cos(pos[0])*sin(pos[1]);up[2]=sin(pos[0]);
            fresh_spp_sigma=fmin(15.0,omission_up(obs,n,rs,dts,var,svh,nav,&opt_,ssat,sol,vsat,up));
            fresh_spp_ready=1;
        }
        estvel(obs,n,rs,dts,nav,&opt_,sol,azel_,vsat);''')
    (B/"pntpos.c").write_text(p,encoding="utf-8")
    p=CMN.read_text(encoding="utf-8-sig")
    p=replace(p,"static int filter_(const double *x,",'#include "new_sat.inc"\nstatic int filter_(const double *x,')
    p=replace(p,'    matmulp("TN",m,m,n,H,F,Q);','''    matmulp("TN",m,m,n,H,F,Q);
    const int fresh_active=s13_capture && fresh_var>0;
    if(fresh_active){
        if(!physical || m!=fresh_nv || s13_pos_index[0]<0 || s13_pos_index[1]<0 || s13_pos_index[2]<0)abort();
        fresh_innovation(Q,m);fresh_cross(F,n,m);
    }''')
    p=replace(p,'        matmul("NN",n,m,m,F,Q,K);','        if(fresh_active)fresh_bias(Q,v,m);\n        matmul("NN",n,m,m,F,Q,K);')
    p=replace(p,'if (idx>=0) for (int col=0;col<m;col++) s13_kv[a]+=K[idx+n*col]*v[col];','''if(m!=fresh_nv)abort();
                if(idx>=0)for(int col=0;col<m;col++){
                    fresh_rows[col].kv[a]=K[idx+n*col]*v[col];
                    s13_kv[a]+=fresh_rows[col].kv[a];
                }''')
    p=replace(p,'                matmulp("NT",n,n,m,KR,K,Pp);','                matmulp("NT",n,n,m,KR,K,Pp);\n                if(fresh_active)fresh_joseph(Pp,K,n,m,KR);')
    (B/"rtkcmn.c").write_text(p,encoding="utf-8")
    rules=(ROOT/"build/build.cmd").read_text().splitlines();cmds=rules[:2]
    link=next(l for l in rules if l.startswith("link ") and str(ROOT/"bin/ppp_ssr_replay.exe") in l)
    for stem in ("pntpos","ppp","rtkcmn"):
        src=stem+".c";obj=stem+".obj"
        cl=next(l for l in rules if l.startswith("cl ") and str(ROOT/"core"/src) in l)
        cl=cl.replace(" /TC ",f' /I"{D}" /TC ').replace(str(ROOT/"core"/src),str(B/src)).replace(str(ROOT/"build"/obj),str(B/obj))
        cmds.extend([cl,"if errorlevel 1 exit /b 1"])
        link=link.replace(str(ROOT/"build"/obj),str(B/obj))
    batch=B/"build.cmd"
    batch.write_text("\n".join(cmds+[link.replace(str(ROOT/"bin/ppp_ssr_replay.exe"),str(B/"replay.exe")),"exit /b %errorlevel%"])+"\n")
    with (B/"build.log").open("wb") as log:
        subprocess.run(["cmd","/c",str(batch)],cwd=B,env=dict(os.environ,TMP=str(B),TEMP=str(B)),stdout=log,stderr=subprocess.STDOUT,check=True)

if __name__=="__main__":
    g=guards();(D/"guards_local.json").open("x").write(json.dumps(g,indent=2)+"\n")
    build()
    old.HERE=D;old.BUILD=B
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(old.replay,[(p,a) for a in ("new_sat","ema","original") for p in LABELS]))
    assert guards()==g
