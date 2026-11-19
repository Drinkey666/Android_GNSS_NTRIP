import csv,os
from pathlib import Path
d=Path(__file__).resolve().parent
os.environ['MPLCONFIGDIR']=str(d/'plot_cache')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams.update({'font.family':['Microsoft YaHei','DejaVu Sans'],'axes.unicode_minus':False,'font.size':11})
rs=list(csv.DictReader((d/'epochs_paired.csv').open()))
fig,axs=plt.subplots(2,2,figsize=(11.5,6.1),sharex='col')
colors={'full_file':'#a76a24','live':'#303c55','ema_gap':'#078a83'}
for col,sess in enumerate(('2221','2236')):
    r=[x for x in rs if x['session']==sess]
    t=np.array([float(x['elapsed_s'])/60 for x in r]);gap=np.array([x['osb_gap_filled']=='1' for x in r])
    for i,var in enumerate(('h','u')):
        ax=axs[i,col];ax.axvspan(t[gap][0],t[gap][-1]+1/60,color='#b9d9ef',alpha=.6)
        for n,label in [('full_file','武大整套文件'),('live','手机实时'),('ema_gap','EMA 定权＋缺口备用')]:
            v=[float(row[n+'_'+var+'_m']) if row[n+'_'+var+'_m'] else np.nan for row in r]
            ax.plot(t,v,label=label,color=colors[n],lw=1.25 if n!='ema_gap' else 1.6,alpha=.93)
        ax.set_xlim(t[0],t[-1]);ax.grid(axis='y',color='#e2e6eb',lw=.7)
        ax.spines[['top','right']].set_visible(False)
        if i==1:ax.axhline(0,color='#636363',lw=.7,ls=':');ax.set_xlabel('距首个观测（分钟）')
        if col==0:ax.set_ylabel('水平误差（米）' if i==0 else '高程误差 U（米）')
        if i==0:ax.set_title('22:21 小米' if sess=='2221' else '22:36 小米',loc='left',fontweight='bold')
for i in (0,1):
    a,b=axs[i];lo=min(a.get_ylim()[0],b.get_ylim()[0]);hi=max(a.get_ylim()[1],b.get_ylim()[1]);a.set_ylim(lo,hi);b.set_ylim(lo,hi)
fig.legend(*axs[0,0].get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.50,.998),ncol=3,frameon=False)
fig.subplots_adjust(left=.08,bottom=.135,right=.985,top=.87,wspace=.14,hspace=.26)
fig.text(.082,.025,'阴影标出手机因码偏差估计停止更新而连续缺解的时段。曲线仅绘制 Q6。',color='#37414e',fontsize=10)
fig.savefig(d/'accuracy.png',dpi=170,facecolor='white')
