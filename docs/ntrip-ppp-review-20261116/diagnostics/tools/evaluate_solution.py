"""Read-only WGS84 error CSV; optional matplotlib curves. Reference never enters PPP."""
import argparse
import csv
import json
import math
from pathlib import Path


def reference_ecef(reference):
    if reference.get('frame')!='WGS84' or not reference.get('source'):
        raise ValueError('Reference needs frame=WGS84 and its independent source description')
    lat=float(reference['lat_deg']);lon=float(reference['lon_deg']);height=float(reference['height_m'])
    if not all(math.isfinite(v) for v in (lat,lon,height)) or not -90<=lat<=90 or not -180<=lon<=180:
        raise ValueError('REFERENCE_INVALID')
    kind=reference.get('height_type')
    if kind not in ('ELLIPSOID','NORMAL'):raise ValueError('HEIGHT_TYPE_REQUIRED')
    vertical=kind=='ELLIPSOID'
    if not vertical and reference.get('height_anomaly_m') is not None:
        anomaly=float(reference['height_anomaly_m'])
        if not math.isfinite(anomaly):raise ValueError('HEIGHT_ANOMALY_INVALID')
        height+=anomaly;vertical=True
    if not vertical:height=0  # E/N projections are independent of an origin shift along its normal.
    phi=math.radians(lat);lam=math.radians(lon);e2=6.6943799901413165e-3
    N=6378137.0/math.sqrt(1-e2*math.sin(phi)**2)
    xyz=((N+height)*math.cos(phi)*math.cos(lam),(N+height)*math.cos(phi)*math.sin(lam),
         (N*(1-e2)+height)*math.sin(phi))
    return phi,lam,xyz,vertical


def enu(xyz,reference):
    phi,lam,origin,vertical=reference_ecef(reference)
    dx,dy,dz=(a-b for a,b in zip(xyz,origin))
    E=-math.sin(lam)*dx+math.cos(lam)*dy
    N=-math.sin(phi)*math.cos(lam)*dx-math.sin(phi)*math.sin(lam)*dy+math.cos(phi)*dz
    U=math.cos(phi)*math.cos(lam)*dx+math.cos(phi)*math.sin(lam)*dy+math.sin(phi)*dz
    return E,N,U if vertical else None


def evaluate(solution,reference,out,plot=False):
    _,_,_,vertical=reference_ecef(reference)
    with Path(solution).open(newline='',encoding='ascii') as f:rows=list(csv.DictReader(f))
    if not rows:raise ValueError('NO_EPOCHS')
    first=int(rows[0]['week'])*604800+float(rows[0]['tow'])
    output=[]
    for row in rows:
        t=int(row['week'])*604800+float(row['tow'])-first
        valid=row['Q']=='6'
        r=dict(elapsed_s=t,week=row['week'],tow=row['tow'],Q=row['Q'],E_m='',N_m='',U_m='',horizontal_m='',three_d_m='')
        if valid:
            xyz=tuple(float(row[k]) for k in ('x_m','y_m','z_m'))
            if not all(math.isfinite(v) for v in xyz):raise ValueError('NONFINITE_PPP_COORDINATE')
            e,n,u=enu(xyz,reference)
            r.update(E_m=e,N_m=n,horizontal_m=math.hypot(e,n))
            if u is not None:r.update(U_m=u,three_d_m=math.sqrt(e*e+n*n+u*u))
        output.append(r)
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    with (out/'errors.csv').open('x',newline='',encoding='ascii') as f:
        w=csv.DictWriter(f,fieldnames=list(output[0]));w.writeheader();w.writerows(output)
    valid=[r for r in output if r['Q']=='6']
    def stats(key):
        values=[float(r[key]) for r in valid if r[key]!='']
        return dict(N=len(values),mean=sum(values)/len(values),rms=math.sqrt(sum(v*v for v in values)/len(values)),
                    maximum_abs=max(abs(v) for v in values)) if values else None
    convergence=None;start=previous=None
    for r in output:
        if r['Q']=='6' and r['horizontal_m']<1:
            if previous is None or r['elapsed_s']-previous>1.5:start=r['elapsed_s']
            previous=r['elapsed_s']
            if r['elapsed_s']-start>=60:
                convergence=start;break
        else:start=previous=None
    summary=dict(reference=reference,reference_independence='user declaration; not inferred from this PPP solution',
                 vertical_error_available=vertical,epochs=len(output),ppp_epochs=len(valid),
                 statistics={k:stats(k) for k in ('E_m','N_m','U_m','horizontal_m','three_d_m')},
                 convergence_definition='Q6 and H<1 m continuously for >=60 s; no gap >1.5 s; evaluation only',
                 horizontal_convergence_start_s=convergence,plot_generated=False)
    if plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(3 if vertical else 2,1,figsize=(11,8),sharex=True)
        times=[r['elapsed_s'] for r in output]
        def series(key):return [float(r[key]) if r[key]!='' else math.nan for r in output]
        axes[0].plot(times,series('E_m'),label='East');axes[0].plot(times,series('N_m'),label='North');axes[0].set_ylabel('Error (m)');axes[0].legend()
        axes[1].plot(times,series('horizontal_m'),label='Horizontal');axes[1].axhline(1,color='gray',linestyle='--',label='1 m (evaluation)');axes[1].set_ylabel('Horizontal (m)');axes[1].legend()
        if vertical:axes[2].plot(times,series('U_m'),label='Up');axes[2].set_ylabel('Up (m)');axes[2].legend()
        for ax in axes:ax.grid(alpha=.3)
        axes[-1].set_xlabel('Elapsed GNSS time (s)');fig.suptitle('Recorded NTRIP + TXT causal replay; all epochs')
        fig.tight_layout();fig.savefig(out/'convergence.png',dpi=180);plt.close(fig);summary['plot_generated']=True
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--solution',type=Path,required=True)
    ap.add_argument('--reference',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--plot',action='store_true');a=ap.parse_args()
    reference=json.loads(a.reference.read_text(encoding='utf-8-sig'))
    if a.plot:
        try:import matplotlib
        except ImportError:ap.error('PNG plotting requires matplotlib; error CSV generation works without --plot')
    print(json.dumps(evaluate(a.solution,reference,a.out,a.plot),indent=2))


if __name__=='__main__':main()
