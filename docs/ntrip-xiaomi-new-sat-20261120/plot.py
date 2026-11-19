"""Render two post-solution panels from the public relative-error tables."""
import csv,os
from pathlib import Path
D=Path(__file__).resolve().parent
os.environ.update(MPLCONFIGDIR=str(D/"plot_cache"),TMP=str(D),TEMP=str(D))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family":["Microsoft YaHei","DejaVu Sans"],"axes.unicode_minus":False,"font.size":10})
def load(n):
    with (D/n).open() as f:return list(csv.DictReader(f))
fig,(ax,bx)=plt.subplots(1,2,figsize=(12,4.5),layout="constrained",width_ratios=(1,1.22))
points=load("matched_epochs.csv")
for label,name,color,mark in (("2236","22:36","#006e69","o"),("2221","22:21","#956319","s")):
    r=[p for p in points if p["session"]==label];t0=float(r[0]["elapsed_s"])
    sel=[p for p in r if float(p["elapsed_s"])-t0<=10.1]
    ax.plot([float(p["elapsed_s"])-t0 for p in sel],[float(p["new_sat_U_m"])-float(p["original_U_m"]) for p in sel],
            color=color,label=name,marker=mark,ms=4,lw=1.7)
ax.axhline(0,color="#717579",lw=.7);ax.set_title("新增卫星修正能维持多久",loc="left",fontweight="bold")
ax.set_ylabel("新方案减原版的高程（米）");ax.set_xlabel("距首个 Q6（秒）");ax.legend(frameon=False)
signals=load("second_half_signal.csv")
signals0=[r for r in signals if r["arm"]=="original"]
sel=signals0[:5]+signals0[-2:][::-1]
for i,r in enumerate(sel):
    for a,off,color,title in (("original",-.17,"#3d5169","原版"),("ema",.17,"#178276","EMA")):
        q=next(x for x in signals if x["arm"]==a and (x["satellite"],x["signal"])==(r["satellite"],r["signal"]))
        bx.barh(i+off,float(q["net_m"]),height=.30,color=color,label=title if i==0 else None)
bx.set_yticks(range(len(sel)),[r["satellite"]+" "+r["signal"] for r in sel]);bx.invert_yaxis()
bx.axvline(0,color="#4a5158",lw=.9);bx.legend(frameon=False,loc="upper right")
bx.set_title("22:21 后半段 · 伪距累计垂向贡献",loc="left",fontweight="bold")
bx.set_xlabel("累计向下（负）／向上（正），米")
for a in (ax,bx):a.spines[["top","right"]].set_visible(False);a.set_axisbelow(True)
ax.grid(axis="y",color="#e3e5e8");bx.grid(axis="x",color="#e3e5e8")
fig.savefig(D/"startup_and_drift.png",dpi=175)
