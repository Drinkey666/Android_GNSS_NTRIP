"""Plot the two target windows using post-solution signed Up error."""
import csv
from pathlib import Path
import os
import math
D=Path(__file__).resolve().parent
os.environ["MPLCONFIGDIR"]=str(D/"plot_cache")
os.environ["TEMP"]=os.environ["TMP"]=str(D)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family":["Microsoft YaHei","DejaVu Sans"],"axes.unicode_minus":False,"font.size":10})
with (D/"common_epoch_errors.csv").open() as f: rows=list(csv.DictReader(f))
styles=[("original","原版","#1f2937","-",2.4),("seed","启动可信度","#c2750b",(0,(2.5,2.5)),1.5),
        ("drift","连续弧降权","#216ba9",(0,(5,3)),1.3),("ema","EMA","#008366","-",1.7)]
fig,axes=plt.subplots(1,2,figsize=(11.5,4.5),layout="constrained")
for ax,label,title in zip(axes,("2236","2221"),("22:36  ·  首个 Q6 起的 60 秒","22:21  ·  采集后半段")):
    sess=[r for r in rows if r["session"]==label]
    start=float(sess[0]["elapsed_s"])
    end=float(sess[-1]["elapsed_s"])
    selected=[r for r in sess if (float(r["elapsed_s"])-start<60 if label=="2236" else float(r["elapsed_s"])>=end/2)]
    for arm,name,color,ls,lw in styles:
        ts=[];ys=[];last=None
        for r in selected:
            t=float(r["elapsed_s"])
            if last is not None and t-last>1.5:ts.append(math.nan);ys.append(math.nan)
            ts.append((t-start) if label=="2236" else t/60);ys.append(float(r[arm+"_U_m"]));last=t
        ax.plot(ts,ys,color=color,ls=ls,lw=lw,label=name)
    ax.set_title(title,loc="left",fontweight="bold")
    ax.set_xlabel("距首次 Q6（秒）" if label=="2236" else "距采集开始（分钟）")
    ax.set_ylabel("高程误差 U（米）")
    ax.grid(axis="y",color="#dfe4e8");ax.spines[["top","right"]].set_visible(False)
    if label=="2221":ax.axvspan((end-60)/60,end/60,color="#8899aa",alpha=.10,zorder=0)
    if label=="2236":ax.legend(frameon=False,ncol=2,fontsize=9,loc="lower right")
fig.savefig(D/"height_comparison.png",dpi=170)
