"""Separate tests of learned code scatter across all peers and of a settled vertical covariance."""
from floor_probe import *
B4=D/"settle_build"
ARMS4=("native_floor","native_floor_select","settled_select")
def build4():
    B4.mkdir()
    for n in ("rtkcmn.c","pntpos.c","new_sat.inc"):(B4/n).write_bytes((B3/n).read_bytes())
    s=(B3/"ppp.c").read_text(encoding="utf-8-sig")
    s=rep(s,'extern int use_floor_mode(void);','extern void settle_commit(gtime_t,int,const double*,const double*,int);\nextern int use_floor_mode(void);')
    s=rep(s,'        fresh_commit(obs[0].time,rtk->sol.stat);','        settle_commit(obs[0].time,rtk->sol.stat,rtk->x,rtk->P,rtk->nx);\n        fresh_commit(obs[0].time,rtk->sol.stat);')
    (B4/"ppp.c").write_text(s,encoding="utf-8")
    s=(B3/"method.inc").read_text(encoding="utf-8-sig")
    s=rep(s,'static double empirical_floor[FRESH_CAP];','''static double empirical_floor[FRESH_CAP],sigma_history[30];
static int settle_mode,ready,nhist,ihist,native_floor;
static gtime_t last_commit;
void settle_commit(gtime_t time,int q,const double *x,const double *P,int n){
    if(!settle_mode || q!=SOLQ_PPP || ready)return;
    double dt=timediff(time,last_commit),pos[3],up[3],v=0.;
    if(dt<=0. || dt>1.5){nhist=ihist=0;}
    last_commit=time;ecef2pos(x,pos);up[0]=cos(pos[0])*cos(pos[1]);up[1]=cos(pos[0])*sin(pos[1]);up[2]=sin(pos[0]);
    for(int i=0;i<3;i++)for(int j=0;j<3;j++)v+=up[i]*P[i+j*n]*up[j];
    sigma_history[ihist]=sqrt(v);ihist=(ihist+1)%30;if(nhist<30)nhist++;
    if(nhist==30){
        double lo=sigma_history[0],hi=lo;
        for(int j=1;j<30;j++){lo=fmin(lo,sigma_history[j]);hi=fmax(hi,sigma_history[j]);}
        if(lo>0. && hi<=1.10*lo){ready=1;int w;double tow=time2gpst(time,&w);
            trace(2,"$SETTLED,%d,%.9f,%.12g,%.12g\\n",w,tow,lo,hi);}
    }
}
''')
    s=rep(s,'!strcmp(a,"floor_select"))','!strcmp(a,"floor_select") || !strcmp(a,"native_floor") || !strcmp(a,"native_floor_select"))')
    s=rep(s,'    high_weight=arm','''    native_floor=arm && (!strcmp(arm,"native_floor") || !strcmp(arm,"native_floor_select"));
    settle_mode=arm && !strcmp(arm,"settled_select");
    high_weight=arm''')
    (B4/"method.inc").write_text(s,encoding="utf-8")
    s=(B3/"reason.inc").read_text(encoding="utf-8-sig")
    s=rep(s,'reason_select=(arm && !strcmp(arm,"floor_select"))','reason_select=settle_mode || (arm && (!strcmp(arm,"floor_select") || !strcmp(arm,"native_floor_select")))')
    s=rep(s,'if(!reason_select || r->kind','if((settle_mode && !ready) || !reason_select || r->kind')
    s=rep(s,'rr[i].r0>rr[i].peer || rr[i].slip','(!native_floor && rr[i].r0>rr[i].peer) || rr[i].slip')
    (B4/"reason.inc").write_text(s,encoding="utf-8")
    batch=B4/"build.cmd";batch.write_text((B3/"build.cmd").read_text().replace(str(B3),str(B4)))
    with (B4/"build.log").open("wb") as log:subprocess.run(["cmd","/c",str(batch)],cwd=B4,env=dict(os.environ,TMP=str(B4),TEMP=str(B4)),stdout=log,stderr=subprocess.STDOUT,check=True)
if __name__=="__main__":
    assert guards()==read(D/"guards_local.json");build4();old.HERE=D;old.BUILD=B4
    with ThreadPoolExecutor(4) as pool:list(pool.map(old.replay,[(l,a) for a in ("settled_select","native_floor","native_floor_select") for l in LABELS]))
    assert guards()==read(D/"guards_local.json")
