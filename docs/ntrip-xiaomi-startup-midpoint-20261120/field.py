from pathlib import Path
import sys,os,json,subprocess
from concurrent.futures import ThreadPoolExecutor
D=Path(__file__).resolve().parent;P=D.parent/"xiaomi_code_and_rebound_20261120"
sys.path.insert(0,str(P))
import probe as parent
from score_rows import rows,epoch,sec,key,projection,equal
from evaluate_solution import enu
old=parent.old;ROOT=parent.ROOT;SRC=parent.SRC;B=D/"private"
rep=parent.rep;read=parent.read;sha=parent.sha;LABELS=("2221","2236")
ARMS=("original","ema","selective","carry","consensus","carry_block")
def guards():
    g=parent.guards();assert g==read(P/"guards_local.json")
    for n in ("private/ppp.c","private/pntpos.c","private/rtkcmn.c","private/new_sat.inc","private/build.cmd","reason.inc","probe.py",
              "accuracy.csv","actions.csv","verification.json","rebound_rows.csv","REPORT.md"):
        g["rebound/"+n]=sha(P/n)
    for l in LABELS:
        for arm in ARMS[:4]:
            for n in ("solution.csv","solution.trace"):
                g["rebound/"+l+"/"+arm+"/"+n]=sha(P/(l+"_"+arm)/n)
    return g
def build():
    B.mkdir()
    for n in ("ppp.c","pntpos.c"):
        s=(P/"private"/n).read_text(encoding="utf-8-sig")
        s=rep(s,'!strcmp(getenv("FIELD_METHOD"),"carry")','(!strcmp(getenv("FIELD_METHOD"),"carry") || !strcmp(getenv("FIELD_METHOD"),"carry_block"))')
        if n=="ppp.c":
            s=rep(s,"static int ppp_res(int post,","extern void midpoint_model(int,double,double,double,double,double,double,double);\nstatic int ppp_res(int post,")
            s=rep(s,"            if (v) v[nv] = res;","""            if(!post && row_meta && code)midpoint_model(nv,y-obs[i].P[frq],r-obs[i].P[frq],cdtr,
                -CLIGHT*dts[i*2],dtrp,C*dion,dcb+bias);
            if (v) v[nv] = res;""")
        (B/n).write_text(s,encoding="utf-8")
    (B/"new_sat.inc").write_bytes((P/"private/new_sat.inc").read_bytes())
    s=(P/"reason.inc").read_text(encoding="utf-8-sig")
    s=rep(s,"static int double_order(",'#include "method.inc"\nstatic int double_order(')
    s=rep(s,'reason_select=arm && !strcmp(arm,"selective");','method_begin(arm);\n    reason_select=use_consensus || (arm && !strcmp(arm,"selective"));')
    s=rep(s,'reason_carry=arm && !strcmp(arm,"carry");','reason_carry=use_block || (arm && !strcmp(arm,"carry"));')
    s=rep(s,'double *S,const double *v,int m)','double *S,const double *v,int m,const double *F,int n)')
    s=rep(s,'    for(int i=0;i<m;i++)if(rr[i].factor>1.){','''    if(!fresh_first.time || timediff(reason_time,fresh_first)<60.)code_block(precision,m);
    vertical_evidence(precision,F,n,m);
    for(int i=0;i<m;i++)if(rr[i].factor>1.){''')
    s=rep(s,'    if(q!=SOLQ_PPP)return;','    if(q!=SOLQ_PPP)return;\n    midpoint_report(t);')
    (B/"reason.inc").write_text(s,encoding="utf-8")
    s=(P/"private/rtkcmn.c").read_text(encoding="utf-8-sig")
    s=rep(s,'reason_prefit(Q,v,m);','reason_prefit(Q,v,m,F,n);')
    s=rep(s,'        matmul("NN",n,m,m,F,Q,K);','        matmul("NN",n,m,m,F,Q,K);\n        if(s13_capture)vertical_gain(K,n,m);')
    (B/"rtkcmn.c").write_text(s,encoding="utf-8")
    batch=B/"build.cmd";batch.write_text((P/"private/build.cmd").read_text().replace(str(P/"private"),str(B)).replace(f'/I"{P}"',f'/I"{D}"'))
    with (B/"build.log").open("wb") as log:subprocess.run(["cmd","/c",str(batch)],cwd=B,env=dict(os.environ,TMP=str(B),TEMP=str(B)),stdout=log,stderr=subprocess.STDOUT,check=True)
if __name__=="__main__":
    with (D/"guards_local.json").open("x") as f:json.dump(guards(),f,indent=2)
    build();old.HERE=D;old.BUILD=B
    with ThreadPoolExecutor(4) as pool:list(pool.map(old.replay,[(l,a) for a in ("consensus","carry_block","carry","selective","ema","original") for l in LABELS]))
    assert guards()==read(D/"guards_local.json")
