"""Project each committed measurement update and compare it with the saved formal solution."""
import collections
import csv
from decimal import Decimal
import json
import math
import statistics
import sys

from replay import HERE, SOURCE, PROBE, LABELS, digest, read

sys.path.insert(0, str(HERE.parents[1] / "tools"))
from evaluate_solution import enu, reference_ecef

CLASSES = ("other", "code", "phase", "ionex", "vmf3")

def load_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def stamp(w, t):
    return int(w)*604800 + Decimal(t)

def epoch(r):
    return stamp(r["week"], r["tow"])

def basis(ref):
    phi, lam, _, _ = reference_ecef(ref)
    s, c = math.sin(phi), math.cos(phi)
    a, b = math.sin(lam), math.cos(lam)
    return ((-a,b,0), (-s*b,-s*a,c), (c*b,c*a,s))

def delta(row, ref):
    return enu([float(row[k]) for k in ("x_m","y_m","z_m")], ref)

def components(path, keys, axes):
    kv = collections.defaultdict(lambda: collections.defaultdict(lambda:[0.,0.,0.]))
    closed, trials = {}, {}
    with path.open() as stream:
        for line in stream:
            if "$S5_ROW," in line:
                w,t,trial,group,sv,sig,slot,x,y,z,*_ = line.partition("$S5_ROW,")[2].strip().split(",")
                k = stamp(w,t)
                if k not in keys:
                    continue
                assert trials.setdefault(k,trial)==trial
                direction = kv[k][CLASSES[int(group)]]
                xyz = tuple(map(float,(x,y,z)))
                for i,axis in enumerate(axes):
                    direction[i] += sum(a*b for a,b in zip(axis,xyz))
            if "$S5_CLOSURE," in line:
                w,t,x,y,z=line.partition("$S5_CLOSURE,")[2].strip().split(",")
                k=stamp(w,t)
                if k in keys:
                    assert k not in closed
                    closed[k]=math.hypot(*map(float,(x,y,z)))
    assert keys == closed.keys() == kv.keys() and max(closed.values())<1.e-8
    return kv, max(closed.values())

def window(ks, pos, kv):
    sums = {g:[sum(kv[k][g][a] for k in ks) for a in range(3)] for g in CLASSES}
    prior = [pos[ks[0]][a]-sum(kv[ks[0]][g][a] for g in CLASSES) for a in range(3)]
    end = pos[ks[-1]]
    u = [pos[k][2] for k in ks]
    between = [end[a]-prior[a]-sum(v[a] for v in sums.values()) for a in range(3)]
    mean=statistics.mean(u); mean_square=statistics.mean(x*x for x in u)
    return dict(q6=len(ks),prior_enu_m=prior,end_enu_m=end,
        mean_enu_m=[statistics.mean(pos[k][a] for k in ks) for a in range(3)],
        horizontal_rms_m=math.sqrt(statistics.mean(sum(x*x for x in pos[k][:2]) for k in ks)),
        u_rms_m=math.sqrt(mean_square),u_mean_m=mean,u_population_sd_m=statistics.pstdev(u),
        u_mean_squared_share=mean*mean/mean_square,u_negative_epochs=sum(x<0 for x in u),
        committed_kv_enu_m=sums,between_q6_updates_enu_m=between)

def analyze(label):
    src,run=SOURCE/label, HERE/label
    receipt=read(src/"SSR/replay.json")
    for n,h in receipt["input_sha256"].items():
        assert digest(receipt["input_files"][n])==h
    assert all(digest(run/n)==digest(src/"SSR"/n) for n in ["observations.csv","corrections.csv"])
    formal=load_rows(src/"SSR/solution.csv"); replay=load_rows(run/"solution.csv")
    assert len(formal)==len(replay)
    fields=set(formal[0])-{"processing_ms"}
    assert all(all(a[i]==b[i] for i in fields) for a,b in zip(formal,replay))
    ref=read(src/"imported/capture.json")["reference"]
    pos={epoch(r):delta(r,ref) for r in replay if r["Q"]=="6"}
    kv, residual=components(run/"solution.trace",pos.keys(),basis(ref))
    keys=sorted(pos); end=epoch(formal[-1])
    windows={"first_q6":keys[:1],"first60_seconds":[k for k in keys if k<keys[0]+60],
        "after_first60":[k for k in keys if k>=keys[0]+60],
        "tail60_seconds":[k for k in keys if k>end-60],"all":keys}
    return dict(epochs=len(formal), matched_non_runtime_fields=len(fields), max_kv_closure_m=residual,
        trace_sha256=digest(run/"solution.trace"), source_checksums=len(receipt["input_sha256"]),
        windows={n:window(ks,pos,kv) for n,ks in windows.items()})

if __name__=="__main__":
    results={l:analyze(l) for l in LABELS}
    result=dict(probe_sha256=digest(PROBE),methods="Formal position field parity; projections use only the bound post-solution reference; Q6 updates only.",sessions=results)
    (HERE/"attribution.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
