"""Read out projected prior/posterior vertical variance without changing filter math."""
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
import experiment as e

def main():
    primary=e.BUILD
    work=e.HERE/"sigma_build"
    work.mkdir()
    s=(primary/"ppp.c").read_text(encoding="utf-8-sig")
    s=e.replace(s,'#include "drift.inc"',r'''#include "drift.inc"
static double field_up_sigma(const double *x,const double *P,int nx)
{
    double llh[3],u[3],var=0.0;
    ecef2pos(x,llh);
    u[0]=cos(llh[0])*cos(llh[1]);u[1]=cos(llh[0])*sin(llh[1]);u[2]=sin(llh[0]);
    for(int j=0;j<3;j++)for(int k=0;k<3;k++)var+=u[j]*P[j+k*nx]*u[k];
    return var>=0.0?sqrt(var):NAN;
}''')
    s=e.replace(s,'double field_add=0.0','double field_pred_sigma=0.0,field_add=0.0')
    s=e.replace(s,'        field_collect=(i==0','        field_pred_sigma=field_up_sigma(xp,Pp,rtk->nx);\n        field_collect=(i==0')
    s=e.replace(s,'            field_finish_seed(field_stage);',r'''            field_finish_seed(field_stage);
            trace(2,"$FIELD_SIGMA,%d,%.9f,%.9f,%.9f\n",w,tow,field_pred_sigma,field_up_sigma(rtk->x,rtk->P,rtk->nx));''')
    (work/"ppp.c").write_text(s,encoding="utf-8")
    lines=(primary/"build.cmd").read_text().splitlines()
    cmd=next(l for l in lines if l.startswith("cl ") and str(primary/"ppp.c") in l)
    link=next(l for l in lines if l.startswith("link "))
    lines=lines[:2]+[cmd.replace(str(primary/"ppp.c"),str(work/"ppp.c")).replace(str(primary/"ppp.obj"),str(work/"ppp.obj")),"if errorlevel 1 exit /b 1",
        link.replace(str(primary/"ppp.obj"),str(work/"ppp.obj")).replace(str(primary/"replay.exe"),str(work/"replay.exe")),"exit /b %errorlevel%"]
    batch=work/"build.cmd";batch.write_text("\n".join(lines)+"\n")
    with (work/"build.log").open("wb") as log:
        subprocess.run(["cmd","/c",str(batch)],cwd=work,env=dict(os.environ,TMP=str(work),TEMP=str(work)),stdout=log,stderr=subprocess.STDOUT,check=True)
    e.BUILD=work
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(lambda pair:e.replay(pair,True),[(p,a) for p in e.LABELS for a in ("original","seed")]))
if __name__=="__main__":main()
