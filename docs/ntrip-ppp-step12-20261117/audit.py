"""Step 12 reads saved solutions. Candidate coordinates exist only in memory."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from frame_model import (OUT, SCENARIOS, decimal_year, ecef, from_gpst, geodetic_angles,
                         igs_comparators, models, origin_at_observation, regional_stations,
                         rotation, self_check, sha, validated_sources)

ROOT = OUT.parents[1]
STEP5 = ROOT/"validation/brain_step5_east_and_m1v2"
STEP11 = ROOT/"validation/brain_step11_presmooth_cmd_iono"
XIAOMI_1031 = ROOT/"validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json"
DATASETS = ("1120_xiaomi","1120_vivo","1004_xiaomi","1004_vivo","1031_xiaomi_V1","1031_xiaomi_V2")
SITES = {"11-14":"1120_xiaomi","10-31":"1031_xiaomi_V2"}
AXES = ("E", "N", "U")
PRIMARY = "regional_S4_CCEA"
MODERN = {"ITRF2014_obs_G2139_proxy","WGS84_G2139_obs_NGA2024","WGS84_G2296_obs_ITRF2020_proxy"}

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return list(csv.DictReader(source))

def save(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")

def table(name,items):
    fields = list(dict.fromkeys(k for r in items for k in r))
    with (OUT/name).open("w",encoding="utf-8",newline="") as stream:
        writer = csv.DictWriter(stream,fieldnames=fields,lineterminator="\n")
        writer.writeheader()
        writer.writerows(items)

def base(dataset):
    return STEP5/"runs"/dataset/"Baseline"

def resolve_inputs(dataset):
    directory = base(dataset)
    args = read(directory/"command.json")["args"]
    path_for = lambda key: Path(args[args.index(key)+1])
    session = path_for("--stream-session")
    reference = XIAOMI_1031 if dataset.startswith("1031") else session/"capture.json"
    assert args[args.index("--ssr-datum")+1]=="COM"
    return reference, session, [path_for(k) for k in ("--atx","--ionex","--vmf0","--vmf6","--orog")]

def verify(snapshot_name):
    manifest = STEP11/"input_guard_sha256.json"
    build = ROOT/"validation/build.json"
    guard = read(manifest)
    bins = read(build)["binaries"]
    assert len(guard)==245 and len(bins)==9
    mismatch = [Path(p).name for p,expected in guard.items() if sha(Path(p))!=expected]
    actual = {name:sha(ROOT/"bin"/name) for name in bins}
    assert not mismatch and actual==bins, (mismatch,[n for n in bins if bins[n]!=actual[n]])
    deps = {"step5_all_epoch_accuracy": STEP5/"all_epoch_accuracy.csv",
            "step5_matched_baseline_windows": STEP5/"matched_baseline_windows.csv"}
    for name in DATASETS:
        ref, session, products = resolve_inputs(name)
        deps.update({f"{name}_{label}":p for label,p in (
            ("command",base(name)/"command.json"),("solution",base(name)/"solution.csv"),
            ("scoring_reference",ref),("session_capture",session/"capture.json"),
            ("product_manifest",session/"products.json"),
            *zip(("atx","ionex","vmf0","vmf6","orography"),products))})
    result_digest = {k:sha(p) for k,p in deps.items()}
    snapshot = dict(step11_guard_matched=245,step11_guard_sha256=sha(manifest),
                    bin_matched=9,build_manifest_sha256=sha(build),binary_sha256=actual,
                    readonly_evidence_sha256=result_digest)
    marker = OUT/"guard_before.json"
    if snapshot_name=="before":
        # Keep the original pre-analysis footprint.
        with marker.open("x",encoding="utf-8",newline="\n") as file:
            json.dump(snapshot,file,indent=2)
            file.write("\n")
    else:
        assert read(marker)==snapshot
    print(f"{snapshot_name}: Step 11 guard 245/245, binaries 9/9, auxiliary hashes {len(deps)}/{len(deps)}")
    return snapshot

def direction(prefix,xyz,suffix="_m"):
    return {f"{prefix}{axis}{suffix}":float(v) for axis,v in zip(AXES,xyz,strict=True)}

def load_datasets(wang,ccea):
    data, provenance = {}, []
    for name in DATASETS:
        ref,session,products = resolve_inputs(name)
        value = read(ref)["reference"]
        source = value["source"]
        assert value["frame"]=="WGS84" and value["height_type"]=="ELLIPSOID"
        assert sha(products[0])=="737c46fcfd30b80a8a622f011f88bae779449e6a14781ac6e1a558934004261a"
        lat,lon,h = (np.deg2rad(float(value["lat_deg"])),np.deg2rad(float(value["lon_deg"])),float(value["height_m"]))
        pos = ecef(lat,lon,h)
        if value.get("ellipsoid_height_m") is not None:
            assert abs(h-float(value["ellipsoid_height_m"]))<1e-9
        sol = [r for r in rows(base(name)/"solution.csv") if r["Q"]=="6"]
        w,t = np.array([(int(r["week"]),float(r["tow"])) for r in sol]).T
        ts = (w*604800+t)
        assert len(sol)>=60 and np.all(np.diff(ts)>0)
        epochs = np.array([decimal_year(from_gpst(int(week),float(tow))) for week,tow in zip(w,t,strict=True)])
        keys = [(int(week),round(tow)) for week,tow in zip(w,t,strict=True)]
        assert len(set(keys))==len(keys)
        xyz = np.array([[float(r[field]) for field in ("x_m","y_m","z_m")] for r in sol])
        assert np.isfinite(xyz).all()
        speed,local = models(wang,ccea,lat,lon)
        data[name] = dict(lat=lat,lon=lon,h=h,pos=pos,R=rotation(lat,lon),xyz=xyz,
                          epochs=epochs,ts=ts,keys=keys,tail=ts>ts[-1]-60,models=speed,local=local)
        lines = ref.read_text(encoding="utf-8-sig").splitlines()
        provenance.append(dict(dataset=name,frame_tag="WGS84",source_tag=source,height_type="ELLIPSOID",
                       reference_artifact=(ref.name if name.startswith("1031") else "imported/capture.json"),
                       reference_key_line=next(i for i,line in enumerate(lines,1) if '"reference"' in line),
                       source_line=next(i for i,line in enumerate(lines,1) if f'"{source}"' in line),
                       survey_date_verified=False,
                       cors_provider_verified=False, realization_verified=False, coordinate_epoch_verified=False))
    return data,provenance

def estimate(data,scenario,model):
    pos,R = data["pos"],data["R"]
    speed_enu,sigma_enu = data["models"][model]
    speed = R.T @ speed_enu
    lat,lon,h = data["lat"],data["lon"],data["h"]
    xyz = np.array([origin_at_observation(lat,lon,h,t,scenario,speed) for t in data["epochs"]])
    eval_enu = (data["xyz"]-xyz) @ R.T
    deltas = (xyz-pos) @ R.T
    return eval_enu,deltas,sigma_enu

def stats(p):
    return {**direction("",p.mean(axis=0),"_mean_m"),
            "H_RMS_m":float(np.sqrt(np.mean(np.sum(p[:,:2]**2,axis=1)))),
            "U_RMS_m":float(np.sqrt(np.mean(p[:,2]**2))),"n":len(p)}

def compute_accuracy(data):
    output,cache = [],{}
    for name,d in data.items():
        for scenario in SCENARIOS:
            model_ids = d["models"] if scenario.epoch is not None else (PRIMARY,)
            for m in model_ids:
                errors,delta,_ = estimate(d,scenario,m)
                tail = errors[d["tail"]]
                cache[name,scenario.name,m] = stats(tail)["E_mean_m"]
                for window,values in (("first_q6",errors[:1]),("first20",errors[:20]),
                        ("first60",errors[:60]),("full",errors),("tail60",tail)):
                    output.append(dict(dataset=name,scenario=scenario.name,velocity_model=m,window=window,
                                       **stats(values)))
                assert np.max(np.abs(errors+delta-(d["xyz"]-d["pos"])@d["R"].T))<1e-12
    return output,cache

def frame_offsets(data):
    offsets, stations = [],[]
    for label,dataset in SITES.items():
        d = data[dataset]
        epoch = float(d["epochs"][0])
        for scenario in SCENARIOS:
            if scenario.name=="original":
                continue
            for model in (d["models"] if scenario.epoch is not None else (PRIMARY,)):
                vel,sigma = d["models"][model]
                origin = origin_at_observation(d["lat"],d["lon"],d["h"],epoch,scenario,d["R"].T@vel)
                shift = d["R"] @ (origin-d["pos"])
                dt = epoch-scenario.epoch if scenario.epoch is not None else 0.0
                bound = 1.96*sigma*dt*1e-3
                offsets.append(dict(site=label,scenario=scenario.name,velocity_model=model,observation_epoch=epoch,
                                    **direction("delta_",shift),**direction("vel95_low_",shift-bound),
                                    **direction("vel95_high_",shift+bound),**direction("vel95_halfwidth_",bound),
                                    **direction("velocity_",vel if dt else np.zeros(3),"_mm_y")))
        for source,neighbors,weights in d["local"]:
            for (distance,s),weight in zip(neighbors,weights,strict=True):
                stations.append(dict(site=label,source=source,station=s.code,distance_km=distance,
                                     interpolation_weight=float(weight),
                                     **direction("velocity_",s.enu,"_mm_y"),**direction("sigma_",s.sigma,"_mm_y")))
    return offsets,stations

def cross_sites(data):
    rot = data["1120_xiaomi"]["R"]
    mean = lambda d: d["xyz"][d["tail"]].mean(axis=0)
    n14 = DATASETS[:4]
    site14_solution = np.mean([mean(data[k]) for k in n14],axis=0)
    site14_ref = np.mean([data[k]["pos"] for k in n14],axis=0)
    output = []
    for key in DATASETS[4:]:
        d = data[key]
        def compare(name, pos, ref):
            p = rot @ (pos-mean(d))
            r = rot @ (ref-d["pos"])
            return dict(nov14=name,oct31=key,**direction("PPP_",p),**direction("reference_",r),
                        **direction("PPP_minus_reference_",p-r),PPP_H_m=float(np.linalg.norm(p[:2])),
                        reference_H_m=float(np.linalg.norm(r[:2])),
                        difference_H_m=float(np.linalg.norm((p-r)[:2])))
        output.append(compare("mean_4_sessions",site14_solution,site14_ref))
        output.extend(compare(k,mean(data[k]),data[k]["pos"]) for k in n14)
    return output

def dual_phone(data):
    output=[]
    for hour in ("1120","1004"):
        x,v = (data[hour+"_"+name] for name in ("xiaomi","vivo"))
        xm,vm = ({t:i for i,t in enumerate(d["keys"])} for d in (x,v))
        shared = sorted(xm.keys()&vm.keys())
        assert shared
        ix,iv = ([m[t] for t in shared] for m in (xm,vm))
        skew = np.abs(x["ts"][ix]-v["ts"][iv])
        assert max(skew)<.01
        px,pv = x["xyz"][ix],v["xyz"][iv]
        # Basis at solution midpoint. No configured reference is used for the inter-phone vector.
        local = rotation(*geodetic_angles(((px+pv)/2).mean(axis=0)))
        rel = (px-pv) @ local.T
        ref_delta = local @ (x["pos"]-v["pos"])
        xe = (px-x["pos"]) @ local.T
        ve = (pv-v["pos"]) @ local.T
        for label, mask in (("common_q6",np.ones(len(ix),dtype=bool)),("common_q6_tail60",
                   (x["ts"][ix]>x["ts"][ix][-1]-60) & (v["ts"][iv]>v["ts"][iv][-1]-60))):
            p = rel[mask]
            s,e1,e2 = p.mean(axis=0),xe[mask].mean(axis=0),ve[mask].mean(axis=0)
            assert np.max(np.abs((e1-e2)-(s-ref_delta)))<1e-7
            output.append(dict(session=hour,window=label,n=len(p),max_time_skew_s=float(max(skew[mask])),
                **direction("xiaomi_minus_vivo_",s),H_of_mean_m=float(np.linalg.norm(s[:2])),
                paired_H_RMS_m=float(np.sqrt(np.mean(np.sum(p[:,:2]**2,axis=1)))),
                **direction("reference_pair_delta_",ref_delta),reference_pair_H_m=float(np.linalg.norm(ref_delta[:2])),
                **direction("xiaomi_original_mean_",e1),**direction("vivo_original_mean_",e2),
                **direction("pair_common_original_mean_",.5*(e1+e2))))
    return output

def policy_pair(data):
    v1,v2 = [data[k] for k in DATASETS[-2:]]
    maps = [{t:i for i,t in enumerate(d["keys"]) if d["tail"][i]} for d in (v1,v2)]
    common = sorted(maps[0].keys() & maps[1].keys())
    i,j = ([m[t] for t in common] for m in maps)
    assert len(i)==60 and np.array_equal(v1["pos"],v2["pos"])
    p1,p2 = v1["xyz"][i],v2["xyz"][j]
    R = rotation(*geodetic_angles(((p1+p2)/2).mean(axis=0)))
    shift = ((p2-p1) @ R.T).mean(axis=0)
    return dict(common_tail_epochs=len(common), **direction("V2_minus_V1_",shift),
                H_of_mean_m=float(np.linalg.norm(shift[:2])))

def ablations():
    metrics=rows(STEP5/"all_epoch_accuracy.csv")
    saved_tail={(r["dataset"],r["scheme"]):r for r in rows(STEP5/"matched_baseline_windows.csv")
                if r["scope"]=="baseline_tail60"}
    out=[]
    for d in DATASETS:
        for scheme in ("Baseline","NoGPSCode","NoGALCode","NoBDSCode"):
            r=next((item for item in metrics if item["dataset"]==d and item["scheme"]==scheme),None)
            m=saved_tail.get((d,scheme))
            out.append(dict(dataset=d,scheme=scheme,available=r is not None,
                tail_count=int(r["tail60_n"]) if r else None,E_tail_m=float(r["tail60_E_mean_m"]) if r else None,
                E_matched_baseline_m=float(m["base_E_mean_m"]) if m else None,
                E_matched_ablation_m=float(m["candidate_E_mean_m"]) if m else None,
                matched_n=int(m["candidate_n"]) if m else None))
    return out

def aggregates(cache):
    output=[]
    for scenario in SCENARIOS:
        alternatives = {k[2] for k in cache if k[1]==scenario.name}
        for m in sorted(alternatives):
            scores = {name:cache[name,scenario.name,m] for name in DATASETS}
            subset = lambda *names: float(np.mean([scores[d] for d in names]))
            site14,site1031 = subset(*DATASETS[:4]),subset(*DATASETS[4:])
            vivo = subset("1120_vivo","1004_vivo")
            xiaomi = subset("1120_xiaomi","1004_xiaomi","1031_xiaomi_V2")
            mixed = min(scores.values())<0<max(scores.values())
            output.append(dict(candidate=scenario.name,velocity_model=m,E_min_m=min(scores.values()),
               E_max_m=max(scores.values()),positive_runs=sum(e>0 for e in scores.values()),
               mixed_run_sign=mixed,E_equal6_m=subset(*DATASETS),E_1114_m=site14,E_1031_policy_mean_m=site1031,
               E_1031_V2_m=scores["1031_xiaomi_V2"],E_1031_V1_m=scores["1031_xiaomi_V1"],
               E_two_sites_policy_mean_m=(site14+site1031)/2,
               E_two_independent_site_days_V2_m=(site14+scores["1031_xiaomi_V2"])/2,
               E_1120_m=subset(*DATASETS[:2]),E_1004_m=subset(*DATASETS[2:4]),E_vivo_m=vivo,E_xiaomi_V2_m=xiaomi,
               common_positive_site_sign=bool(min(site14,site1031)>0),
               common_positive_phone_sign=bool(min(vivo,xiaomi)>0),
               same_site_sign=bool(site14*site1031>0),same_phone_sign=bool(vivo*xiaomi>0)))
    return output

def classify(items):
    baseline, = (r for r in items if r["candidate"]=="original")
    comparison=[r for r in items if r["candidate"]!="original"]
    target="E_two_independent_site_days_V2_m"
    fitted=[r for r in comparison if r["velocity_model"]==PRIMARY]
    best=min(fitted,key=lambda r:abs(r[target]))
    cleared=[r for r in comparison if abs(r["E_equal6_m"])<.3 and abs(r[target])<.3
             and not r["same_site_sign"] and not r["same_phone_sign"] and r["mixed_run_sign"]]
    modern=[r for r in comparison if r["candidate"] in MODERN]
    if any(r in cleared for r in modern):
        result="NOT_FRAME"
    elif cleared:
        result="FRAME_EXPLAINED"
    elif abs(best[target])<abs(baseline[target]):
        result="PARTIAL"
    else:
        result="NOT_FRAME"
    return dict(result=result,nominal_best=best,baseline=baseline,cleared=cleared)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("before","evaluate"))
    args=parser.parse_args()
    if args.action=="before":
        verify("before")
        return
    assert (OUT/"guard_before.json").is_file()
    sources=validated_sources(OUT)
    self_check()
    data,provenance=load_datasets(*regional_stations(OUT))
    values,cache=compute_accuracy(data)
    offsets,neighbors=frame_offsets(data)
    cross=cross_sites(data)
    dual=dual_phone(data)
    masked=ablations()
    aggregate=aggregates(cache)
    decision=classify(aggregate)
    pairing=policy_pair(data)
    igs=igs_comparators(OUT,(data["1120_xiaomi"]["lat"],data["1120_xiaomi"]["lon"]))
    stock=[r for r in rows(STEP5/"all_epoch_accuracy.csv") if r["scheme"]=="Baseline"]
    historical_dx=0.0
    for x in stock:
        d=x["dataset"]
        for window,alias in (("full","all"),("tail60","tail60")):
            row, = (r for r in values if r["dataset"]==d and r["scenario"]=="original" and r["window"]==window)
            assert int(x[f"{alias}_n"])==row["n"]
            for k in ("E_mean_m","N_mean_m","U_mean_m","H_RMS_m","U_RMS_m"):
                historical_dx=max(historical_dx,abs(float(x[f"{alias}_{k}"])-row[k]))
    assert historical_dx<1e-7
    items={"frame_offsets.csv":offsets,"reeval_accuracy.csv":values,"cross_site_consistency.csv":cross,
           "dual_phone_consistency.csv":dual,"step5_code_ablation.csv":masked,"common_east_by_candidate.csv":aggregate,
           "local_velocity_support.csv":neighbors,"igs_velocity_crosscheck.csv":igs,"reference_metadata.csv":provenance}
    for f,r in items.items():
        table(f,r)
    verified=verify("after")
    missing=[r["dataset"]+" "+r["scheme"] for r in masked if not r["available"]]
    chosen = decision["nominal_best"]
    one,two = [r for r in offsets if r["scenario"]==chosen["candidate"] and r["velocity_model"]==PRIMARY]
    # Use the full site-level velocity range as a common systematic uncertainty.
    mean_bound = (one["vel95_halfwidth_E_m"] + two["vel95_halfwidth_E_m"])/2
    central = chosen["E_two_independent_site_days_V2_m"]
    decision["equal_site_V2_residual_velocity_only_interval_m"] = [central-mean_bound,central+mean_bound]
    save(OUT/"verification.json",dict(guard_before=read(OUT/"guard_before.json"),guard_after=verified,
        sources_sha256=sources,read_only_solution_rows=sum(len(r["xyz"]) for r in data.values()),
        replay_executed=0,formal_build_executed=0,reference_feedback=False,reference_changed=False,
        preexisting_step5_max_error_replication_m=historical_dx,number_of_solutions=len(data),
        observations=decision,policy_pair=pairing,missing_step5_ablations=missing,csv_rows={f:len(v) for f,v in items.items()},
        output_sha256={f:sha(OUT/f) for f in items}))
    print(decision["result"],"best:",decision["nominal_best"]["candidate"],
          f"remaining site-day mean {decision['nominal_best']['E_two_independent_site_days_V2_m']:+.3f} m")

if __name__=="__main__":
    main()
