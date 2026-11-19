"""Same eligibility event and EMA window, with and without the vertical update."""
from memory_probe import *

B7=D/"startup_build"
ARMS7=("window_ema","carry_floor")

def build7():
    B7.mkdir()
    for name in ("ppp.c","pntpos.c","rtkcmn.c","method.inc","reason.inc","new_sat.inc"):
        s=(B2/name).read_text(encoding="utf-8")
        if name in ("ppp.c","pntpos.c"):
            expression='!strcmp(getenv("FIELD_METHOD"),"carry_ema")'
            assert expression in s
            s=s.replace(expression,'('+expression+' || !strcmp(getenv("FIELD_METHOD"),"window_ema") || !strcmp(getenv("FIELD_METHOD"),"carry_floor"))')
        if name=="ppp.c":
            s=rep(s,"            startup_variance_note(r->idx,R[idx],R[idx]+(fs-1.)*r->base);",'''            if(fs>1. && !strcmp(getenv("FIELD_METHOD"),"carry_floor"))
                fs=1.+fmax(0.,fs*r->base-R[idx])/r->base;
            startup_variance_note(r->idx,R[idx],R[idx]+(fs-1.)*r->base);''')
        if name=="method.inc":
            s=rep(s,'carry_ema=arm && !strcmp(arm,"carry_ema");',
                  'carry_ema=arm && (!strcmp(arm,"carry_ema") || !strcmp(arm,"window_ema") || !strcmp(arm,"carry_floor"));')
        if name=="new_sat.inc":
            s=rep(s,"static int fresh_done,","static int shadow_eligible;\nstatic int fresh_done,")
            s=rep(s,"    fresh_nv=nv;","    shadow_eligible=0;fresh_nv=nv;")
            s=rep(s,"    if(contrasts>=2)fresh_var=sigma*sigma;",'''    if(contrasts>=2){
        if(!strcmp(getenv("FIELD_METHOD"),"window_ema"))shadow_eligible=1;
        else fresh_var=sigma*sigma;
    }''')
            s=rep(s,"    if(fresh_var>0){",'''    if(shadow_eligible && q==SOLQ_PPP){
        fresh_done=1;
        trace(2,"$WINDOW_EVENT,%d,%.9f,%d,%d,%d\\n",w,tow,q,fresh_trial,fresh_n);
    }
    if(fresh_var>0){''')
        (B7/name).write_text(s,encoding="utf-8")
    batch=B7/"build.cmd"
    batch.write_text((B2/"build.cmd").read_text().replace(str(B2),str(B7)))
    with (B7/"build.log").open("wb") as log:
        subprocess.run(["cmd","/c",str(batch)],cwd=B7,env=dict(os.environ,TMP=str(B7),TEMP=str(B7)),stdout=log,stderr=subprocess.STDOUT,check=True)

if __name__=="__main__":
    assert guards()==read(D/"guards_local.json")
    build7()
    old.HERE=D
    old.BUILD=B7
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(old.replay,[(l,a) for a in ARMS7 for l in LABELS]))
    assert guards()==read(D/"guards_local.json")
