"""Plot paired signed height differences. Break lines at lost Q6 epochs."""
import csv
import os
from pathlib import Path

D=Path(__file__).resolve().parent
os.environ.update(MPLCONFIGDIR=str(D/"plot_cache"),TMP=str(D),TEMP=str(D))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

def draw(ax, rows, arm, label, color, linestyle, origin):
    tx=[];dy=[]
    for row in rows:
        if row["arm"]!=arm:
            continue
        t=float(row[origin])
        if tx and t-tx[-1]>1.5:
            tx.append(float("nan"));dy.append(float("nan"))
        tx.append(t);dy.append(float(row["signed_U_delta_original_m"]))
    ax.plot(tx,dy,label=label,color=color,linestyle=linestyle,lw=1.8)

def main():
    with (D/"matched_errors.csv").open() as f:
        data=list(csv.DictReader(f))
    plt.rcParams.update({"font.family":["Microsoft YaHei","DejaVu Sans"],"axes.unicode_minus":False,"font.size":10})
    fig,(left,right)=plt.subplots(1,2,figsize=(12.5,4.7),layout="constrained")
    for ax in (left,right):
        ax.spines[["top","right"]].set_visible(False);ax.set_axisbelow(True)
        ax.grid(axis="y",color="#dee5eb");ax.axhline(0,color="#5d6974",lw=.9)
        ax.set_ylabel("相对原版的有符号高程差（米）")
    for arm,label,color,ls in [("selective","上一轮选择性降权","#a05c36","--"),("memory_floor","本轮带保护期的定权","#087769","-")]:
        draw(left,[r for r in data if r["session"]=="2221"],arm,label,color,ls,"elapsed_raw_s")
    left.axvline(379.002,color="#78889b",ls=":",lw=1.3,label="后半段起点")
    left.scatter([102.001,162.001,379.002],[.420397,-.00129,-.128786],s=22,color="#a05c36",zorder=5)
    left.set_title("22:21 · 降权改变高程的时段",loc="left",fontweight="bold")
    left.set_xlabel("距采集开始（秒）");left.legend(frameon=False,fontsize=9)
    for arm,label,color,ls in [("carry","仅同步模糊度","#8d7054","--"),("window_ema","仅启动窗 EMA（与全程 EMA 重合）","#635a99","-."),
                               ("carry_ema","同步模糊度 + 启动窗 EMA","#00796e","-")]:
        draw(right,[r for r in data if r["session"]=="2236"],arm,label,color,ls,"elapsed_first_Q6_s")
    right.set_title("22:36 · 启动修正后保留的高程差",loc="left",fontweight="bold")
    right.set_xlabel("距首个 Q6（秒）");right.legend(frameon=False,fontsize=9)
    fig.savefig(D/"paired_height.png",dpi=170)

if __name__=="__main__":
    main()
