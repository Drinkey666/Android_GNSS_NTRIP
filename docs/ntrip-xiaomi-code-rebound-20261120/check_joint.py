"""Reuse the preceding explicit augmented-state checker, including the ambiguity mapping."""
from probe import D,P,B,old,rep,read,guards
from score_rows import rows,equal
import csv,os,subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import cov_audit as parent
W=D/"joint_probe"
def main():
    W.mkdir()
    src=(B/"rtkcmn.c").read_text(encoding="utf-8-sig")
    hook=rep(parent.hook,"fwrite(fresh_up,sizeof(double),3,fp);","fwrite(compressed_lift,sizeof(double),n,fp);")
    anchor="    free(F); free(Q); free(K); free(I);"
    (W/"rtkcmn.c").write_text(rep(src,anchor,hook+anchor),encoding="utf-8")
    # Keep the same include text in the probe's source directory.
    (W/"new_sat.inc").write_bytes((B/"new_sat.inc").read_bytes())
    rules=(B/"build.cmd").read_text().splitlines()
    cl=next(l for l in rules if l.startswith("cl ") and str(B/"rtkcmn.c") in l)
    link=next(l for l in rules if l.startswith("link "))
    cl=cl.replace(str(B/"rtkcmn.c"),str(W/"rtkcmn.c")).replace(str(B/"rtkcmn.obj"),str(W/"rtkcmn.obj"))
    link=link.replace(str(B/"rtkcmn.obj"),str(W/"rtkcmn.obj")).replace(str(B/"replay.exe"),str(W/"replay.exe"))
    batch=W/"build.cmd";batch.write_text("\n".join(rules[:2]+[cl,"if errorlevel 1 exit /b 1",link,"exit /b %errorlevel%"])+"\n")
    with (W/"build.log").open("wb") as log:subprocess.run(["cmd","/c",str(batch)],cwd=W,env=dict(os.environ,TMP=str(W),TEMP=str(W)),stdout=log,stderr=subprocess.STDOUT,check=True)
    old.HERE=W;old.BUILD=W
    with ThreadPoolExecutor(2) as pool:list(pool.map(old.replay,[(l,"carry") for l in ("2221","2236")]))
    out={}
    for l in ("2221","2236"):
        p=W/(l+"_carry");orig=D/(l+"_carry");equal(rows(orig/"solution.csv"),rows(p/"solution.csv"))
        for f in ("observations.csv","corrections.csv"):assert old.digest(p/f)==old.digest(orig/f)
        with (p/"solution.trace").open() as trace:events=[s.partition("$NEW_EVENT,")[2].strip().split(",") for s in trace if "$NEW_EVENT," in s]
        assert len(events)==1 and events[0][2]=="6"
        with (p/("joint_trial_"+events[0][3]+".private")).open("rb") as s:
            n,m,*idx=np.fromfile(s,np.int32,5)
            def take(k):return np.fromfile(s,np.float64,k)
            var=take(1)[0];lift=take(n);g=take(m);x=take(n)
            def matrix(r,c):return take(r*c).reshape((r,c),order="F")
            P0=matrix(n,n);H=matrix(n,m);R=matrix(m,m);v=take(m);xp=take(n);Pp=matrix(n,n)
            assert not s.read()
        A=np.zeros((n+1,n+1));A[:n,:n]=P0;A[n,n]=var
        design=np.column_stack([H.T,g]);G=np.eye(n,n+1);G[:,n]=lift
        K=np.linalg.solve(design@A@design.T+R,design@A).T
        update=K@v;expected=x+G@update;M=np.eye(n+1)-K@design
        cov=G@(M@A@M.T+K@R@K.T)@G.T
        dx=float(np.max(abs(expected-xp)));dp=float(np.max(abs(cov-Pp)/np.maximum(1.,np.sqrt(np.outer(np.diag(cov),np.diag(cov))))))
        assert dx<1e-7 and dp<1e-8 and abs(update[-1]-float(events[0][6]))<1e-7
        out[l]=dict(ambiguities=int(np.count_nonzero(lift)-3),max_state_difference=dx,max_scaled_covariance_difference=dp)
    assert guards()==read(D/"guards_local.json")
    import json
    (D/"joint_check.json").write_text(json.dumps(out,indent=2)+"\n")
if __name__=="__main__":main()
