"""Conditional same-epoch ablations and prefix checks against saved controls."""
import math
from statistics import fmean
from run_replays import DATASETS, SCHEMES
A1,A2="A1_outlier_gim_mad","A2_stoch_ema_r"
B1,B2,B3,B4=SCHEMES
def build_contrasts(summary):
    comparisons=[("remove_cmc",B1,A2),("pure_ema_vs_base",B1,"Baseline"),
                 ("ionq_given_a1",B2,A1),("ema_given_a1",B3,A1),("a1_given_ema",B3,B1),
                 ("ionq_given_a1_ema",B4,B3),("ema_given_a1_ionq",B4,B2)]
    by={(r["dataset"],r["scheme"]):r for r in summary}
    contrast=[]
    for d in DATASETS:
        for name,scheme,control in comparisons:
            r,b=by[d,scheme],by[d,control]
            diff={"d_"+k:v-b[k] for k,v in r.items() if k.endswith("_m") and not k.startswith("d_")}
            contrast.append(dict(dataset=d,contrast=name,scheme=scheme,control=control,**diff))
    return contrast

def ionq_effects(series,cases):
    effects=[]
    for c in cases:
        d,s=c["dataset"],c["scheme"]
        if s not in (B2,B4):
            continue
        control=A1 if s==B2 else B3
        current,old=series[d,s],series[d,control]
        assert current.keys()==old.keys()
        h,u=[],[]
        for k,p in current.items():
            e,n,up=(x-y for x,y in zip(p,old[k]))
            h.append(math.hypot(e,n))
            u.append(up)
        effects.append(dict(dataset=d,scheme=s,control=control,q6=len(u),
            clipped_satellite_epochs=c["ion_q_halved_satellites"],
            removed_ion_process_variance_m2=c["ion_q_removed_m2"],
            max_horizontal_displacement_m=max(h),max_abs_vertical_displacement_m=max(map(abs,u)),
            rms_horizontal_displacement_m=math.sqrt(fmean(x*x for x in h)),
            rms_vertical_displacement_m=math.sqrt(fmean(x*x for x in u))))
    return effects

def focus_effects(summary):
    by={(r["dataset"],r["scheme"]):r for r in summary}
    result=[]
    for d,metrics in (("1031_xiaomi_V2",("tail60_U_rms_m","tail60_U_mean_m","all_U_rms_m")),
                      ("1004_xiaomi",tuple(w+"_"+axis+"_rms_m" for w in ("first20","first60","all","tail60") for axis in "HU"))):
        for m in metrics:
            base,a2,b1=(by[d,s][m] for s in ("Baseline",A2,B1))
            retained=(b1-base)/(a2-base)
            result.append(dict(dataset=d,metric=m,baseline_m=base,A2_m=a2,B1_m=b1,
                A2_minus_baseline_m=a2-base,B1_minus_baseline_m=b1-base,B1_minus_A2_m=b1-a2,
                retained_fraction_of_A2_change=retained,removed_fraction_of_A2_change=1-retained))
    return result
def check_prefixes(series,action_rows,old_rows):
    """Up to the first active perturbation, all common committed Q6 ENU must match exactly."""
    checks=[]
    for d in DATASETS:
        for scheme,control,source,flag,arm in [
            (B1,A2,old_rows,"cmc_boost_rows",A2),
            (B2,A1,action_rows,"ion_q_halved_satellites",B2),
            (B4,B3,action_rows,"ion_q_halved_satellites",B4)]:
            hit=next(r for r in source if r["dataset"]==d and r["scheme"]==arm and int(r[flag])>0)
            first=(int(hit["week"]),float(hit["tow"]))
            a,b=series[d,scheme],series[d,control]
            assert set(a)==set(b)
            keys=[k for k in a if (int(k[0]),float(k[1]))<first]
            assert all(a[k]==b[k] for k in keys),(d,scheme,control)
            checks.append(dict(dataset=d,scheme=scheme,control=control,first_action_week=first[0],
                               first_action_tow=first[1],identical_prior_q6=len(keys)))
    return checks
