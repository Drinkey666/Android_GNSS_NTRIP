"""Build isolated selectivity and ambiguity-transfer candidates against the preceding PC probe."""
from pathlib import Path
import sys,os,json,subprocess
from concurrent.futures import ThreadPoolExecutor
D=Path(__file__).resolve().parent;V=D.parent;ROOT=V.parent
P=V/"xiaomi_2221_2236_new_sat_20261120"
sys.path.insert(0,str(P))
import run as prev
old=prev.old;SRC=prev.SRC;B=D/"private";LABELS=prev.LABELS
ARMS=("original","ema","new_sat","selective","carry")
read=prev.read;sha=prev.sha;rep=prev.replace
def guards():
    g=prev.guards();assert g==read(P/"guards_local.json")
    for n in ("new_sat.inc","run.py","score_rows.py","verification.json","joint_check.json","second_half_signal.csv",
              "private/pntpos.c","private/ppp.c","private/rtkcmn.c","private/build.cmd"):
        g["parent/"+n]=sha(P/n)
    for label in LABELS:
        for arm in ("original","ema","new_sat"):
            path=P/(label+"_"+arm)/"solution.csv";h=sha(path)
            assert h==read(P/"verification.json")["sessions"][label][arm]["solution_sha256"]
            g[label+"/"+arm+"/solution"]=h
    return g
def build():
    B.mkdir()
    both='(!strcmp(getenv("FIELD_METHOD"),"new_sat") || !strcmp(getenv("FIELD_METHOD"),"carry"))'
    p=(P/"private/pntpos.c").read_text(encoding="utf-8-sig")
    (B/"pntpos.c").write_text(rep(p,'!strcmp(getenv("FIELD_METHOD"),"new_sat")',both),encoding="utf-8")
    p=(P/"private/ppp.c").read_text(encoding="utf-8-sig")
    p=rep(p,'!strcmp(getenv("FIELD_METHOD"),"new_sat")',both)
    p=rep(p,'extern void fresh_commit','''extern void reason_start(gtime_t,int,double*,const ppp_innovation_meta_t*);
extern void reason_ambiguity(int,int,const double*);
extern void fresh_commit''')
    p=rep(p,'        s13_closure_begin(xp);','''        reason_start(obs[0].time,nv,R,row_meta);
        for(int z=0;z<nv;z++)if(row_meta[z].measurement_class==INNOV_GNSS_PHASE){
            int amb=IB(row_meta[z].sat,row_meta[z].frequency_slot,opt);
            if(H[amb+z*rtk->nx]!=1.0)abort();
            reason_ambiguity(z,amb,H+z*rtk->nx);
        }
        s13_closure_begin(xp);''')
    (B/"ppp.c").write_text(p,encoding="utf-8")
    p=(P/"new_sat.inc").read_text(encoding="utf-8-sig")
    p=rep(p,"void fresh_prepare(",'#include "reason.inc"\nvoid fresh_prepare(')
    p=rep(p,'    for(int a=0;a<3;a++)for(int j=0;j<m;j++)','''    if(reason_carry){
        for(int i=0;i<n;i++)if(compressed_lift[i]!=0.)for(int j=0;j<m;j++)
            F[i+j*n]+=compressed_lift[i]*fresh_var*fresh_rows[j].g;
        return;
    }
    for(int a=0;a<3;a++)for(int j=0;j<m;j++)''')
    p=rep(p,'        for(int j=0;j<m;j++)work[i]-=','        if(reason_carry)work[i]=compressed_lift[i];\n        for(int j=0;j<m;j++)work[i]-=')
    p=rep(p,'    if(q==SOLQ_PPP && !fresh_first.time)','    reason_report(t,q);\n    if(q==SOLQ_PPP && !fresh_first.time)')
    (B/"new_sat.inc").write_text(p,encoding="utf-8")
    p=(P/"private/rtkcmn.c").read_text(encoding="utf-8-sig")
    p=rep(p,'    if (!info && !(info=matinv(Q,m))) {\n        if(fresh_active)', '    if(!info && s13_capture)info=reason_prefit(Q,v,m);\n    if (!info && !(info=matinv(Q,m))) {\n        if(fresh_active)')
    p=rep(p,'                    fresh_rows[col].kv[a]=','                    rr[col].gain[a]=K[idx+n*col];\n                    fresh_rows[col].kv[a]=')
    p=rep(p,'for (i=0;i<k;i++) if (ix[i]<3) s13_pos_index[ix[i]]=i;','for (i=0;i<k;i++) if (ix[i]<3) s13_pos_index[ix[i]]=i;\n        reason_compress(ix,k);')
    (B/"rtkcmn.c").write_text(p,encoding="utf-8")
    rules=(P/"private/build.cmd").read_text().replace(str(P/"private"),str(B)).replace(f'/I"{P}"',f'/I"{D}"')
    batch=B/"build.cmd";batch.write_text(rules)
    with (B/"build.log").open("wb") as log:subprocess.run(["cmd","/c",str(batch)],cwd=B,
        env=dict(os.environ,TMP=str(B),TEMP=str(B)),stdout=log,stderr=subprocess.STDOUT,check=True)
if __name__=="__main__":
    g=guards()
    with (D/"guards_local.json").open("x") as f:json.dump(g,f,indent=2)
    build();old.HERE=D;old.BUILD=B
    with ThreadPoolExecutor(4) as pool:list(pool.map(old.replay,[(p,a) for a in ("carry","selective","new_sat","original","ema") for p in LABELS]))
    assert g==guards()
