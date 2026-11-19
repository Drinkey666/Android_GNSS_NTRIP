"""Apply the identical startup-window EMA and new-satellite update without lifting ambiguities."""
from startup_ablation import *

B8=D/"ambiguity_build"
ARMS8=("new_sat_window",)

def build8():
    B8.mkdir()
    for name in ("ppp.c","pntpos.c","rtkcmn.c","method.inc","reason.inc","new_sat.inc"):
        s=(B7/name).read_text(encoding="utf-8")
        if name in ("ppp.c","pntpos.c"):
            original='!strcmp(getenv("FIELD_METHOD"),"window_ema")'
            assert original in s
            s=s.replace(original,'('+original+' || !strcmp(getenv("FIELD_METHOD"),"new_sat_window"))')
        if name=="method.inc":
            s=rep(s,'!strcmp(arm,"window_ema")','(!strcmp(arm,"window_ema") || !strcmp(arm,"new_sat_window"))')
        if name=="reason.inc":
            s=rep(s,'reason_carry=carry_ema ||','reason_carry=(carry_ema && strcmp(arm,"new_sat_window")) ||')
        (B8/name).write_text(s,encoding="utf-8")
    batch=B8/"build.cmd"
    batch.write_text((B7/"build.cmd").read_text().replace(str(B7),str(B8)))
    with (B8/"build.log").open("wb") as log:
        subprocess.run(["cmd","/c",str(batch)],cwd=B8,env=dict(os.environ,TMP=str(B8),TEMP=str(B8)),stdout=log,stderr=subprocess.STDOUT,check=True)

if __name__=="__main__":
    assert guards()==read(D/"guards_local.json")
    build8()
    old.HERE=D
    old.BUILD=B8
    with ThreadPoolExecutor(2) as pool:
        list(pool.map(old.replay,[(l,ARMS8[0]) for l in LABELS]))
    assert guards()==read(D/"guards_local.json")
