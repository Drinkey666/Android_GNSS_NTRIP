"""Evaluate actual SPP equations and PPP bootstrap states after the replay has finished."""
from collections import Counter, defaultdict
import csv
import math
from pathlib import Path
import re
import sys

import numpy as np

from run_replays import DATASETS, OUT, ROOT, STEP6, args_for, guard, read, rows, save, sha

sys.path.insert(0, str(ROOT / "tools"))
from evaluate_solution import reference_ecef

STATE_LABELS = ("X", "Y", "Z", "GPS_clock", "GLO_ISB", "GAL_ISB", "BDS_ISB", "IRN_ISB", "QZS_ISB")
LOCAL_LABELS = ("E", "N", "U", *STATE_LABELS[3:])
SYSTEMS = {"G": "GPS", "E": "GAL", "C": "BDS", "R": "GLO", "J": "QZS", "I": "IRN", "S": "SBAS"}
ROW_VALUES = ("el_deg", "az_deg", "SNR_dBHz", "P_raw_m", "P_corrected_m", "geometric_range_m",
              "minus_c_sat_clock_m", "broadcast_iono_m", "saastamoinen_trop_m", "vare_m2",
              "vmeas_m2", "vion_m2", "vtrp_m2", "varerr_m2", "variance_m2", "prefit_m")
STEP5 = OUT.parent / "brain_step5_east_and_m1v2"

def table(path, data):
    fields = list(dict.fromkeys(k for row in data for k in row))
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)

def key(week, second):
    return int(week), round(float(second))

def triplet(vector):
    return "/".join(f"{float(x):+.3f}" for x in vector[:3])

def vector_columns(prefix, array, labels, suffix=""):
    return {f"{prefix}_{label}{suffix}": float(value) for label, value in zip(labels, array)}

def reference(dataset):
    if dataset.startswith("1031"):
        path = ROOT / "validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json"
    else:
        args = args_for(dataset)
        path = Path(args[args.index("--stream-session") + 1]) / "capture.json"
    phi, lam, origin, vertical = reference_ecef(read(path)["reference"])
    assert vertical, dataset
    s, c, sl, cl = math.sin(phi), math.cos(phi), math.sin(lam), math.cos(lam)
    rotation = np.array([[-sl, cl, 0], [-s*cl, -s*sl, c], [c*cl, c*sl, s]])
    return np.array(origin), rotation

def parse_log(path):
    calls, attempts, final, states = {}, {}, {}, []
    steps, equations, postfits = defaultdict(dict), defaultdict(list), defaultdict(dict)
    with path.open(encoding="ascii", newline="") as stream:
        for kind, *p in csv.reader(stream, delimiter="\t"):
            if kind == "CALL":
                call, week, tow, startup, ephopt, nx = p
                calls[int(call)] = dict(time=key(week, tow), tow=float(tow),
                                       startup=int(startup), ephopt=int(ephopt), nx=int(nx))
            elif kind == "TRY":
                call, attempt, parent, role, omitted = p
                attempts[int(attempt)] = dict(call=int(call), attempt=int(attempt), parent=int(parent),
                                              role=role, omitted_sat_number=int(omitted))
            elif kind == "RESULT":
                _, attempt, status, iteration, wrote = p
                attempts[int(attempt)].update(status=status, last_iteration=int(iteration), wrote=bool(int(wrote)))
            elif kind == "SELECT":
                _, attempt, role, round_index, sat = p
                attempts[int(attempt)].update(selected_role=role, selected_round=int(round_index),
                                              selected_omission=int(sat))
            elif kind == "END":
                call, attempt, ok, q, *state = p
                final[int(call)] = dict(attempt=int(attempt), ok=bool(int(ok)), q=int(q),
                                        position=np.array(state[:3], dtype=float),
                                        clocks=np.array(state[3:], dtype=float) * 299792458.0)
            elif kind == "STATE":
                w, t, stage, call, f1, f2, q, fail, spp_valid, ppp_valid, spp_clk, sol_clk, clk, *xyz = p
                states.append(dict(time=key(w,t), tow=float(t), stage=stage, call=int(call),
                                   flag1=int(f1), flag2=int(f2), sol_q=int(q), ppp_failure=int(fail),
                                   spp_clock_valid=int(spp_valid), ppp_clock_valid=int(ppp_valid),
                                   spp_clock_m=float(spp_clk), sol_clock_m=float(sol_clk), observed_clock_m=float(clk),
                                   xyz=np.array(xyz[:3], dtype=float), sol_xyz=np.array(xyz[3:], dtype=float)))
            elif kind == "ROW":
                _, at, it, r, oi, sat, sysnum, sig, datum, *data = p
                meta = dict(zip(ROW_VALUES, map(float, data[:len(ROW_VALUES)]), strict=True))
                equations[int(at),int(it)].append(
                    dict(row=int(r), obs_index=int(oi), sat=sat, system_number=int(sysnum),
                         signal=sig, datum=int(datum), H=np.array(data[len(ROW_VALUES):], dtype=float), **meta))
            elif kind == "STEP":
                call, at, it, nv, *vectors = p
                n = calls[int(call)]["nx"]
                steps[int(at)][int(it)] = tuple(map(lambda a: np.array(a, dtype=float),
                                                   (vectors[:n], vectors[n:2*n], vectors[2*n:]))) + (int(nv),)
            elif kind == "POST":
                _, at, oi, datum, v = p
                postfits[int(at)][int(oi),int(datum)] = float(v)
            elif kind not in ("METRICS", "TRIAL_METRICS"):
                raise ValueError(f"Unrecognized audit record: {kind}")
    assert len(final) == len(calls) and all("status" in x for x in attempts.values())
    return calls, attempts, final, states, steps, equations, postfits

def make_equations(data):
    H = np.stack([x["H"] for x in data])
    variance = np.array([x["variance_m2"] for x in data])
    prefit = np.array([x["prefit_m"] for x in data])
    assert np.all(variance > 0.0)
    B = H / np.sqrt(variance)[:,None]
    normal = B.T @ B
    K = np.linalg.solve(normal, (H / variance[:,None]).T)
    return H, variance, prefit, normal, K

def group_for(row):
    if row["datum"] >= 0:
        return f"constraint:{STATE_LABELS[row['datum']]}"
    return f"{SYSTEMS[row['sat'][0]]} {row['signal']}"

def local_vector(rotation, vector):
    return np.r_[rotation @ vector[:3], vector[3:]]

def summed(matrix):
    return np.array([math.fsum(column) for column in matrix.T])

def maxabs(vector):
    return float(np.max(np.abs(vector)))

def selected_lineage(chosen, attempts):
    lineage = []
    while chosen:
        attempt = attempts[chosen]
        if attempt["wrote"]:
            lineage.append(chosen)
        chosen = attempt["parent"]
    return list(reversed(lineage))

def from_initial(attempt, at_meta, steps, equations, reference_xyz, rotation):
    lineage = selected_lineage(attempt, at_meta)
    nx = len(steps[attempt][0][0])
    last = np.r_[reference_xyz, np.zeros(nx - 3)]
    contributions = defaultdict(list)
    numerical = []
    checks = []
    for at in lineage:
        for it, (before, dx, after, nv) in sorted(steps[at].items()):
            if it == 0:
                name = "initial_seed_minus_reference" if not checks else "FDE_trial_reseed"
                contributions[name].append(before - last)
            else:
                assert np.array_equal(last, before)
            data = equations[at,it]
            assert len(data) == nv
            _, _, v, _, gain = make_equations(data)
            per_row = gain.T * v[:,None]
            independent_dx = summed(per_row)
            solver_error = dx - independent_dx
            arithmetic_roundoff = (after - before) - dx
            numerical.extend((solver_error, arithmetic_roundoff))
            for row, vector in zip(data, per_row, strict=True):
                contributions[group_for(row)].append(vector)
            checks.append(dict(attempt=at, iteration=it, rows=nv, max_dx_difference_m=maxabs(solver_error),
                               max_float_update_roundoff_m=maxabs(arithmetic_roundoff)))
            last = after
    initial_offset = np.r_[reference_xyz, np.zeros(nx - 3)]
    sums = {g: summed(np.stack(v)) for g, v in contributions.items()}
    # This separately reports the numerical scale lost summing Earth-centre iterations.
    centre_closure = summed(np.stack([*sums.values(), *numerical])) - (last - initial_offset)
    assert maxabs(centre_closure) < 1e-6, (attempt, centre_closure)
    groups = {g: local_vector(rotation, v) for g, v in sums.items()}
    groups["finite_precision_solver_and_state_addition"] = local_vector(rotation, summed(np.stack(numerical)))
    return groups, checks, maxabs(centre_closure)

def analyze_bootstrap(dataset, call, attempt, rotation, origin, attempts, steps, equations, postfits):
    iteration = max(steps[attempt])
    before, dx, after, nv = steps[attempt][iteration]
    data = equations[attempt,iteration]
    H, variance, v, normal, K = make_equations(data)
    assert nv == len(data)
    assert all(row["row"] == j for j, row in enumerate(data))
    assert maxabs(np.sum(np.stack([[row[k] for k in ROW_VALUES[9:14]] for row in data]), axis=1)
                  - np.where([row["datum"] >= 0 for row in data], 0.0, variance)) < 1e-10
    D = H[:,3:]
    G = H[:,:3]
    weights = 1.0 / variance
    # The final fitted clocks define the clock datum at the reference position.
    # Transport the observed prefit equations linearly without changing weights, masks or the solution.
    anchor = np.r_[origin, after[3:]]
    v_ref = v + H @ (before - anchor)
    clock_components = np.linalg.solve(D.T @ (D * weights[:,None]), D.T @ (v_ref * weights))
    v_shape = v_ref - D @ clock_components
    projected_G = G - D @ np.linalg.solve(D.T @ (D * weights[:,None]), D.T @ (G * weights[:,None]))
    schur_answer = np.linalg.solve(projected_G.T @ (G * weights[:,None]), projected_G.T @ (v_shape * weights))
    closure_schur = maxabs(schur_answer - (K @ v_ref)[:3])
    rounding = (after - before) - dx
    transported = K.T * v_ref[:,None]
    shape = K.T * v_shape[:,None]
    fixed_error = maxabs(summed(transported) + rounding - (after - anchor))
    direct_error = maxabs(summed(K.T * v[:,None]) - dx)
    ident_error = maxabs(K @ H - np.eye(H.shape[1]))
    assert max(fixed_error, direct_error) < 1e-9, (dataset, fixed_error, direct_error)
    assert max(closure_schur, ident_error) < 1e-9, dataset
    for row in data:
        datum = row["datum"]
        if datum >= 0:
            assert row["prefit_m"] == 0.0 and row["variance_m2"] == 0.01
            assert np.array_equal(row["H"], np.eye(H.shape[1])[datum])
        else:
            model = (row["geometric_range_m"] + before[3] + row["minus_c_sat_clock_m"]
                     + row["broadcast_iono_m"] + row["saastamoinen_trop_m"])
            isb = row["H"][4:] @ before[4:]
            assert abs((row["P_corrected_m"] - model - isb) - row["prefit_m"]) < 1e-9
    labels = [group_for(row) for row in data]

    cov = np.linalg.inv(normal)
    local_axes = np.eye(H.shape[1])
    local_axes[:3,:3] = rotation
    local_cov = local_axes @ cov @ local_axes.T
    sigma = np.sqrt(np.diag(local_cov))
    correlation = local_cov / sigma[:,None] / sigma[None,:]
    coupled = []
    for dimension, row in enumerate(correlation):
        for j, value in enumerate(row):
            if j >= 3 and dimension <= j:
                coupled.append(dict(dataset=dataset, kind="covariance_correlation", from_state=LOCAL_LABELS[dimension],
                                    to_state=LOCAL_LABELS[j], value=float(value), unit="1"))
    for system in ("GPS","GAL","BDS","GLO","IRN","QZS"):
        indicator = np.array([float(label.startswith(system+" ")) for label in labels])
        if not np.any(indicator):
            continue
        offset_steps = K @ indicator
        residual_norm = maxabs(indicator - H @ offset_steps)
        assert max(maxabs(offset_steps[:3]), residual_norm) < 1e-9
        for dim, value in enumerate(local_vector(rotation, offset_steps)):
            coupled.append(dict(dataset=dataset, kind="constant_plus_1m", from_state=system,
                                to_state=LOCAL_LABELS[dim], value=float(value), unit="m"))
        coupled.append(dict(dataset=dataset, kind="constant_plus_1m", from_state=system,
                            to_state="max_remaining_row_residual", value=residual_norm, unit="m"))

    accepted, groups = [], []
    for j, row in enumerate(data):
        row_info = {k: val for k, val in row.items() if k != "H"}
        row_info.update(dataset=dataset, week=call["time"][0], tow=call["tow"], attempt=attempt,
                        iteration=iteration, group=labels[j], sateph=call["ephopt"],
                        weight_m_minus2=weights[j], postfit_linear_m=float(v[j] - H[j] @ dx),
                        postfit_nonlinear_m=postfits[attempt].get((row["obs_index"],row["datum"])),
                        v_at_linearized_reference_m=float(v_ref[j]), clock_projected_v_ref_m=float(v_shape[j]),
                        leverage=float(H[j] @ K[:,j]))
        for prefix, array, name in (("H", H[j], STATE_LABELS), ("H", local_vector(rotation,H[j])[:3], LOCAL_LABELS),
                                    ("K", K[:,j], STATE_LABELS), ("K", local_vector(rotation,K[:,j])[:3], LOCAL_LABELS),
                                    ("Kv_step", local_vector(rotation, K[:,j]*v[j]), LOCAL_LABELS),
                                    ("Kv_ref", local_vector(rotation, transported[j]), LOCAL_LABELS),
                                    ("Kv_shape", local_vector(rotation, shape[j]), LOCAL_LABELS)):
            row_info.update(vector_columns(prefix, array, name))
        accepted.append(row_info)
    for g in dict.fromkeys(labels):
        mask = np.array([label == g for label in labels])
        groups.append(dict(dataset=dataset, method="fixed_reference", group=g, rows=int(mask.sum()),
                           fixed_closure_max_m=fixed_error,
                           **vector_columns("Kv",local_vector(rotation,summed(transported[mask])),LOCAL_LABELS,"_m"),
                           **vector_columns("shape",local_vector(rotation,summed(shape[mask])),LOCAL_LABELS,"_m"),
                           mean_prefit_m=float(np.mean(v[mask])),
                           wmean_v_ref_m=float(np.average(v_ref[mask],weights=weights[mask]))))
    for group, inc in (("state_update_roundoff",rounding),("TOTAL",after-anchor)):
        groups.append(dict(dataset=dataset, method="fixed_reference", group=group, rows=nv if group=="TOTAL" else 0,
                           fixed_closure_max_m=fixed_error,
                           **vector_columns("Kv",local_vector(rotation,inc),LOCAL_LABELS,"_m")))
    iter_groups, checks, iter_close = from_initial(attempt, attempts, steps, equations, origin, rotation)
    for g, vec in iter_groups.items():
        groups.append(dict(dataset=dataset, method="from_initial", group=g,
                           iteration_closure_max_m=iter_close, **vector_columns("Kv",vec,LOCAL_LABELS,"_m")))
    groups.append(dict(dataset=dataset, method="from_initial", group="TOTAL",
                       iteration_closure_max_m=iter_close,
                       **vector_columns("Kv",local_vector(rotation,after-np.r_[origin,np.zeros(len(after)-3)]),
                                        LOCAL_LABELS,"_m")))
    assert all(row["postfit_nonlinear_m"] is not None for row in accepted), dataset
    return (accepted, groups, coupled, [dict(dataset=dataset, **x) for x in checks],
            dict(iterations=iteration+1, nx=len(after), equations=nv, raw_rows=sum(r["datum"]<0 for r in data),
                 constraint_rows=sum(r["datum"]>=0 for r in data), selected_attempt=attempt,
                 normal_condition=float(np.linalg.cond(normal)), fixed_reference_max_m=fixed_error,
                 final_lsq_max_m=direct_error, clock_schur_max_m=closure_schur, gain_identity_max=ident_error,
                 iteration_sum_max_m=iter_close, max_group_shape_difference_E_m=max(
                     abs(row["Kv_E_m"]-row["shape_E_m"]) for row in groups if "shape_E_m" in row),
                 **vector_columns("spp_fit",after[3:],STATE_LABELS[3:],"_m"),
                 **vector_columns("clock_projection",clock_components,STATE_LABELS[3:],"_m")))

def audit_case(dataset, verification, step6_row, step5_row):
    folder = OUT / "runs" / dataset
    actual = rows(folder / "solution.csv")
    q6 = next(key(r["week"],r["tow"]) for r in actual if r["Q"]=="6")
    origin, rotation = reference(dataset)
    calls, attempts, end, states, steps, equations, postfits = parse_log(folder / "observer.tsv")
    head = [s for s in states if s["time"] <= q6]
    committed = [s for s in head if s["stage"]=="ppp_commit"]
    assert all(c["ephopt"] == 4 for c in calls.values()), dataset
    config = (folder / "console.log").read_text(encoding="utf-8",errors="replace")
    assert re.search(r"^PPP_CONFIG,.*sateph=4 iono=4 .* ar=0 .*repairs=B_VERIFIED",config,re.M), dataset
    assert committed and committed[-1]["time"]==q6, dataset
    commit = committed[-1]
    prior = next(s for s in head if s["stage"]=="ppp_trial_prior" and s["time"]==q6 and s["flag1"]==commit["flag1"])
    bootstraps = [s for s in head if s["stage"]=="spp_return" and s["flag1"] and s["flag2"]]
    assert bootstraps
    bootstrap = bootstraps[0]
    selected = end[bootstrap["call"]]
    assert selected["ok"] and np.array_equal(selected["position"],bootstrap["xyz"])
    assert np.array_equal(bootstrap["xyz"],bootstrap["sol_xyz"])
    boot_xyz = selected["position"]
    chosen_steps = steps[selected["attempt"]]
    final_step_xyz = chosen_steps[max(chosen_steps)][2][:3]
    assert np.array_equal(final_step_xyz, boot_xyz), dataset
    s_enu, p_enu = rotation @ (boot_xyz-origin), rotation @ (prior["xyz"]-origin)
    delta = rotation @ (prior["xyz"]-boot_xyz)
    prior_screen = [int(r["Q"]) for r in actual if key(r["week"],r["tow"]) < q6]
    difference_step5 = None
    if step5_row:
        recorded = np.array([float(step5_row[f"{axis}_first_q6_before_measurement_m"]) for axis in "ENU"])
        difference_step5 = maxabs(p_enu - recorded)
        assert difference_step5 < 1e-7, (dataset, difference_step5)
    if step6_row:
        assert q6 == key(step6_row["week"],step6_row["first_q6_second"])
        assert abs(float(step6_row["E_before_first_Q6_m"]) - p_enu[0]) < 1e-7
        assert int(step6_row["prior_exported_Q5"]) == prior_screen.count(5)
        assert int(step6_row["committed_PPP_trials_before_Q6"]) == len(committed)-1
        assert int(step6_row["bootstrap_spp_success_lines"]) == len(bootstraps)

    chain = []
    events = defaultdict(list)
    for event in head:
        events[event["time"]].append(event)
    for item in actual:
        time = key(item["week"], item["tow"])
        if time > q6:
            break
        ev = events.pop(time, [])
        common = dict(dataset=dataset, week=time[0], second=time[1], exported_Q=int(item["Q"]))
        if not ev:
            chain.append(dict(**common, stage="no_rtkpos_processed"))
        for s in ev:
            stage = {k:v for k,v in s.items() if k not in ("time","xyz","sol_xyz")}
            chain.append(dict(**common, **stage,
                              **(vector_columns("position_ref",rotation@(s["xyz"]-origin),"ENU","_m")
                                 if np.any(s["xyz"]) else {}),
                              **(vector_columns("position_from_bootstrap",rotation@(s["xyz"]-boot_xyz),"ENU","_m")
                                 if np.any(s["xyz"]) else {}),
                              **(vector_columns("trusted_sol_ref",rotation@(s["sol_xyz"]-origin),"ENU","_m")
                                 if np.any(s["sol_xyz"]) else {})))
    assert not events, (dataset,list(events)[:5])
    accepted, groups, coupling, checks, stats = analyze_bootstrap(dataset, calls[bootstrap["call"]],
                                      selected["attempt"], rotation, origin, attempts, steps, equations, postfits)
    calls_counts = Counter(at["status"] for at in attempts.values())
    attempts_table = []
    for at in attempts.values():
        c = calls[at["call"]]
        e = end[at["call"]]
        attempts_table.append(dict(dataset=dataset, week=c["time"][0], second=c["time"][1], tow=c["tow"],
                                   startup=c["startup"], **at, final_chosen=e["attempt"]==at["attempt"] and e["ok"],
                                   bootstrap_evidence=at["call"]==bootstrap["call"] and at["attempt"]==selected["attempt"],
                                   call_accepted=e["ok"]))
    args = args_for(dataset)
    stats.update(**verification, ssr_profile=args[args.index("--ssr-profile")+1],
                 position_propagated_bitwise=np.array_equal(prior["xyz"],boot_xyz),
                 boot_week=bootstrap["time"][0], boot_tow=bootstrap["tow"],
                 spp_enu_m=list(s_enu), q6_prior_enu_m=list(p_enu), spp_to_q6_prior_enu_m=list(delta),
                 weak_or_no_fix_before_q6=prior_screen.count(0), prior_exported_q5=prior_screen.count(5),
                 committed_ppp_before_q6=len(committed)-1, bootstrap_overwrites=len(bootstraps)-1,
                 spp_failure_calls_before_or_at_first_q6=sum(
                     s["stage"]=="spp_return" and not s["flag1"] for s in head),
                 spp_fallbacks_before_first_q6=sum(s["stage"]=="spp_fallback" for s in head),
                 pre_q6_trial_count=sum(s["stage"]=="ppp_trial_prior" for s in head),
                 accepted_q6_trial_index=commit["flag1"],
                 step6_crosscheck=bool(step6_row), step5_prior_difference_max_m=difference_step5,
                 total_spp_calls=len(calls), total_spp_attempts=len(attempts),
                 startup_fde_trials=sum(a["role"]=="startup_fde" for a in attempts.values()),
                 raim_fde_trials=sum(a["role"]=="raim_fde" for a in attempts.values()),
                 spp_attempt_results=dict(calls_counts), spp_clock_m=bootstrap["spp_clock_m"],
                 ppp_trial_clock_m=prior["observed_clock_m"],
                 udclk_clock_m=next(s["observed_clock_m"] for s in head if s["stage"]=="udclk_out"
                                    and s["time"]==q6), spp_reference_evaluation_only=True)
    return stats, chain, accepted, groups, coupling, checks, attempts_table

def terminal(cases, groups, coupling):
    text = ["# Step 9 终端汇总", "",
            "## 无损回放与首解前状态链", "",
            "| 数据包 | 首个 Q6 GPST 周/秒 | 总期/Q6 | 启动 SPP E/N/U m | Q6 验前 E/N/U m | SPP→验前 ENU 位移 m | 前置 Q0/Q5/PPP 提交/回退 | LS 闭合 m |",
            "|---|---|---:|---:|---:|---:|---:|---:|"]
    for d, s in cases.items():
        text.append(f"| {d} | {s['first_q6_week']}/{s['first_q6_tow']:.3f} | {s['epochs']}/{s['q6']} | "
                    f"{triplet(s['spp_enu_m'])} | {triplet(s['q6_prior_enu_m'])} | "
                    f"{triplet(s['spp_to_q6_prior_enu_m'])} | {s['weak_or_no_fix_before_q6']}/"
                    f"{s['prior_exported_q5']}/{s['committed_ppp_before_q6']}/{s['spp_fallbacks_before_first_q6']} | "
                    f"{s['fixed_reference_max_m']:.2e} |")
    text += ["", "## 最终接纳 SPP 的固定线性化位置贡献", "",
             "各列为 E/N/U，单位米。约束和未出现信号码的贡献为零。", "",
             "| 数据包 | GPS 1C | GAL 1C | BDS 2I | GLO 1C | 虚拟秩亏约束 | 合计 |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for d in cases:
        this = {r["group"]:r for r in groups if r["dataset"]==d and r["method"]=="fixed_reference"}
        result = lambda names: [math.fsum(this[g][f"Kv_{axis}_m"] for g in names if g in this) for axis in "ENU"]
        cols = [triplet(result([g])) for g in ("GPS 1C","GAL 1C","BDS 2I","GLO 1C")]
        cols += [triplet(result([g for g in this if g.startswith("constraint:")])), triplet(result(["TOTAL"]))]
        text.append(f"| {d} | " + " | ".join(cols) + " |")
    text += ["", "位置状态以接纳解的钟差和 ISB 作为参考点的钟差基准。完整行、钟差增量及数值舍入见 CSV。",
             "", "## 钟差与 ISB 耦合", "",
             "| 数据包 | SPP GPS 公共钟 / GAL ISB / BDS ISB m | PPP 时间更新钟 / 接纳试次钟 m | ρ(钟,GAL) / ρ(钟,BDS) |",
             "|---|---:|---:|---:|"]
    for d,s in cases.items():
        rho = {r["to_state"]:r["value"] for r in coupling if r["dataset"]==d
               and r["kind"]=="covariance_correlation" and r["from_state"]=="GPS_clock"}
        text.append(f"| {d} | {triplet([s['spp_clock_m'],s['spp_fit_GAL_ISB_m'],s['spp_fit_BDS_ISB_m']])} | "
                    f"{s['udclk_clock_m']:+.3f}/{s['ppp_trial_clock_m']:+.3f} | "
                    f"{rho['GAL_ISB']:+.3f}/{rho['BDS_ISB']:+.3f} |")
    (OUT / "TERMINAL_TABLES.md").write_text("\n".join(text)+"\n", encoding="utf-8")
    print("\n".join(text))

def main():
    replay = read(OUT / "replay_verification.json")
    stage6 = {x["dataset"]: x for x in rows(STEP6 / "pre_q6_init.csv")}
    stage5 = {x["dataset"]: x for x in rows(STEP5 / "state_transition_budget.csv")}
    cases = {}
    tables = [[] for _ in range(6)]
    for d in DATASETS:
        stats, *items = audit_case(d,replay["datasets"][d],stage6.get(d),stage5.get(d))
        cases[d] = stats
        for table_rows, batch in zip(tables,items,strict=True):
            table_rows.extend(batch)
    names = ("spp_to_first_q6_chain.csv", "spp_accepted_rows.csv", "spp_constellation_contributions.csv",
             "spp_clock_coupling.csv", "spp_iteration_closure.csv", "spp_attempts.csv")
    for name, data in zip(names,tables,strict=True):
        assert data, name
        table(OUT / name,data)
    assert guard() == read(OUT / "input_guard_sha256.json")
    verification = dict(cases=cases, guard_counts=replay["guard_counts"], total_exact_replays=len(cases),
        total_epochs=sum(s["epochs"] for s in cases.values()), total_q6=sum(s["q6"] for s in cases.values()),
        max_fixed_reference_closure_m=max(s["fixed_reference_max_m"] for s in cases.values()),
        max_final_lsq_closure_m=max(s["final_lsq_max_m"] for s in cases.values()),
        max_iteration_sum_closure_m=max(s["iteration_sum_max_m"] for s in cases.values()),
        max_step5_prior_difference_m=max(s["step5_prior_difference_max_m"] for s in cases.values()
            if s["step5_prior_difference_max_m"] is not None),
        max_uniform_constellation_offset_position_m=max(abs(r["value"]) for r in tables[3]
            if r["kind"]=="constant_plus_1m" and r["to_state"] in ("E", "N", "U")),
        csv_rows={n:len(data) for n,data in zip(names,tables,strict=True)},
        sha256={n:sha(OUT / n) for n in (*names, "step9_probe.exe", "step9_private.patch")},
        replay_reference_feedback=False, spp_ephemeris="EPHOPT_SSRCOM",
        ppp_iono_mode="IONOOPT_EST", modear=0)
    save(OUT / "verification.json",verification)
    terminal(cases,tables[2],tables[3])

if __name__ == "__main__":
    main()
