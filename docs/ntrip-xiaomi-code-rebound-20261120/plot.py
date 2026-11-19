"""Plot only relative positioning errors and committed vertical update contributions."""
import os,csv
from pathlib import Path
D=Path(__file__).resolve().parent;os.environ.update(MPLCONFIGDIR=str(D/"plot_cache"),TMP=str(D),TEMP=str(D))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams.update({"font.family":["Microsoft YaHei","DejaVu Sans"],"axes.unicode_minus":False,"font.size":10})
def load(f):
    with (D/f).open() as s:return list(csv.DictReader(s))
def style(a):
    a.spines[["top","right"]].set_visible(False);a.set_axisbelow(True);a.grid(axis="y",color="#e1e6ec")
fig,(ax,bx)=plt.subplots(1,2,figsize=(12,4.7),layout="constrained")
data=load("target_diagnostics.csv")
for idx,(arm,name,col) in enumerate([("original","原版","#45566e"),("ema","EMA","#8c7352"),("selective","选择性降权","#087c71")]):
    pos=[j+(idx-1)*.24 for j in range(3)]
    vals=[float(next(r["net_all_rows_m"] for r in data if (r["arm"],r["satellite"],r["signal"])==(arm,sv,sig))) for sv,sig in (("C13","2I"),("G06","1C"),("C33","2I"))]
    ax.bar(pos,vals,width=.22,color=col,label=name)
ax.set_title("22:21 后半段 · 三条码的净贡献",loc="left",fontweight="bold")
ax.set_xticks(range(3),["北斗 C13 B1I","GPS G06 L1","北斗 C33 B1I"]);ax.set_ylabel("向上为正（米）")
ax.axhline(0,color="#51616d",lw=.8);ax.legend(frameon=False,loc="lower right")
data=[r for r in load("startup_epochs.csv") if r["session"]=="2236"];base={float(r["elapsed_from_first_Q6_s"]):float(r["up_m"]) for r in data if r["arm"]=="original"}
for arm,name,col,ls in [("new_sat","上一轮新增卫星修正","#72819b","--"),("carry","同步更新浮点模糊度","#007874","-"),("ema","EMA","#a26b28",":")]:
    rs=[r for r in data if r["arm"]==arm];t=[float(r["elapsed_from_first_Q6_s"]) for r in rs];v=[float(r["up_m"])-base[k] for k,r in zip(t,rs)]
    # Segment at real gaps.
    for j in reversed(range(1,len(t))):
        if t[j]-t[j-1]>1.5:t.insert(j,float("nan"));v.insert(j,float("nan"))
    bx.plot(t,v,lw=1.9,label=name,color=col,ls=ls)
bx.set_title("22:36 首分钟 · 比原版修回多少高程",loc="left",fontweight="bold")
bx.set_xlabel("距首个 Q6（秒）");bx.set_ylabel("相对原版的有符号高程差（米）")
bx.axhline(0,color="#51616d",lw=.8);bx.legend(frameon=False,loc="upper right")
for a in (ax,bx):style(a)
fig.savefig(D/"field_results.png",dpi=170)
