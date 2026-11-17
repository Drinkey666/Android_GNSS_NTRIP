"""Evaluate Step 11 Part A (read-only tail60 & all-Q6 East K·v slice) and Part B (S1..S4 accuracy & closure)."""
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import mean
import sys

from run_replays import (
    CANDIDATES,
    DATASETS,
    OUT,
    ROOT,
    STEP5,
    args_for,
    baseline,
    build_guard,
    check_guard,
    read,
    rows,
    save,
    sha,
)

sys.path.insert(0, str(ROOT / "tools"))
from evaluate_solution import enu, reference_ecef

LABELS = dict(
    zip(
        DATASETS,
        ("11:20 小米", "11:20 vivo", "1004 小米", "1004 vivo", "10/31 小米 V1", "10/31 小米 V2"),
    )
)
SCHEMES = ("Baseline", *CANDIDATES)
DISPLAY = {
    "Baseline": "基线",
    "S1_O1_robust": "S1_稳健电离层锚定",
    "S2_Q0_presmooth": "S2_Q0等待期预平滑",
    "S3_presmooth_cmd": "S3_预平滑+CMD自适应R",
    "S4_joint": "S4_联合(S1+S3)",
}
CLASS_NAMES = {
    0: "OTHER",
    1: "CODE",
    2: "PHASE",
    3: "IONEX",
    4: "VMF3_ZWD",
}


def write_csv(name, data):
    fields = list(dict.fromkeys(k for r in data for k in r))
    with (OUT / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(data)


def key(week, tow):
    return int(week), round(float(tow))


def dataset_reference(d):
    if d.startswith("1031"):
        return read(ROOT / "validation/whu_first_complete_20261114/saved_v1_evaluation/summary.json")["reference"]
    args = args_for(d)
    return read(Path(args[args.index("--stream-session") + 1]) / "capture.json")["reference"]


def dxyz_to_enu(dx, dy, dz, phi, lam):
    e = -math.sin(lam) * dx + math.cos(lam) * dy
    n = -math.sin(phi) * math.cos(lam) * dx - math.sin(phi) * math.sin(lam) * dy + math.cos(phi) * dz
    u = math.cos(phi) * math.cos(lam) * dx + math.cos(phi) * math.sin(lam) * dy + math.sin(phi) * dz
    return e, n, u


def parse_step5_stat(stat_path: Path):
    """Parse $ION and $RCB records from solution.stat keyed by (week, round(tow))."""
    ion_by_sat = defaultdict(list)  # (sat) -> [(tkey, az, el, ion_m, std_m)]
    last_rcb = {}  # rcb_name -> (val_m, std_m)
    last_trop = None
    with stat_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("$ION,"):
                p = line.strip().split(",")
                tkey = key(p[1], p[2])
                sat = p[4]
                ion_by_sat[sat].append((tkey, float(p[5]), float(p[6]), float(p[7]), float(p[8])))
            elif line.startswith("$RCB,"):
                p = line.strip().split(",")
                last_rcb[p[4]] = (float(p[5]), float(p[6]))
            elif line.startswith("$TROP,"):
                p = line.strip().split(",")
                last_trop = (float(p[5]), float(p[6]))
    return ion_by_sat, last_rcb, last_trop


def parse_step5_trace_rows(trace_path: Path, valid_q6_keys: set, phi: float, lam: float):
    """Parse $S5_ROW and $S5_CLOSURE from Step 5 Baseline trace, retaining committed Q6 rows."""
    by_epoch_rows = defaultdict(list)
    by_epoch_clos = {}
    with trace_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if "$S5_ROW," in line:
                idx = line.index("$S5_ROW,")
                p = line[idx:].strip().split(",")
                tkey = key(p[1], p[2])
                if tkey not in valid_q6_keys:
                    continue
                mcls = int(p[4])
                sat = p[5]
                sig = p[6]
                slot = int(p[7])
                dx, dy, dz = float(p[8]), float(p[9]), float(p[10])
                de, dn, du = dxyz_to_enu(dx, dy, dz, phi, lam)
                post_ok = int(p[11])
                by_epoch_rows[tkey].append((mcls, sat, sig, slot, de, dn, du, post_ok))
            elif "$S5_CLOSURE," in line:
                idx = line.index("$S5_CLOSURE,")
                p = line[idx:].strip().split(",")
                tkey = key(p[1], p[2])
                if tkey not in valid_q6_keys:
                    continue
                ce = max(abs(float(p[3])), abs(float(p[4])), abs(float(p[5])))
                by_epoch_clos[tkey] = ce
    return by_epoch_rows, by_epoch_clos


def evaluate_part_a():
    """Read-only tail60 and all-Q6 East K·v equilibrium slice from saved Step 5 Baselines."""
    slice_rows = []
    top_sat_rows = []

    for d in DATASETS:
        ref = dataset_reference(d)
        phi, lam, _, _ = reference_ecef(ref)
        base_dir = baseline(d)
        base_csv = rows(base_dir / "solution.csv")
        q6 = {}
        for r in base_csv:
            if r["Q"] != "6":
                continue
            tk = key(r["week"], r["tow"])
            e, n, u = enu([float(r[k]) for k in ("x_m", "y_m", "z_m")], ref)
            tsec = int(r["week"]) * 604800 + float(r["tow"])
            q6[tk] = (tsec, e, n, u)

        ordered = list(q6.items())
        end_t = ordered[-1][1][0]
        tail_keys = {tk for tk, v in ordered if end_t - v[0] < 60.0}
        first_tk = ordered[0][0]
        all_after_first_keys = set(q6) - {first_tk}
        tail_e_mean = mean(q6[tk][1] for tk, _ in ordered if tk in tail_keys)
        all_e_mean = mean(v[1] for _, v in ordered)
        e_first = ordered[0][1][1]
        e_last = ordered[-1][1][1]
        # Epoch right before tail60 starts (if any) to track net E change across tail60
        non_tail = [tk for tk, _ in ordered if tk not in tail_keys]
        e_pre_tail = q6[non_tail[-1]][1] if non_tail else e_first

        ion_by_sat, last_rcb, last_trop = parse_step5_stat(base_dir / "solution.stat")
        by_epoch_rows, by_epoch_clos = parse_step5_trace_rows(base_dir / "solution.trace", set(q6), phi, lam)
        max_clos = max(by_epoch_clos.values()) if by_epoch_clos else 0.0

        # Accumulators for all Q6 (excluding first_tk for trajectory drift vs including first_tk)
        cls_all_ex1 = defaultdict(float)
        cls_all_inc1 = defaultdict(float)
        cls_tail = defaultdict(float)
        sig_all_inc1 = defaultdict(float)
        sig_tail = defaultdict(float)
        sat_all_inc1 = defaultdict(float)
        sat_tail = defaultdict(float)
        sat_all_code = defaultdict(float)
        sat_all_phase = defaultdict(float)
        sat_tail_code = defaultdict(float)
        sat_tail_phase = defaultdict(float)

        for tk, items in by_epoch_rows.items():
            in_tail = tk in tail_keys
            after_first = tk in all_after_first_keys
            for mcls, sat, sig, slot, de, dn, du, post_ok in items:
                cname = CLASS_NAMES.get(mcls, "OTHER")
                cls_all_inc1[cname] += de
                if after_first:
                    cls_all_ex1[cname] += de
                if in_tail:
                    cls_tail[cname] += de
                if cname in ("CODE", "PHASE") and sat != "-":
                    sys_char = sat[0]
                    sig_key = f"{cname}_{sys_char}_{sig}"
                    sig_all_inc1[sig_key] += de
                    if in_tail:
                        sig_tail[sig_key] += de
                    sat_all_inc1[sat] += de
                    if cname == "CODE":
                        sat_all_code[sat] += de
                    else:
                        sat_all_phase[sat] += de
                    if in_tail:
                        sat_tail[sat] += de
                        if cname == "CODE":
                            sat_tail_code[sat] += de
                        else:
                            sat_tail_phase[sat] += de

        # Check linear K*v trajectory sum after first Q6 vs E_last - E_first
        kv_drift_after1 = sum(cls_all_ex1.values())
        actual_drift_after1 = e_last - e_first
        drift_closure_err = abs(kv_drift_after1 - actual_drift_after1)

        # tail60 non-first keys (just in case V1 has first_q6 inside tail60)
        tail_kv_sum = sum(cls_tail.values())
        tail_kv_ex1 = sum(
            sum(it[4] for it in by_epoch_rows[tk]) for tk in tail_keys if tk in all_after_first_keys
        )

        # Dominant code/iono/phase contributors in all-Q6 and tail60
        rcb_str = "; ".join(f"{k}={v[0]:+.3f}" for k, v in sorted(last_rcb.items()) if abs(v[0]) > 1e-6)
        slice_rows.append(
            dict(
                dataset=d,
                label=LABELS[d],
                q6_epochs=len(ordered),
                tail60_epochs=len(tail_keys),
                E_first_q6_m=e_first,
                E_last_q6_m=e_last,
                all_E_mean_m=all_e_mean,
                tail60_E_mean_m=tail_e_mean,
                drift_first_to_last_E_m=actual_drift_after1,
                kv_after_first_q6_E_m=kv_drift_after1,
                drift_closure_err_m=drift_closure_err,
                max_epoch_kv_closure_m=max_clos,
                all_CODE_E_m=cls_all_inc1["CODE"],
                all_PHASE_E_m=cls_all_inc1["PHASE"],
                all_IONEX_E_m=cls_all_inc1["IONEX"],
                all_VMF3_E_m=cls_all_inc1["VMF3_ZWD"],
                ex1_CODE_E_m=cls_all_ex1["CODE"],
                ex1_PHASE_E_m=cls_all_ex1["PHASE"],
                ex1_IONEX_E_m=cls_all_ex1["IONEX"],
                ex1_VMF3_E_m=cls_all_ex1["VMF3_ZWD"],
                tail60_net_E_m=e_last - e_pre_tail,
                tail60_kv_E_m=tail_kv_sum,
                tail60_CODE_E_m=cls_tail["CODE"],
                tail60_PHASE_E_m=cls_tail["PHASE"],
                tail60_IONEX_E_m=cls_tail["IONEX"],
                tail60_VMF3_E_m=cls_tail["VMF3_ZWD"],
                CODE_G_1C_E_m=sig_all_inc1.get("CODE_G_1C", 0.0),
                CODE_G_5Q_E_m=sig_all_inc1.get("CODE_G_5Q", 0.0),
                CODE_E_1C_E_m=sig_all_inc1.get("CODE_E_1C", 0.0),
                CODE_E_5Q_E_m=sig_all_inc1.get("CODE_E_5Q", 0.0),
                CODE_C_2I_E_m=sig_all_inc1.get("CODE_C_2I", 0.0),
                CODE_C_1P_E_m=sig_all_inc1.get("CODE_C_1P", 0.0),
                CODE_C_5P_E_m=sig_all_inc1.get("CODE_C_5P", 0.0),
                tail60_mean_CODE_step_m=cls_tail["CODE"] / max(len(tail_keys), 1),
                last_trop_ztd_m=last_trop[0] if last_trop else math.nan,
                nonzero_last_rcb=rcb_str,
            )
        )

        # Rank top 6 satellites by |all_inc1 E K·v| and capture tail60 + Az/El + mean $ION
        ranked_sats = sorted(sat_all_inc1.keys(), key=lambda s: abs(sat_all_inc1[s]), reverse=True)[:8]
        for rank, sat in enumerate(ranked_sats, 1):
            ion_recs = ion_by_sat.get(sat, [])
            tail_ions = [r for r in ion_recs if r[0] in tail_keys]
            az_mean = mean(r[1] for r in ion_recs) if ion_recs else math.nan
            el_mean = mean(r[2] for r in ion_recs) if ion_recs else math.nan
            ion_mean_all = mean(r[3] for r in ion_recs) if ion_recs else math.nan
            ion_mean_tail = mean(r[3] for r in tail_ions) if tail_ions else ion_mean_all
            top_sat_rows.append(
                dict(
                    dataset=d,
                    label=LABELS[d],
                    rank=rank,
                    sat=sat,
                    az_mean_deg=az_mean,
                    el_mean_deg=el_mean,
                    all_E_kv_m=sat_all_inc1[sat],
                    all_CODE_E_kv_m=sat_all_code[sat],
                    all_PHASE_E_kv_m=sat_all_phase[sat],
                    tail60_E_kv_m=sat_tail[sat],
                    tail60_CODE_E_kv_m=sat_tail_code[sat],
                    tail60_PHASE_E_kv_m=sat_tail_phase[sat],
                    ion_mean_all_m=ion_mean_all,
                    ion_mean_tail60_m=ion_mean_tail,
                )
            )

    return slice_rows, top_sat_rows


def parse_step11_trace(trace_path: Path, valid_q6_keys: set):
    max_clos = 0.0
    infos = []
    with trace_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if "$S11_CLOSURE," in line:
                p = line[line.index("$S11_CLOSURE,") :].strip().split(",")
                tkey = key(p[1], p[2])
                if tkey in valid_q6_keys:
                    c = max(abs(float(p[3])), abs(float(p[4])), abs(float(p[5])))
                    if c > max_clos:
                        max_clos = c
            elif "$S11_INFO," in line:
                p = line[line.index("$S11_INFO,") :].strip().split(",")
                tkey = key(p[1], p[2])
                if tkey in valid_q6_keys:
                    infos.append(
                        dict(
                            tkey=tkey,
                            ndf=int(p[3]),
                            nsf=int(p[4]),
                            delta_df=float(p[5]),
                            q0_epochs=int(p[6]),
                            q0_smoothed=int(p[7]),
                            cmd_rows=int(p[8]),
                            cmd_inflated=int(p[9]),
                            cmd_max_f=float(p[10]),
                            cmd_mean_f=float(p[11]),
                        )
                    )
    return max_clos, infos


def calc_stats(pts):
    return dict(
        n=len(pts),
        E_mean_m=mean(p[1] for p in pts),
        N_mean_m=mean(p[2] for p in pts),
        U_mean_m=mean(p[3] for p in pts),
        H_rms_m=math.sqrt(mean(p[1] ** 2 + p[2] ** 2 for p in pts)),
        U_rms_m=math.sqrt(mean(p[3] ** 2 for p in pts)),
    )


def evaluate_part_b():
    summary_rows = []
    paired_q6_rows = []
    cmd_presmooth_rows = []
    verify_cases = []
    q_series_by_ds_scheme = {}

    for d in DATASETS:
        ref = dataset_reference(d)
        base_folder = baseline(d)
        base_csv = rows(base_folder / "solution.csv")
        base_stats = None

        for s in SCHEMES:
            folder = base_folder if s == "Baseline" else (OUT / "runs" / d / s)
            data = base_csv if s == "Baseline" else rows(folder / "solution.csv")
            if s != "Baseline":
                assert [(r["week"], r["tow"]) for r in data] == [(r["week"], r["tow"]) for r in base_csv]
                assert [r["Q"] for r in data] == [r["Q"] for r in base_csv]
                assert all(sha(folder / f) == sha(base_folder / f) for f in ("observations.csv", "corrections.csv"))

            q = {}
            for r in data:
                if r["Q"] != "6":
                    continue
                t = key(r["week"], r["tow"])
                assert t not in q
                e, n, u = enu([float(r[k]) for k in ("x_m", "y_m", "z_m")], ref)
                q[t] = (int(r["week"]) * 604800 + float(r["tow"]), e, n, u, math.hypot(e, n))
            q_series_by_ds_scheme[(d, s)] = q

            pts = list(q.values())
            end_t = pts[-1][0]
            first_pt = pts[0]
            w_first20 = pts[:20]
            w_first60 = pts[:60]
            w_tail60 = [p for p in pts if end_t - p[0] < 60.0]

            row = dict(
                dataset=d,
                label=LABELS[d],
                scheme=s,
                display=DISPLAY[s],
                first_q6_E_m=first_pt[1],
                first_q6_N_m=first_pt[2],
                first_q6_U_m=first_pt[3],
                first_q6_H_m=first_pt[4],
            )
            for wname, wpts in (("first20", w_first20), ("first60", w_first60), ("all", pts), ("tail60", w_tail60)):
                st = calc_stats(wpts)
                for k, v in st.items():
                    row[f"{wname}_{k}"] = v
            if s == "Baseline":
                base_stats = row
            row["d_first20_H_rms_m"] = row["first20_H_rms_m"] - base_stats["first20_H_rms_m"]
            row["d_first20_U_rms_m"] = row["first20_U_rms_m"] - base_stats["first20_U_rms_m"]
            row["d_all_H_rms_m"] = row["all_H_rms_m"] - base_stats["all_H_rms_m"]
            row["d_all_U_rms_m"] = row["all_U_rms_m"] - base_stats["all_U_rms_m"]
            row["d_tail60_H_rms_m"] = row["tail60_H_rms_m"] - base_stats["tail60_H_rms_m"]
            row["d_tail60_U_rms_m"] = row["tail60_U_rms_m"] - base_stats["tail60_U_rms_m"]
            summary_rows.append(row)

            if s != "Baseline":
                max_clos, infos = parse_step11_trace(folder / "solution.trace", set(q))
                q0_ep = infos[0]["q0_epochs"] if infos else 0
                q0_sm = infos[0]["q0_smoothed"] if infos else 0
                cmd_rows_tot = sum(x["cmd_rows"] for x in infos)
                cmd_inf_tot = sum(x["cmd_inflated"] for x in infos)
                cmd_inf_frac = (cmd_inf_tot / cmd_rows_tot) if cmd_rows_tot > 0 else 0.0
                cmd_max_f = max((x["cmd_max_f"] for x in infos), default=1.0)
                cmd_mean_f = mean(x["cmd_mean_f"] for x in infos if x["cmd_rows"] > 0) if any(x["cmd_rows"] > 0 for x in infos) else 1.0
                ndf_mean = mean(x["ndf"] for x in infos) if infos else 0.0
                nsf_mean = mean(x["nsf"] for x in infos) if infos else 0.0
                ddf_mean = mean(x["delta_df"] for x in infos) if infos else 0.0

                cmd_presmooth_rows.append(
                    dict(
                        dataset=d,
                        label=LABELS[d],
                        scheme=s,
                        q6_epochs=len(pts),
                        q0_wait_epochs=q0_ep,
                        q0_wait_smoothed_slots=q0_sm,
                        mean_ndf=ndf_mean,
                        mean_nsf=nsf_mean,
                        mean_delta_df_m=ddf_mean,
                        cmd_code_rows_total=cmd_rows_tot,
                        cmd_inflated_rows_total=cmd_inf_tot,
                        cmd_inflated_frac=cmd_inf_frac,
                        cmd_mean_f=cmd_mean_f,
                        cmd_max_f=cmd_max_f,
                    )
                )
                verify_cases.append(
                    dict(
                        dataset=d,
                        scheme=s,
                        epochs=len(data),
                        q6=len(pts),
                        same_q_sequence=True,
                        same_observations=True,
                        same_corrections=True,
                        max_kv_closure_m=max_clos,
                        q0_wait_epochs=q0_ep,
                        q0_wait_smoothed_slots=q0_sm,
                        cmd_inflated_frac=cmd_inf_frac,
                        cmd_mean_f=cmd_mean_f,
                        cmd_max_f=cmd_max_f,
                    )
                )

    for pair_name, d_a, d_b in [("11:20", "1120_xiaomi", "1120_vivo"), ("10:04", "1004_xiaomi", "1004_vivo")]:
        for s in SCHEMES:
            qa = q_series_by_ds_scheme[(d_a, s)]
            qb = q_series_by_ds_scheme[(d_b, s)]
            common_t = sorted(set(qa) & set(qb))
            pts_a = [qa[t] for t in common_t]
            pts_b = [qb[t] for t in common_t]
            sta, stb = calc_stats(pts_a), calc_stats(pts_b)
            paired_q6_rows.append(
                dict(
                    pair=pair_name,
                    scheme=s,
                    common_q6=len(common_t),
                    xiaomi_H_rms_m=sta["H_rms_m"],
                    xiaomi_U_rms_m=sta["U_rms_m"],
                    xiaomi_E_mean_m=sta["E_mean_m"],
                    xiaomi_N_mean_m=sta["N_mean_m"],
                    vivo_H_rms_m=stb["H_rms_m"],
                    vivo_U_rms_m=stb["U_rms_m"],
                    vivo_E_mean_m=stb["E_mean_m"],
                    vivo_N_mean_m=stb["N_mean_m"],
                )
            )

    return summary_rows, paired_q6_rows, cmd_presmooth_rows, verify_cases


def md_table(headers, body):
    return "\n".join("| " + " | ".join(map(str, r)) + " |" for r in (headers, ["---"] * len(headers), *body))


def main():
    guard = build_guard()
    assert guard == read(OUT / "input_guard_sha256.json")
    check_guard(guard)

    slice_rows, top_sat_rows = evaluate_part_a()
    summary_rows, paired_q6_rows, cmd_presmooth_rows, verify_cases = evaluate_part_b()

    write_csv("partA_tail60_east_slice.csv", slice_rows)
    write_csv("partA_tail60_top_sats.csv", top_sat_rows)
    write_csv("partB_accuracy_summary.csv", summary_rows)
    write_csv("partB_paired_common_q6.csv", paired_q6_rows)
    write_csv("partB_cmd_presmooth_stats.csv", cmd_presmooth_rows)

    t_pa = md_table(
        [
            "数据集",
            "Q6/tail",
            "首/末 Q6 E (m)",
            "全段/末60s E均值",
            "首后Code/Phase/IONEX/ZWD E",
            "末60s净ΔE / 步均Code",
            "末60s Code/Phase/IONEX E",
            "末历元非零 $RCB (m)",
        ],
        [
            [
                r["label"],
                f"{r['q6_epochs']}/{r['tail60_epochs']}",
                f"{r['E_first_q6_m']:+.3f}/{r['E_last_q6_m']:+.3f}",
                f"{r['all_E_mean_m']:+.3f}/{r['tail60_E_mean_m']:+.3f}",
                f"{r['ex1_CODE_E_m']:+.3f}/{r['ex1_PHASE_E_m']:+.3f}/{r['ex1_IONEX_E_m']:+.3f}/{r['ex1_VMF3_E_m']:+.3f}",
                f"{r['tail60_net_E_m']:+.3f}/{r['tail60_mean_CODE_step_m']:+.4f}",
                f"{r['tail60_CODE_E_m']:+.3f}/{r['tail60_PHASE_E_m']:+.3f}/{r['tail60_IONEX_E_m']:+.3f}",
                r["nonzero_last_rcb"] or "-",
            ]
            for r in slice_rows
        ],
    )

    t_pa_sats = md_table(
        ["数据集", "卫星", "Az/El (°)", "全段E K·v", "全段Code/Phase E", "末60s E K·v", "全段/末60s $ION (m)"],
        [
            [
                r["label"],
                r["sat"],
                f"{r['az_mean_deg']:.1f}/{r['el_mean_deg']:.1f}",
                f"{r['all_E_kv_m']:+.3f}",
                f"{r['all_CODE_E_kv_m']:+.3f}/{r['all_PHASE_E_kv_m']:+.3f}",
                f"{r['tail60_E_kv_m']:+.3f}",
                f"{r['ion_mean_all_m']:.2f}/{r['ion_mean_tail60_m']:.2f}",
            ]
            for r in top_sat_rows
            if r["rank"] <= 4
        ],
    )

    t_pb = md_table(
        ["数据集", "方案", "首Q6 H/U", "前20 H/U RMS", "前60 H/U RMS", "全段 H/U RMS", "末60s E均值 / H/U RMS"],
        [
            [
                r["label"],
                DISPLAY[r["scheme"]],
                f"{r['first_q6_H_m']:.3f}/{r['first_q6_U_m']:+.3f}",
                f"{r['first20_H_rms_m']:.3f}/{r['first20_U_rms_m']:.3f}",
                f"{r['first60_H_rms_m']:.3f}/{r['first60_U_rms_m']:.3f}",
                f"{r['all_H_rms_m']:.3f}/{r['all_U_rms_m']:.3f}",
                f"{r['tail60_E_mean_m']:+.3f} / {r['tail60_H_rms_m']:.3f}/{r['tail60_U_rms_m']:.3f}",
            ]
            for r in summary_rows
        ],
    )

    t_pb_stats = md_table(
        ["数据集", "方案", "Q0等历元/平滑槽", "均值ndf/nsf", "均值δI_df (m)", "CMD行/放大占比", "CMD均值/最大f"],
        [
            [
                r["label"],
                DISPLAY[r["scheme"]],
                f"{r['q0_wait_epochs']}/{r['q0_wait_smoothed_slots']}",
                f"{r['mean_ndf']:.1f}/{r['mean_nsf']:.1f}",
                f"{r['mean_delta_df_m']:+.3f}",
                f"{r['cmd_code_rows_total']}/{r['cmd_inflated_frac']:.1%}",
                f"{r['cmd_mean_f']:.2f}/{r['cmd_max_f']:.2f}",
            ]
            for r in cmd_presmooth_rows
        ],
    )

    t_pb_pair = md_table(
        ["时段", "方案", "共有 Q6", "小米 H/U RMS (m)", "小米 E/N 均值 (m)", "vivo H/U RMS (m)", "vivo E/N 均值 (m)"],
        [
            [
                r["pair"],
                DISPLAY[r["scheme"]],
                r["common_q6"],
                f"{r['xiaomi_H_rms_m']:.3f}/{r['xiaomi_U_rms_m']:.3f}",
                f"{r['xiaomi_E_mean_m']:+.3f}/{r['xiaomi_N_mean_m']:+.3f}",
                f"{r['vivo_H_rms_m']:.3f}/{r['vivo_U_rms_m']:.3f}",
                f"{r['vivo_E_mean_m']:+.3f}/{r['vivo_N_mean_m']:+.3f}",
            ]
            for r in paired_q6_rows
        ],
    )

    terminal_md = (
        "# Step 11 终端汇总\n\n"
        "## Part A1 · 已保存基线全段与 tail60 东向 K·v 平衡切片（只读）\n\n"
        + t_pa
        + "\n\n## Part A2 · 主导东向 K·v 卫星与 Az/El/$ION 上下文（每包前 4 颗）\n\n"
        + t_pa_sats
        + "\n\n## Part B1 · Step 11 (S1..S4) 全量回放精度对比（m）\n\n"
        + t_pb
        + "\n\n## Part B2 · Q0 预平滑、双频电离层锚定与 CMD 自适应定权统计\n\n"
        + t_pb_stats
        + "\n\n## Part B3 · 11:20 与 10:04 双机共有 Q6 配对精度（m）\n\n"
        + t_pb_pair
        + "\n"
    )
    (OUT / "TERMINAL_TABLES.md").write_text(terminal_md, encoding="utf-8")

    out_csvs = (
        "partA_tail60_east_slice.csv",
        "partA_tail60_top_sats.csv",
        "partB_accuracy_summary.csv",
        "partB_paired_common_q6.csv",
        "partB_cmd_presmooth_stats.csv",
    )
    max_parta_clos = max(r["max_epoch_kv_closure_m"] for r in slice_rows)
    max_partb_clos = max(c["max_kv_closure_m"] for c in verify_cases)
    verification = dict(
        guard_files=len(guard),
        new_replays=len(verify_cases),
        baseline_reused=len(DATASETS),
        all_same_q_sequence=all(c["same_q_sequence"] for c in verify_cases),
        all_same_observations=all(c["same_observations"] for c in verify_cases),
        all_same_corrections=all(c["same_corrections"] for c in verify_cases),
        max_partA_epoch_kv_closure_m=max_parta_clos,
        max_kv_closure_m=max_partb_clos,
        used_if=False,
        used_ar=False,
        reference_used_only_after_replay=True,
        no_production_changes=True,
        cases=verify_cases,
        sha256={
            **{n: sha(OUT / n) for n in (*out_csvs, "step11_probe.exe", "step11_private.patch", "step11_mods.inc")},
        },
    )
    save(OUT / "verification.json", verification)
    print(terminal_md)
    print("Verification max_kv_closure_m:", max_partb_clos)
    print("Verification max_partA_epoch_kv_closure_m:", max_parta_clos)


if __name__ == "__main__":
    main()
