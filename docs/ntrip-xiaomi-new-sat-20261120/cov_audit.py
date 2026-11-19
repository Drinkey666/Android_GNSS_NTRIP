"""Independently reconstruct the committed startup trial as an explicit extra-state filter."""
import csv,json,os,subprocess
from concurrent.futures import ThreadPoolExecutor
from run import D,B,LABELS,old,replace,guards,read
from score_rows import rows,equal
import numpy as np
W=D/"joint_probe"
hook=r"""
    if(fresh_active && !info){
        char name[64];sprintf(name,"joint_trial_%d.private",fresh_trial);
        FILE *fp=fopen(name,"wb");if(!fp)abort();
        int dims[5]={n,m,s13_pos_index[0],s13_pos_index[1],s13_pos_index[2]};
        fwrite(dims,sizeof(int),5,fp);fwrite(&fresh_var,sizeof(double),1,fp);
        fwrite(fresh_up,sizeof(double),3,fp);
        for(int j=0;j<m;j++)fwrite(&fresh_rows[j].g,sizeof(double),1,fp);
        fwrite(x,sizeof(double),n,fp);fwrite(P,sizeof(double),n*n,fp);
        fwrite(H,sizeof(double),n*m,fp);fwrite(R,sizeof(double),m*m,fp);
        fwrite(v,sizeof(double),m,fp);fwrite(xp,sizeof(double),n,fp);
        fwrite(Pp,sizeof(double),n*n,fp);fclose(fp);
    }
"""
def compare(f):
    with f.open("rb") as s:
        n,m,*idx=np.fromfile(s,np.int32,5)
        def take(count):return np.fromfile(s,np.float64,count)
        var=take(1)[0];up=take(3);g=take(m);x=take(n)
        P=take(n*n).reshape((n,n),order="F");H=take(n*m).reshape((n,m),order="F")
        R=take(m*m).reshape((m,m),order="F");v=take(m);expected=take(n)
        expected_cov=take(n*n).reshape((n,n),order="F");assert not s.read()
    A=np.zeros((n+1,n+1));A[:n,:n]=P;A[n,n]=var
    design=np.column_stack([H.T,g])
    innovation=design@A@design.T+R
    gain=np.linalg.solve(innovation,design@A).T
    G=np.eye(n,n+1);G[idx,n]=up
    upd=gain@v;yp=x+G@upd
    M=np.eye(n+1)-gain@design
    cov=G@(M@A@M.T+gain@R@gain.T)@G.T
    max_abs=float(np.max(abs(yp-expected)))
    cov_err=float(np.max(abs(cov-expected_cov)/np.maximum(1.,np.sqrt(np.outer(np.diag(cov),np.diag(cov))))))
    assert max_abs<1e-7 and cov_err<1e-8
    return dict(compressed_states=int(n),rows=int(m),max_abs_state_difference=max_abs,
                max_covariance_error_scaled_by_state_sigmas=cov_err,bias_m=float(upd[-1]))
def main():
    W.mkdir();src=(B/"rtkcmn.c").read_text(encoding="utf-8-sig")
    anchor="    free(F); free(Q); free(K); free(I);"
    (W/"rtkcmn.c").write_text(replace(src,anchor,hook+anchor),encoding="utf-8")
    rules=(B/"build.cmd").read_text().splitlines()
    cl=next(l for l in rules if l.startswith("cl ") and str(B/"rtkcmn.c") in l)
    cl=cl.replace(str(B/"rtkcmn.c"),str(W/"rtkcmn.c")).replace(str(B/"rtkcmn.obj"),str(W/"rtkcmn.obj"))
    link=next(l for l in rules if l.startswith("link "))
    link=link.replace(str(B/"rtkcmn.obj"),str(W/"rtkcmn.obj")).replace(str(B/"replay.exe"),str(W/"replay.exe"))
    batch=W/"build.cmd";batch.write_text("\n".join(rules[:2]+[cl,"if errorlevel 1 exit /b 1",link,"exit /b %errorlevel%"])+"\n")
    with (W/"build.log").open("wb") as log:subprocess.run(["cmd","/c",str(batch)],cwd=W,
        env=dict(os.environ,TMP=str(W),TEMP=str(W)),stdout=log,stderr=subprocess.STDOUT,check=True)
    old.HERE=W;old.BUILD=W
    with ThreadPoolExecutor(2) as pool:list(pool.map(old.replay,[(label,"new_sat") for label in LABELS]))
    out={}
    for e in rows(D/"startup_events.csv"):
        label=e["session"];run=W/(label+"_new_sat");orig=D/(label+"_new_sat")
        equal(rows(orig/"solution.csv"),rows(run/"solution.csv"))
        for f in ("observations.csv","corrections.csv"):assert old.digest(orig/f)==old.digest(run/f)
        r=compare(run/("joint_trial_"+e["trial"]+".private"))
        assert abs(r["bias_m"]-float(e["estimated_offset_m"]))<1e-7
        out[label]=r
    assert guards()==read(D/"guards_local.json")
    (D/"joint_check.json").write_text(json.dumps(out,indent=2)+"\n")
if __name__=="__main__":main()
