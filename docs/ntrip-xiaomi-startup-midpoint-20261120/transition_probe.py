"""Temporal intervention and reverse-order control using the same causal covariance readiness gate."""
from settle_probe import *
B5=D/"transition_build";ARMS5=("settled_add","settled_remove","soft_floor")
def build5():
    B5.mkdir()
    for n in ("rtkcmn.c","pntpos.c","new_sat.inc","ppp.c"):(B5/n).write_bytes((B4/n).read_bytes())
    s=(B4/"method.inc").read_text(encoding="utf-8-sig")
    s=rep(s,'static int settle_mode,','static int settled_add,settled_remove,soft_floor;\nstatic int settle_mode,')
    s=rep(s,'!strcmp(a,"native_floor_select"))','!strcmp(a,"native_floor_select") || !strcmp(a,"settled_add") || !strcmp(a,"settled_remove") || !strcmp(a,"soft_floor"))')
    s=rep(s,'    settle_mode=arm &&','''    settled_add=arm && !strcmp(arm,"settled_add");settled_remove=arm && !strcmp(arm,"settled_remove");
    soft_floor=arm && !strcmp(arm,"soft_floor");
    settle_mode=settled_add || settled_remove || (arm &&''')
    s=rep(s,'!strcmp(arm,"settled_select");','!strcmp(arm,"settled_select"));')
    (B5/"method.inc").write_text(s,encoding="utf-8")
    s=(B4/"reason.inc").read_text(encoding="utf-8-sig")
    s=rep(s,'reason_select=settle_mode ||','reason_select=soft_floor || settle_mode ||')
    s=rep(s,'(settle_mode && !ready)','(settle_mode && !settled_add && !settled_remove && !ready)')
    s=rep(s,'(!native_floor && rr[i].r0>rr[i].peer)','((settled_add || settled_remove || soft_floor)?rr[i].r0>4.*rr[i].peer:(!native_floor && rr[i].r0>rr[i].peer))')
    s=rep(s,'if(peers>=3)rr[i].factor=fmax(rr[i].factor,fmin(20.,empirical_floor[i]/rr[i].r0));','''if(peers<3 || (settled_add && !ready) || (settled_remove && ready))continue;
        double excess=fmax(0.,empirical_floor[i]/rr[i].r0-1.);
        if(soft_floor)excess*=fmin(1.,rr[i].peer/rr[i].r0);
        rr[i].factor=fmax(rr[i].factor,fmin(20.,1.+excess));''')
    (B5/"reason.inc").write_text(s,encoding="utf-8")
    batch=B5/"build.cmd";batch.write_text((B4/"build.cmd").read_text().replace(str(B4),str(B5)))
    with (B5/"build.log").open("wb") as log:subprocess.run(["cmd","/c",str(batch)],cwd=B5,env=dict(os.environ,TMP=str(B5),TEMP=str(B5)),stdout=log,stderr=subprocess.STDOUT,check=True)
if __name__=="__main__":
    assert guards()==read(D/"guards_local.json");build5();old.HERE=D;old.BUILD=B5
    with ThreadPoolExecutor(4) as pool:list(pool.map(old.replay,[(l,a) for a in ARMS5 for l in LABELS]))
    assert guards()==read(D/"guards_local.json")
