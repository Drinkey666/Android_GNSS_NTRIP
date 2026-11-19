import csv, json, math, statistics as st,sys,collections
from pathlib import Path
from decimal import Decimal
d=Path(__file__).resolve().parent
sys.path.insert(0,str(d.parents[1]/'tools'))
from evaluate_solution import enu
def rows(p):
 with p.open(newline='',encoding='utf-8-sig') as f:return list(csv.DictReader(f))
def key(r):return int(r['week'])*604800+Decimal(r['tow'])
def metrics(e):
 if not e:return dict(n=0)
 return dict(n=len(e),h=round(math.sqrt(st.mean(x*x+y*y for x,y,z in e)),4),u=round(math.sqrt(st.mean(z*z for x,y,z in e)),4),mean_enu=[round(st.mean(a[j] for a in e),4) for j in range(3)])
def err(r,ref):return enu([float(r[k]) for k in ('x_m','y_m','z_m')],ref)
def runs(keys):
 out=[]
 for k in keys:
  if not out or k-out[-1][-1]>Decimal('1.5'):out.append([])
  out[-1].append(k)
 return out
def arm(path,ref):
 a=rows(path)
 return {key(r):err(r,ref) for r in a if r['Q']=='6'}
