"""Remember a weak nominal weight across a short recovery of the same code arc."""
from transition_probe import *

B6 = D / "memory_build"
ARMS6 = ("memory_floor",)

def build6():
    B6.mkdir()
    for name in ("rtkcmn.c", "pntpos.c", "new_sat.inc", "ppp.c"):
        (B6/name).write_bytes((B5/name).read_bytes())
    s = (B5/"method.inc").read_text()
    s = rep(s, 'static int settled_add,', '''typedef struct {gtime_t last;int sig,weak,recovery;} weight_memory_t;
static weight_memory_t weight_memory[MAXSAT+1][NFREQ];
static int memory_floor;
static int settled_add,''')
    s = rep(s, '!strcmp(a,"soft_floor"))', '!strcmp(a,"soft_floor") || !strcmp(a,"memory_floor"))')
    s = rep(s, 'soft_floor=arm && !strcmp(arm,"soft_floor");',
            'memory_floor=arm && !strcmp(arm,"memory_floor");\n    soft_floor=memory_floor || (arm && !strcmp(arm,"soft_floor"));')
    (B6/"method.inc").write_text(s)
    s = (B5/"reason.inc").read_text()
    s = rep(s, '    vertical_evidence(precision,F,n,m);', '''    if(memory_floor)for(int i=0;i<m;i++){
        const fresh_row_t *r=fresh_rows+i;
        if(r->kind!=INNOV_GNSS_CODE || rr[i].slip)continue;
        const weight_memory_t *h=&weight_memory[r->sat][r->slot];
        double dt=timediff(reason_time,h->last);
        if(h->weak && h->sig==r->signal && dt>0. && dt<=2.)rr[i].factor=1.;
    }
    vertical_evidence(precision,F,n,m);''')
    s = rep(s, '        a->peer_k=n?middle(peers,n):NAN;', '''        a->peer_k=n?middle(peers,n):NAN;
        if(memory_floor && r->kind==INNOV_GNSS_CODE){
            weight_memory_t *h=&weight_memory[r->sat][r->slot];
            double dt=timediff(t,h->last);
            if(a->slip || h->sig!=r->signal || dt<=0. || dt>2.)h->weak=h->recovery=0;
            if(n>=3 && a->r0>4.*a->peer)h->weak=1;
            if(h->weak){
                if(n>=3 && a->r0<=a->peer){if(++h->recovery>=20)h->weak=h->recovery=0;}
                else h->recovery=0;
            }
            h->sig=r->signal;h->last=t;
        }''')
    (B6/"reason.inc").write_text(s)
    batch=B6/"build.cmd"
    batch.write_text((B5/"build.cmd").read_text().replace(str(B5),str(B6)))
    with (B6/"build.log").open("wb") as log:
        subprocess.run(["cmd","/c",str(batch)],cwd=B6,env=dict(os.environ,TMP=str(B6),TEMP=str(B6)),stdout=log,stderr=subprocess.STDOUT,check=True)

if __name__=="__main__":
    assert guards()==read(D/"guards_local.json")
    build6()
    old.HERE=D
    old.BUILD=B6
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(old.replay,[(label,ARMS6[0]) for label in LABELS]))
    assert guards()==read(D/"guards_local.json")
