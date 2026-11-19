"""Decompose the first accepted SPP fit after replay, with constellation clock terms removed."""
import json
import sys

import numpy as np
from attribute import basis, load_rows, reference_ecef
from replay import HERE, SOURCE, LABELS, digest, read

STEP9 = HERE.parent / "brain_step9_spp_bootstrap_audit"
sys.path.insert(0, str(STEP9))
from evaluate import analyze_bootstrap, key, make_equations, parse_log

def inspect(label):
    src=SOURCE/label
    directory=HERE/(label+"_spp")
    formal=load_rows(src/"SSR/solution.csv")
    actual=load_rows(directory/"solution.csv")
    assert len(actual)==len(formal)
    assert all(all(a[k]==b[k] for k in a if k!="processing_ms") for a,b in zip(actual,formal))
    assert all(digest(src/"SSR"/p)==digest(directory/p) for p in ("observations.csv","corrections.csv"))
    q=next(r for r in actual if r["Q"]=="6")
    time=key(q["week"],q["tow"])
    calls,attempts,final,states,steps,equations,postfits=parse_log(directory/"observer.tsv")
    first=next(s for s in states if s["stage"]=="spp_return" and s["flag1"] and s["flag2"])
    commit=next(s for s in states if s["stage"]=="ppp_commit" and s["time"]==time)
    prior=next(s for s in states if s["stage"]=="ppp_trial_prior" and s["time"]==time and s["flag1"]==commit["flag1"])
    selected=final[first["call"]]
    assert selected["ok"] and np.array_equal(selected["position"],prior["xyz"])
    ref=read(src/"imported/capture.json")["reference"]
    _,_,origin,_=reference_ecef(ref)
    rotation=np.array(basis(ref))
    rows,groups,_,_,summary=analyze_bootstrap(label,calls[first["call"]],selected["attempt"],
        rotation,np.array(origin),attempts,steps,equations,postfits)
    terms=[dict(satellite=r["sat"],signal=r["signal"],elevation_deg=r["el_deg"],
        clock_removed_residual_m=r["clock_projected_v_ref_m"],up_gain=r["K_U"],
        up_contribution_m=r["K_U"]*r["clock_projected_v_ref_m"]) for r in rows if r["datum"]<0]
    height=float((rotation@(selected["position"]-origin))[2])
    assert abs(height-sum(r["up_contribution_m"] for r in terms))<1.e-7
    attempt=selected["attempt"]
    data=equations[attempt,max(steps[attempt])]
    H,variance,v,_,K=make_equations(data)
    weighted=H/np.sqrt(variance)[:,None]
    rhs=v/np.sqrt(variance)
    omission={}
    for j,row in enumerate(data):
        if row["datum"]>=0:
            continue
        mask=np.arange(len(data))!=j
        fit,_,rank,_=np.linalg.lstsq(weighted[mask],rhs[mask],rcond=None)
        if rank==H.shape[1]:
            omission[row["sat"]]=float((rotation@(fit-K@v)[:3])[2])
    start=float(formal[0]["tow"])
    early=[]
    for i,accepted in final.items():
        elapsed=calls[i]["tow"]-start
        if elapsed>12.1 or not accepted["ok"]:
            continue
        a=accepted["attempt"]; obs=equations[a,max(steps[a])]
        early.append(dict(elapsed_s=round(elapsed,3),systems=sorted({r["sat"][0] for r in obs if r["datum"]<0}),
            spp_height_error_m=float((rotation@(accepted["position"]-origin))[2])))
    return dict(spp_height_error_m=height,observations=len(terms),max_closure_m=summary["fixed_reference_max_m"],
        omission_vertical_shift_fixed_linearization_m=omission,early_spp=early,
        real_code_rows=sorted(terms,key=lambda r:-abs(r["up_contribution_m"])))
if __name__=="__main__":
    results={label:inspect(label) for label in LABELS}
    (HERE/"startup.json").write_text(json.dumps(results,indent=2)+"\n",encoding="utf8")
