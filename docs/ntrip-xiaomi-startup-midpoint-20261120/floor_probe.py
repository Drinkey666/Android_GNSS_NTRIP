"""Compare empirical variance floors with the original additive variance treatment."""
from followup import *
B3=D/"floor_build";ARMS3=("empirical_floor","floor_select")
def build3():
    B3.mkdir()
    for n in ("pntpos.c","rtkcmn.c","new_sat.inc"):
        (B3/n).write_bytes((B2/n).read_bytes())
    s=(B2/"ppp.c").read_text(encoding="utf-8-sig")
    s=rep(s,'extern int startup_variance_allowed(gtime_t);','extern int use_floor_mode(void);\nextern void floor_note(int,double);\nextern int startup_variance_allowed(gtime_t);')
    s=rep(s,'if(getenv("FIELD_METHOD") && !strcmp(getenv("FIELD_METHOD"),"carry_ema"))s13_scheme=EMA_ONLY;',
          'if(use_floor_mode() || (getenv("FIELD_METHOD") && !strcmp(getenv("FIELD_METHOD"),"carry_ema")))s13_scheme=EMA_ONLY;')
    s=rep(s,'        R[idx]=(R[idx]+(fs-1.0)*r->base)*fo;','''        if(use_floor_mode()){
            floor_note(r->idx,fs>1.?fs*r->base:0.);fs=1.;
        }
        R[idx]=(R[idx]+(fs-1.0)*r->base)*fo;''')
    (B3/"ppp.c").write_text(s,encoding="utf-8")
    s=(B2/"method.inc").read_text(encoding="utf-8-sig")
    s=rep(s,'static int high_weight,','''static double empirical_floor[FRESH_CAP];
int use_floor_mode(void){
    const char *a=getenv("FIELD_METHOD");return a && (!strcmp(a,"empirical_floor") || !strcmp(a,"floor_select"));
}
void floor_note(int i,double variance){if(i<0 || i>=FRESH_CAP)abort();empirical_floor[i]=variance;}
static int high_weight,''')
    (B3/"method.inc").write_text(s,encoding="utf-8")
    s=(B2/"reason.inc").read_text(encoding="utf-8-sig")
    s=rep(s,'reason_select=high_weight ||','reason_select=(arm && !strcmp(arm,"floor_select")) || high_weight ||')
    s=rep(s,'    vertical_evidence(precision,F,n,m);','''    if(use_floor_mode())for(int i=0;i<m;i++){
        if(fresh_rows[i].kind!=INNOV_GNSS_CODE || !isfinite(rr[i].peer) || rr[i].r0>rr[i].peer || rr[i].slip)continue;
        int peers=0;for(int j=0;j<m;j++)peers+=same_signal(i,j);
        if(peers>=3)rr[i].factor=fmax(rr[i].factor,fmin(20.,empirical_floor[i]/rr[i].r0));
    }
    vertical_evidence(precision,F,n,m);''')
    (B3/"reason.inc").write_text(s,encoding="utf-8")
    batch=B3/"build.cmd";batch.write_text((B2/"build.cmd").read_text().replace(str(B2),str(B3)))
    with (B3/"build.log").open("wb") as log:subprocess.run(["cmd","/c",str(batch)],cwd=B3,env=dict(os.environ,TMP=str(B3),TEMP=str(B3)),stdout=log,stderr=subprocess.STDOUT,check=True)
if __name__=="__main__":
    assert guards()==read(D/"guards_local.json");build3();old.HERE=D;old.BUILD=B3
    with ThreadPoolExecutor(4) as pool:list(pool.map(old.replay,[(l,a) for a in ARMS3 for l in LABELS]))
    assert guards()==read(D/"guards_local.json")
