"""Controlled PC replay. The estimator receives no evaluation reference."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE.parent / "xiaomi_2221_2236_20261119"
PARENT = SOURCE / "ema_build/ppp.c"
CLOSURE = HERE.parent / "brain_step13_adaptive_refine/rtkcmn.obj"
BUILD = HERE / "private"
LABELS = ("2221", "2236")
ARMS = ("original", "ema", "seed", "drift")

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

def guard():
    pins = {}
    def pin(name,path,expected=None):
        sha=digest(path)
        if expected is not None: assert sha==expected, name
        pins[name]=sha
    binaries=read(ROOT/"validation/build.json")["binaries"]
    assert len(binaries)==9
    for name,h in binaries.items(): pin("bin/"+name,ROOT/"bin"/name,h)
    for label in LABELS:
        src=SOURCE/label
        r=read(src/"SSR/replay.json")
        for k,h in r["input_sha256"].items(): pin(label+"/input/"+k,r["input_files"][k],h)
        for sub in ("SSR","B1_ema_only_v2"):
            for f in ("solution.csv","observations.csv","corrections.csv"):
                pin(label+"/"+sub+"/"+f,src/sub/f)
        pin(label+"/receipt",src/"SSR/replay.json")
        pin(label+"/capture_manifest",src/"imported/capture.json")
    for p in [PARENT,CLOSURE,ROOT/"core/pntpos.c",ROOT/"core/ppp.c",ROOT/"core/rtkcmn.c",ROOT/"build/build.cmd"]:
        pin(p.relative_to(ROOT).as_posix(),p)
    for p in sorted((ROOT/"build").glob("*.obj")):pin("build/"+p.name,p)
    return pins

def replace(s,old,new):
    assert s.count(old)==1,old
    return s.replace(old,new)

def build():
    BUILD.mkdir()
    s=PARENT.read_text(encoding="utf-8-sig")
    s=replace(s,"*Lc = *Pc = 0.0;","*Lc = *Pc = 0.0;\n    if(opt->ionoopt==IONOOPT_EST)return;")
    s=replace(s,"static int ppp_res(int post,",'#include "drift.inc"\nstatic int ppp_res(int post,')
    s=replace(s,"        applydoppsm_ppp(rtk, obs + i, P);\n\n        /* stack", """        if(field_collect && !post)field_observe(rtk,obs+i,nav,sys,L,P,x,gim_ok,map*gim,mexc?mexc+i*2*NFREQ:NULL);
        applydoppsm_ppp(rtk, obs + i, P);

        /* stack""")
    s=replace(s,"    s13_scheme=s13_read_scheme();","""    int field_stage=0,field_nc=0,field_ni=0;
    double field_add=0.0,field_mc=1.0,field_mi=1.0;
    field_collect=field_mature=0;memset(field_w,0,sizeof(field_w));
    s13_scheme=s13_read_scheme();""")
    s=replace(s,"if(ppp_innovation_log_enabled() || opt->ppp_baseline==MODE_C_NEW_ROBUST ||","if(field_is(\"drift\") || ppp_innovation_log_enabled() || opt->ppp_baseline==MODE_C_NEW_ROBUST ||")
    s=replace(s,"if(!row_meta && (smartphone_ppp_policy(opt).common_clock","if(!row_meta && (field_is(\"drift\") || smartphone_ppp_policy(opt).common_clock")
    s=replace(s,"        /* prefit residuals */","""        if(field_is("seed"))field_stage=field_seed_covariance(obs[0].time,Pp,rtk->nx,&field_add);
        field_collect=(i==0 && field_is("drift"));
        /* prefit residuals */""")
    s=replace(s,'#ifdef ENABLE_FILTER_DIAGNOSTIC\n    ppp_fd_state("BEFORE_CLOCK_SEED"','        field_collect=0;\n#ifdef ENABLE_FILTER_DIAGNOSTIC\n    ppp_fd_state("BEFORE_CLOCK_SEED"')
    s=replace(s,"        if(s13_scheme) s13_weight", '        if(field_is("drift"))field_apply(nv,R,row_meta,&field_nc,&field_ni,&field_mc,&field_mi);\n        if(s13_scheme) s13_weight')
    s=replace(s,"if (rtk->sol.stat==SOLQ_PPP) s13_closure_commit(obs[0].time,rtk->x);",r"""if (rtk->sol.stat==SOLQ_PPP){
            int w;double tow=time2gpst(obs[0].time,&w);
            s13_closure_commit(obs[0].time,rtk->x);
            field_finish_seed(field_stage);
            trace(2,"$FIELD_COMMIT,%d,%.9f,%d,%.9f,%d,%d,%d,%.9f,%.9f\n",w,tow,field_stage,field_add,field_mature,field_nc,field_ni,field_mc,field_mi);
        }""")
    (BUILD/"ppp.c").write_text(s,encoding="utf-8")
    s=(ROOT/"core/pntpos.c").read_text(encoding="utf-8-sig")
    s=replace(s,"static int pntpos_impl(",'#include "seed.inc"\nstatic int pntpos_impl(')
    s=replace(s,"        estvel(obs,n,rs,dts,nav,&opt_,sol,azel_,vsat);", """        if(startup && getenv("FIELD_METHOD") && !strcmp(getenv("FIELD_METHOD"),"seed"))
            observe_seed(obs,n,rs,dts,var,svh,nav,&opt_,ssat,sol,vsat);
        estvel(obs,n,rs,dts,nav,&opt_,sol,azel_,vsat);""")
    (BUILD/"pntpos.c").write_text(s,encoding="utf-8")
    rules=(ROOT/"build/build.cmd").read_text().splitlines()
    cmds=rules[:2]
    link=next(l for l in rules if l.startswith("link ") and str(ROOT/"bin/ppp_ssr_replay.exe") in l)
    for stem in ("pntpos","ppp"):
        src=stem+".c";obj=stem+".obj"
        cl=next(l for l in rules if l.startswith("cl ") and str(ROOT/"core"/src) in l)
        cl=cl.replace(" /TC ",f' /I"{HERE}" /TC ').replace(str(ROOT/"core"/src),str(BUILD/src)).replace(str(ROOT/"build"/obj),str(BUILD/obj))
        cmds.extend([cl,"if errorlevel 1 exit /b 1"])
        link=link.replace(str(ROOT/"build"/obj),str(BUILD/obj))
    link=link.replace(str(ROOT/"build/rtkcmn.obj"),str(CLOSURE)).replace(str(ROOT/"bin/ppp_ssr_replay.exe"),str(BUILD/"replay.exe"))
    batch=BUILD/"build.cmd";batch.write_text("\n".join(cmds+[link,"exit /b %errorlevel%"])+"\n")
    with (BUILD/"build.log").open("wb") as log:
        subprocess.run(["cmd","/c",str(batch)],cwd=BUILD,env=dict(os.environ,TMP=str(BUILD),TEMP=str(BUILD)),stdout=log,stderr=subprocess.STDOUT,check=True)

def replay(pair, audit=False):
    label,arm=pair
    d=HERE/(("sigma_" if audit else "")+label+"_"+arm)
    d.mkdir()
    receipt=read(SOURCE/label/"SSR/replay.json")
    args=receipt["command"].copy()
    assert not {"--ru","--reference"}.intersection(args)
    args[0]=str(BUILD/"replay.exe")
    for flag in ("--ssr-diagnostic","--result-file","--state-dump","--obs-dump","--trace"):
        i=args.index(flag)+1
        args[i]=str(d/Path(args[i]).name)
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(("RTK_PPP_","STEP","FIELD_","XIAOMI_","NTRIP_PRIVATE_","AUDIT_","WHU_EAST_PROBE"))}
    env.update(TMP=str(d),TEMP=str(d),FIELD_METHOD=arm,STEP13_SCHEME="B1_ema_only" if arm=="ema" else "CONTROL_NO_R_CHANGE")
    with (d/"console.log").open("wb") as log:
        subprocess.run(args,cwd=d,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    print(label,arm,"finished",flush=True)

if __name__=="__main__":
    before=guard()
    guardfile=HERE/"guards_local.json"
    if guardfile.exists():assert before==read(guardfile)
    else:guardfile.write_text(json.dumps(before,indent=2)+"\n")
    build()
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        list(pool.map(replay,[(p,a) for a in ("drift","seed","original","ema") for p in LABELS]))
    assert guard()==before
