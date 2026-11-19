"""Follow-up after instantaneous block testing and vertical consensus on the frozen controls."""
from field import *
B2=D/"followup_build"
ARMS2=("carry_ema","high_weight","dual_evidence")
def build2():
    B2.mkdir()
    for name in ("ppp.c","pntpos.c","rtkcmn.c","new_sat.inc","reason.inc"):
        s=(B/name).read_text(encoding="utf-8-sig")
        if name in ("ppp.c","pntpos.c"):
            s=rep(s,'!strcmp(getenv("FIELD_METHOD"),"carry_block")','(!strcmp(getenv("FIELD_METHOD"),"carry_block") || !strcmp(getenv("FIELD_METHOD"),"carry_ema"))')
        if name=="ppp.c":
            s=rep(s,'static int s13_scheme, s13_epoch;','''extern int startup_variance_allowed(gtime_t);
extern void startup_variance_note(int,double,double);
static int s13_scheme, s13_epoch;''')
            s=rep(s,'    s13_scheme=s13_read_scheme();','''    s13_scheme=s13_read_scheme();
    if(getenv("FIELD_METHOD") && !strcmp(getenv("FIELD_METHOD"),"carry_ema"))s13_scheme=EMA_ONLY;''')
            s=rep(s,'        R[idx]=(R[idx]+(fs-1.0)*r->base)*fo;','''        if(getenv("FIELD_METHOD") && !strcmp(getenv("FIELD_METHOD"),"carry_ema")){
            if(!startup_variance_allowed(time))fs=1.;
            startup_variance_note(r->idx,R[idx],R[idx]+(fs-1.)*r->base);
        }
        R[idx]=(R[idx]+(fs-1.0)*r->base)*fo;''')
        if name=="reason.inc":
            s=rep(s,'reason_select=use_consensus ||','reason_select=high_weight || dual_evidence || use_consensus ||')
            s=rep(s,'reason_carry=use_block ||','reason_carry=carry_ema || use_block ||')
            s=rep(s,'        a->factor=fmin(4.,1.+2.*mean*mean);','''        if(high_weight && a->r0>0.5*a->peer && fabs(mean)<1.)continue;
        a->factor=fmin(4.,1.+2.*mean*mean);''')
            s=rep(s,'if(!fresh_first.time || timediff(reason_time,fresh_first)<60.)code_block(precision,m);','''if(dual_evidence || !fresh_first.time || timediff(reason_time,fresh_first)<60.)code_block(precision,m);
    if(dual_evidence)for(int i=0;i<m;i++)if(rr[i].factor>1. && (test_z[i]*rr[i].z<=0. || fabs(test_z[i])<1.))rr[i].factor=1.;''')
        (B2/name).write_text(s,encoding="utf-8")
    s=(D/"method.inc").read_text(encoding="utf-8-sig")
    s=rep(s,'static int use_block,','static double prior_r[FRESH_CAP],after_r[FRESH_CAP];\nstatic int high_weight,dual_evidence,carry_ema;\nstatic int use_block,')
    s=rep(s,'    use_block=arm','''    high_weight=arm && !strcmp(arm,"high_weight");
    dual_evidence=arm && !strcmp(arm,"dual_evidence");
    carry_ema=arm && !strcmp(arm,"carry_ema");
    use_block=arm''')
    s=rep(s,'static void code_block(','''int startup_variance_allowed(gtime_t t)
{
    return fresh_first.time && fresh_done && timediff(t,fresh_first)<60.;
}
void startup_variance_note(int row,double orig,double effective)
{
    if(row<0 || row>=FRESH_CAP)abort();prior_r[row]=orig;after_r[row]=effective;
}
static void code_block(''')
    s=rep(s,'        const double *m=model_terms[i];char sv[16];satno2id(fresh_rows[i].sat,sv);','''        const double *m=model_terms[i];char sv[16];satno2id(fresh_rows[i].sat,sv);
        if(carry_ema && after_r[i]>prior_r[i])trace(2,"$MID_EMA,%d,%.9f,%d,%d,%s,%s,%.12g,%.12g\\n",w,tow,
            fresh_trial,i,sv,code2obs(fresh_rows[i].signal),prior_r[i],after_r[i]);''')
    (B2/"method.inc").write_text(s,encoding="utf-8")
    batch=B2/"build.cmd";batch.write_text((B/"build.cmd").read_text().replace(str(B),str(B2)).replace(f'/I"{D}"',f'/I"{B2}"'))
    with (B2/"build.log").open("wb") as log:subprocess.run(["cmd","/c",str(batch)],cwd=B2,env=dict(os.environ,TMP=str(B2),TEMP=str(B2)),stdout=log,stderr=subprocess.STDOUT,check=True)
if __name__=="__main__":
    assert guards()==read(D/"guards_local.json");build2();old.HERE=D;old.BUILD=B2
    with ThreadPoolExecutor(4) as pool:list(pool.map(old.replay,[(l,a) for a in ARMS2 for l in LABELS]))
    assert guards()==read(D/"guards_local.json")
