"""Evaluate Step 10 Part A (physical decomposition & startup gates) and Part B (O1/O2/O3 accuracy)."""
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
from statistics import mean
import sys

import numpy as np

from run_replays import (
    CANDIDATES,
    DATASETS,
    OUT,
    ROOT,
    STEP5,
    STEP9,
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

LABELS = dict(zip(DATASETS, ("11:20 小米", "11:20 vivo", "1004 小米", "1004 vivo", "10/31 小米 V1", "10/31 小米 V2")))
SCHEMES = ("Baseline", *CANDIDATES)
DISPLAY = {
    "Baseline": "基线",
    "O1_df_iono_anchor": "O1_双频电离层锚定",
    "O2_arc_code_info": "O2_连续弧平滑码去重",
    "O3_joint": "O3_联合(O1+O2)",
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


def load_step9_spp():
    accepted = rows(STEP9 / "spp_accepted_rows.csv")
    v9 = read(STEP9 / "verification.json")
    by_ds = defaultdict(list)
    for r in accepted:
        by_ds[r["dataset"]].append(r)
    # Reconstruct before_xyz / after_anchor for exact linearized range check from observer.tsv
    spp_meta = {}
    for d in DATASETS:
        obs_path = STEP9 / "runs" / d / "observer.tsv"
        attempt = v9["cases"][d]["selected_attempt"]
        last_step = None
        with obs_path.open(encoding="ascii") as f:
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if parts[0] == "STEP" and int(parts[2]) == attempt:
                    it = int(parts[3])
                    nx = 9
                    vecs = [float(x) for x in parts[5:]]
                    before = np.array(vecs[:nx])
                    dx = np.array(vecs[nx : 2 * nx])
                    after = np.array(vecs[2 * nx : 3 * nx])
                    last_step = (it, before, dx, after)
        assert last_step is not None, d
        spp_meta[d] = dict(before=last_step[1], dx=last_step[2], after=last_step[3],
                           week=v9["cases"][d]["boot_week"], tow=v9["cases"][d]["boot_tow"])
    return by_ds, spp_meta, v9


def load_parta_tsv(d):
    p = OUT / "runs" / d / "O2_arc_code_info" / "partA_ppp_first_q6.tsv"
    v9_case = read(STEP9 / "verification.json")["cases"][d]
    target_key = (v9_case["first_q6_week"], round(v9_case["first_q6_tow"]))
    startqc = []
    ppp_rows = {}
    with p.open(encoding="ascii") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            kind = parts[0]
            w, t = int(parts[1]), float(parts[2])
            if (w, round(t)) != target_key:
                continue
            if kind == "STARTQC":
                _, _, _, sat, slot, grp, sig, refsig, peers, res, centre, mad, gate, pos_gate = parts
                startqc.append(dict(
                    sat=sat, slot=int(slot), grp=int(grp), sig=sig, refsig=refsig,
                    peers=int(peers), residual=float(res), centre=float(centre),
                    mad=float(mad), gate=float(gate), position_gate=float(pos_gate),
                ))
            elif kind == "PPP_ROW":
                (
                    _, _, _, sat, slot, sig, p_corr, r, m_c_dts, dtrp, dion_sig,
                    ion_gim_v, mapf, ion_var_prior, base_obs_var, vart, vari, var_rs,
                    sigma0, res, az_deg, el_deg, dion_l1
                ) = parts
                if int(slot) == 1:
                    ppp_rows[sat] = dict(
                        sig=sig, P_corr=float(p_corr), r=float(r), minus_c_dts=float(m_c_dts),
                        dtrp_vmf3=float(dtrp), dion_gim_sig=float(dion_sig),
                        ion_gim_vert=float(ion_gim_v), mapf=float(mapf),
                        ion_var_prior=float(ion_var_prior), sigma0=float(sigma0),
                        prefit_ppp=float(res), dion_l1=float(dion_l1),
                    )
    assert startqc and ppp_rows, d
    return startqc, ppp_rows


def evaluate_part_a(by_ds, spp_meta, v9):
    paired_rows = []
    paired_summary = []
    single_rows = []
    single_summary = []

    # 1. Exact physical decomposition for every dataset row & Part A iono/trop/gate comparison
    per_ds_measured = {}
    for d in DATASETS:
        ref = dataset_reference(d)
        _, _, ref_xyz, _ = reference_ecef(ref)
        ref_xyz = np.array(ref_xyz)
        before = spp_meta[d]["before"]
        after = spp_meta[d]["after"]
        startqc, ppp_first = load_parta_tsv(d)
        startqc_geoms = {
            (r["sat"], r["sig"]): r
            for r in startqc if r["refsig"] == "GEOMETRY"
        }
        startqc_all = {}
        for r in startqc:
            k = (r["grp"], r["sig"], r["refsig"])
            startqc_all.setdefault(k, []).append(r)

        drows = by_ds[d]
        measured = [r for r in drows if int(r["datum"]) < 0]
        H_mat = np.array([[float(r[c]) for c in ("H_X","H_Y","H_Z","H_GPS_clock","H_GLO_ISB","H_GAL_ISB","H_BDS_ISB","H_IRN_ISB","H_QZS_ISB")] for r in drows])
        var_vec = np.array([float(r["variance_m2"]) for r in drows])
        v_nl = np.array([float(r["postfit_nonlinear_m"]) for r in drows])
        B = H_mat / np.sqrt(var_vec)[:, None]
        Q_mat = np.linalg.inv(B.T @ B)

        # Verify physical sum for every measured row
        sys_rows = defaultdict(list)
        max_decomp_err = 0.0
        max_z_lev = 0.0
        max_abs_res = 0.0
        worst_fde_desc = ""
        ds_meas_map = {}

        for j, r in enumerate(drows):
            if int(r["datum"]) >= 0:
                continue
            sat = r["sat"]
            sig = r["signal"]
            sys_name = r["group"].split()[0]
            h_xyz = np.array([float(r["H_X"]), float(r["H_Y"]), float(r["H_Z"])])
            r_ref_lin = float(r["geometric_range_m"]) - float(h_xyz @ (before[:3] - ref_xyz))
            p_raw = float(r["P_raw_m"])
            p_corr = float(r["P_corrected_m"])
            osb = p_corr - p_raw
            m_c_dts = float(r["minus_c_sat_clock_m"])
            iono_brdc = float(r["broadcast_iono_m"])
            trop_saas = float(r["saastamoinen_trop_m"])
            # Clock anchor at reference position: after[3] + H[4:] @ after[4:]
            clk_anchor = float(after[3] + H_mat[j, 4:] @ after[4:])
            v_ref_check = p_raw + osb - r_ref_lin - m_c_dts - iono_brdc - trop_saas - clk_anchor
            v_ref = float(r["v_at_linearized_reference_m"])
            err = abs(v_ref_check - v_ref)
            max_decomp_err = max(max_decomp_err, err)
            assert err < 1e-7, (d, sat, err)

            # startup_fde leverage z
            z_raw = abs(v_nl[j]) / math.sqrt(var_vec[j])
            lev = float(B[j] @ Q_mat @ B[j])
            z_lev = z_raw / math.sqrt(max(0.05, 1.0 - lev))
            if abs(v_nl[j]) > max_abs_res:
                max_abs_res = abs(v_nl[j])
            if z_lev > max_z_lev:
                max_z_lev = z_lev
                worst_fde_desc = f"{sat} {sig} (res={v_nl[j]:+.3f}m, z={z_lev:.3f})"

            # First-Q6 PPP GIM / VMF3 comparison
            prow = ppp_first.get(sat)
            dion_gim = prow["dion_gim_sig"] if prow else float("nan")
            dtrp_vmf3 = prow["dtrp_vmf3"] if prow else float("nan")
            iono_diff_brdc_minus_gim = iono_brdc - dion_gim if prow else float("nan")
            trop_diff_saas_minus_vmf3 = trop_saas - dtrp_vmf3 if prow else float("nan")
            k_e = float(r["K_E"])
            k_n = float(r["K_N"])
            k_u = float(r["K_U"])
            # Notice: v = P - (r + clk + iono + trop). Replacing brdc_iono with GIM shifts v by +(brdc - GIM) = -(GIM - brdc)
            east_push_brdc_vs_gim = k_e * (-iono_diff_brdc_minus_gim) if prow else float("nan")
            east_push_saas_vs_vmf3 = k_e * (-trop_diff_saas_minus_vmf3) if prow else float("nan")

            sq = startqc_geoms.get((sat, sig))
            sq_dev = (sq["residual"] - sq["centre"]) if sq else float("nan")
            sq_gate = sq["gate"] if sq else float("nan")
            sq_mad = sq["mad"] if sq else float("nan")
            sq_ratio = abs(sq_dev) / sq_gate if (sq and sq_gate > 0) else float("nan")

            rec = dict(
                dataset=d, sat=sat, group=r["group"], signal=sig,
                el_deg=float(r["el_deg"]), SNR_dBHz=float(r["SNR_dBHz"]),
                weight_m_minus2=float(r["weight_m_minus2"]),
                P_raw_minus_r_ref_m=p_raw - r_ref_lin,
                osb_m=osb, minus_c_dts_m=m_c_dts,
                broadcast_iono_m=iono_brdc, ppp_gim_iono_m=dion_gim,
                iono_brdc_minus_gim_m=iono_diff_brdc_minus_gim,
                saastamoinen_trop_m=trop_saas, ppp_vmf3_trop_m=dtrp_vmf3,
                trop_saas_minus_vmf3_m=trop_diff_saas_minus_vmf3,
                v_ref_m=v_ref, v_shape_m=float(r["clock_projected_v_ref_m"]),
                K_E=k_e, K_N=k_n, K_U=k_u,
                Kv_ref_E_m=float(r["Kv_ref_E"]), Kv_ref_N_m=float(r["Kv_ref_N"]), Kv_ref_U_m=float(r["Kv_ref_U"]),
                Kv_shape_E_m=float(r["Kv_shape_E"]),
                east_push_brdc_vs_gim_m=east_push_brdc_vs_gim,
                east_push_saas_vs_vmf3_m=east_push_saas_vs_vmf3,
                fde_postfit_nl_m=float(v_nl[j]), fde_z_leverage=z_lev,
                startqc_geom_dev_m=sq_dev, startqc_geom_mad_m=sq_mad,
                startqc_geom_gate_m=sq_gate, startqc_geom_ratio=sq_ratio,
                decomp_closure_err_m=err,
            )
            single_rows.append(rec)
            sys_rows[sys_name].append(rec)
            ds_meas_map[sat] = rec

        per_ds_measured[d] = ds_meas_map

        # Compute max STARTQC ratio across all groups (both GEOMETRY and code pairs)
        worst_sq_ratio = 0.0
        worst_sq_desc = ""
        for (grp, sig, refsig), items in startqc_all.items():
            for it in items:
                ratio = abs(it["residual"] - it["centre"]) / it["gate"]
                if ratio > worst_sq_ratio:
                    worst_sq_ratio = ratio
                    worst_sq_desc = f"{it['sat']} {sig}/{refsig} (dev={it['residual']-it['centre']:+.3f}m, gate={it['gate']:.2f}m, ratio={ratio:.3f})"

        for sys_name, items in sys_rows.items():
            has_ppp = [x for x in items if not math.isnan(x["east_push_brdc_vs_gim_m"])]
            single_summary.append(dict(
                dataset=d, group=items[0]["group"], rows=len(items),
                Kv_E_m=math.fsum(x["Kv_ref_E_m"] for x in items),
                iono_brdc_vs_gim_E_m=math.fsum(x["east_push_brdc_vs_gim_m"] for x in has_ppp),
                trop_saas_vs_vmf3_E_m=math.fsum(x["east_push_saas_vs_vmf3_m"] for x in has_ppp),
                residual_after_ppp_atmo_E_m=math.fsum(x["Kv_ref_E_m"] for x in items) - math.fsum(x["east_push_brdc_vs_gim_m"] for x in has_ppp) - math.fsum(x["east_push_saas_vs_vmf3_m"] for x in has_ppp),
                max_decomp_err_m=max_decomp_err,
                fde_max_abs_res_m=max_abs_res, fde_max_z_lev=max_z_lev, fde_worst=worst_fde_desc,
                startqc_max_ratio=worst_sq_ratio, startqc_worst=worst_sq_desc,
            ))

    # 2. Paired dual-device decomposition (Xiaomi vs Vivo at the same GPST second)
    for pair_name, d_a, d_b in [("11:20", "1120_xiaomi", "1120_vivo"), ("10:04", "1004_xiaomi", "1004_vivo")]:
        ma, mb = per_ds_measured[d_a], per_ds_measured[d_b]
        common_sats = sorted(set(ma) & set(mb))
        only_a = sorted(set(ma) - set(mb))
        only_b = sorted(set(mb) - set(ma))

        # Within each constellation's common satellites, remove unweighted mean to inspect physical terms cleanly
        by_sys = defaultdict(list)
        for s in common_sats:
            by_sys[ma[s]["group"]].append(s)

        # Also do exact Shapley Oaxaca-Blinder decomposition of E_A - E_B on v_ref!
        total_raw_diff_E = 0.0
        total_osb_diff_E = 0.0
        total_sclk_diff_E = 0.0
        total_iono_diff_E = 0.0
        total_trop_diff_E = 0.0
        total_meas_E = 0.0
        total_weight_E = 0.0
        total_only_a_E = math.fsum(ma[s]["Kv_ref_E_m"] for s in only_a)
        total_only_b_E = -math.fsum(mb[s]["Kv_ref_E_m"] for s in only_b)

        for grp, sats in by_sys.items():
            # Common-subset mean across each physical term (so constellation clock/ISB cancels in relative terms)
            mean_raw_a = mean(ma[s]["P_raw_minus_r_ref_m"] for s in sats)
            mean_raw_b = mean(mb[s]["P_raw_minus_r_ref_m"] for s in sats)
            mean_osb_a = mean(ma[s]["osb_m"] for s in sats)
            mean_osb_b = mean(mb[s]["osb_m"] for s in sats)
            mean_clk_a = mean(ma[s]["minus_c_dts_m"] for s in sats)
            mean_clk_b = mean(mb[s]["minus_c_dts_m"] for s in sats)
            mean_ion_a = mean(ma[s]["broadcast_iono_m"] for s in sats)
            mean_ion_b = mean(mb[s]["broadcast_iono_m"] for s in sats)
            mean_trp_a = mean(ma[s]["saastamoinen_trop_m"] for s in sats)
            mean_trp_b = mean(mb[s]["saastamoinen_trop_m"] for s in sats)

            for s in sats:
                ra, rb = ma[s], mb[s]
                raw_rel_a = ra["P_raw_minus_r_ref_m"] - mean_raw_a
                raw_rel_b = rb["P_raw_minus_r_ref_m"] - mean_raw_b
                osb_rel_a = ra["osb_m"] - mean_osb_a
                osb_rel_b = rb["osb_m"] - mean_osb_b
                clk_rel_a = -(ra["minus_c_dts_m"] - mean_clk_a)
                clk_rel_b = -(rb["minus_c_dts_m"] - mean_clk_b)
                ion_rel_a = -(ra["broadcast_iono_m"] - mean_ion_a)
                ion_rel_b = -(rb["broadcast_iono_m"] - mean_ion_b)
                trp_rel_a = -(ra["saastamoinen_trop_m"] - mean_trp_a)
                trp_rel_b = -(rb["saastamoinen_trop_m"] - mean_trp_b)

                v_rel_a = raw_rel_a + osb_rel_a + clk_rel_a + ion_rel_a + trp_rel_a
                v_rel_b = raw_rel_b + osb_rel_b + clk_rel_b + ion_rel_b + trp_rel_b
                # Note: since K_E sums to 0 over any constant shift per constellation, K_E * v_rel == K_E * v_ref!
                k_avg = 0.5 * (ra["K_E"] + rb["K_E"])
                k_diff = ra["K_E"] - rb["K_E"]
                # Wait: because only_a/only_b exist, sum_{s in common} K_E(s) may be slightly != 0,
                # so for exact algebraic closure on common sats we use v_ref_a - v_ref_b directly for Shapley,
                # and note the exact identity between v_rel difference and (P_raw - r_ref) difference!
                dv_raw = raw_rel_a - raw_rel_b
                dv_osb = osb_rel_a - osb_rel_b
                dv_clk = clk_rel_a - clk_rel_b
                dv_ion = ion_rel_a - ion_rel_b
                dv_trp = trp_rel_a - trp_rel_b
                dv_rel = v_rel_a - v_rel_b
                assert abs(dv_rel - (dv_raw + dv_osb + dv_clk + dv_ion + dv_trp)) < 1e-7

                # Note: v_ref_a - v_ref_b = (v_rel_a - v_rel_b) + const_clock_diff_within_grp
                # Since sum_{all A} K_A * const == 0, for common sats we use exact v_ref for exact E_A - E_B closure,
                # and compute the physical-term attribution using k_avg * dv_term!
                e_meas_exact = k_avg * (ra["v_ref_m"] - rb["v_ref_m"])
                e_wt_exact = 0.5 * k_diff * (ra["v_ref_m"] + rb["v_ref_m"])
                e_diff_row = ra["Kv_ref_E_m"] - rb["Kv_ref_E_m"]
                assert abs((e_meas_exact + e_wt_exact) - e_diff_row) < 1e-12

                total_raw_diff_E += k_avg * dv_raw
                total_osb_diff_E += k_avg * dv_osb
                total_sclk_diff_E += k_avg * dv_clk
                total_iono_diff_E += k_avg * dv_ion
                total_trop_diff_E += k_avg * dv_trp
                total_meas_E += e_meas_exact
                total_weight_E += e_wt_exact

                paired_rows.append(dict(
                    pair=pair_name, sat=s, group=grp, status="COMMON",
                    el_deg_a=ra["el_deg"], el_deg_b=rb["el_deg"],
                    snr_a=ra["SNR_dBHz"], snr_b=rb["SNR_dBHz"],
                    weight_a=ra["weight_m_minus2"], weight_b=rb["weight_m_minus2"],
                    raw_rel_a_m=raw_rel_a, raw_rel_b_m=raw_rel_b,
                    diff_raw_rel_m=dv_raw, diff_osb_rel_m=dv_osb,
                    diff_sclk_rel_m=dv_clk, diff_iono_rel_m=dv_ion, diff_trop_rel_m=dv_trp,
                    v_rel_a_m=v_rel_a, v_rel_b_m=v_rel_b, diff_v_rel_m=dv_rel,
                    v_shape_a_m=ra["v_shape_m"], v_shape_b_m=rb["v_shape_m"],
                    K_E_a=ra["K_E"], K_E_b=rb["K_E"],
                    Kv_E_a_m=ra["Kv_ref_E_m"], Kv_E_b_m=rb["Kv_ref_E_m"],
                    diff_Kv_E_m=e_diff_row,
                    shapley_meas_E_m=e_meas_exact, shapley_weight_E_m=e_wt_exact,
                    shapley_raw_code_E_m=k_avg * dv_raw,
                ))

        for s in only_a:
            ra = ma[s]
            paired_rows.append(dict(
                pair=pair_name, sat=s, group=ra["group"], status=f"ONLY_{d_a}",
                el_deg_a=ra["el_deg"], snr_a=ra["SNR_dBHz"], weight_a=ra["weight_m_minus2"],
                v_shape_a_m=ra["v_shape_m"], K_E_a=ra["K_E"], Kv_E_a_m=ra["Kv_ref_E_m"],
                diff_Kv_E_m=ra["Kv_ref_E_m"],
            ))
        for s in only_b:
            rb = mb[s]
            paired_rows.append(dict(
                pair=pair_name, sat=s, group=rb["group"], status=f"ONLY_{d_b}",
                el_deg_b=rb["el_deg"], snr_b=rb["SNR_dBHz"], weight_b=rb["weight_m_minus2"],
                v_shape_b_m=rb["v_shape_m"], K_E_b=rb["K_E"], Kv_E_b_m=rb["Kv_ref_E_m"],
                diff_Kv_E_m=-rb["Kv_ref_E_m"],
            ))

        spp_e_a = v9["cases"][d_a]["spp_enu_m"][0]
        spp_e_b = v9["cases"][d_b]["spp_enu_m"][0]
        actual_diff_e = spp_e_a - spp_e_b
        sum_check = total_meas_E + total_weight_E + total_only_a_E + total_only_b_E
        # Note tiny roundoff in spp_enu_m vs sum of Kv_ref_E (~1e-10)
        paired_summary.append(dict(
            pair=pair_name, device_a=d_a, device_b=d_b,
            common_sats=len(common_sats), only_a=",".join(only_a), only_b=",".join(only_b),
            spp_E_a_m=spp_e_a, spp_E_b_m=spp_e_b, actual_diff_E_m=actual_diff_e,
            shapley_meas_E_m=total_meas_E, shapley_weight_E_m=total_weight_E,
            only_a_E_m=total_only_a_E, only_b_E_m=total_only_b_E,
            shapley_raw_rel_E_m=total_raw_diff_E, shapley_osb_rel_E_m=total_osb_diff_E,
            shapley_sclk_rel_E_m=total_sclk_diff_E, shapley_iono_rel_E_m=total_iono_diff_E,
            shapley_trop_rel_E_m=total_trop_diff_E,
            closure_diff_m=abs(actual_diff_e - sum_check),
        ))

    return paired_rows, paired_summary, single_rows, single_summary


def parse_partb_trace(trace_path, q_keys):
    closures = {}
    o1_info = []
    o2_info = []
    with trace_path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            assert "$S10_INVALID_PROFILE" not in line, trace_path
            if "$S10_CLOSURE," in line:
                w, t, *xyz = line.strip().split("$S10_CLOSURE,", 1)[1].split(",")
                idx = key(w, t)
                closures[idx] = max(abs(float(v)) for v in xyz)
            elif "$S10_O1," in line:
                w, t, ndf, nsf, ddf = line.strip().split("$S10_O1,", 1)[1].split(",")
                o1_info.append((key(w, t), int(ndf), int(nsf), float(ddf)))
            elif "$S10_O2," in line:
                w, t, cnt, maxf = line.strip().split("$S10_O2,", 1)[1].split(",")
                o2_info.append((key(w, t), int(cnt), float(maxf)))
    assert q_keys <= closures.keys(), (trace_path, len(q_keys), len(closures))
    max_closure = max(closures[k] for k in q_keys)
    assert max_closure < 1e-8, (trace_path, max_closure)
    return max_closure, o1_info, o2_info


def calc_stats(pts):
    if not pts:
        return {}
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
    verify_cases = []
    q_series_by_ds_scheme = {}

    for d in DATASETS:
        ref = dataset_reference(d)
        base_folder = baseline(d)
        base_csv = rows(base_folder / "solution.csv")
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
                dataset=d, label=LABELS[d], scheme=s, display=DISPLAY[s],
                first_q6_E_m=first_pt[1], first_q6_N_m=first_pt[2],
                first_q6_U_m=first_pt[3], first_q6_H_m=first_pt[4],
            )
            for wname, wpts in (("first20", w_first20), ("first60", w_first60), ("all", pts), ("tail60", w_tail60)):
                st = calc_stats(wpts)
                for k, v in st.items():
                    row[f"{wname}_{k}"] = v
            summary_rows.append(row)

            if s != "Baseline":
                max_clos, o1_info, o2_info = parse_partb_trace(folder / "solution.trace", set(q))
                verify_cases.append(dict(
                    dataset=d, scheme=s, epochs=len(data), q6=len(pts),
                    same_q_sequence=True, same_observations=True, same_corrections=True,
                    max_kv_closure_m=max_clos,
                    o1_epochs=len(o1_info),
                    o1_median_ndf=mean(x[1] for x in o1_info) if o1_info else None,
                    o1_mean_delta_df_m=mean(x[3] for x in o1_info) if o1_info else None,
                    o2_epochs=len(o2_info),
                    o2_total_inflated_rows=sum(x[1] for x in o2_info) if o2_info else 0,
                ))

    # Paired common Q6 window for 11:20 and 10:04
    for pair_name, d_a, d_b in [("11:20", "1120_xiaomi", "1120_vivo"), ("10:04", "1004_xiaomi", "1004_vivo")]:
        for s in SCHEMES:
            qa = q_series_by_ds_scheme[(d_a, s)]
            qb = q_series_by_ds_scheme[(d_b, s)]
            common_t = sorted(set(qa) & set(qb))
            pts_a = [qa[t] for t in common_t]
            pts_b = [qb[t] for t in common_t]
            sta, stb = calc_stats(pts_a), calc_stats(pts_b)
            paired_q6_rows.append(dict(
                pair=pair_name, scheme=s, common_q6=len(common_t),
                xiaomi_H_rms_m=sta["H_rms_m"], xiaomi_U_rms_m=sta["U_rms_m"],
                xiaomi_E_mean_m=sta["E_mean_m"], xiaomi_N_mean_m=sta["N_mean_m"],
                vivo_H_rms_m=stb["H_rms_m"], vivo_U_rms_m=stb["U_rms_m"],
                vivo_E_mean_m=stb["E_mean_m"], vivo_N_mean_m=stb["N_mean_m"],
            ))

    return summary_rows, paired_q6_rows, verify_cases


def md_table(headers, body):
    return "\n".join("| " + " | ".join(map(str, r)) + " |" for r in (headers, ["---"] * len(headers), *body))


def main():
    guard = build_guard()
    assert guard == read(OUT / "input_guard_sha256.json")
    check_guard(guard)

    by_ds, spp_meta, v9 = load_step9_spp()
    paired_rows, paired_summary, single_rows, single_summary = evaluate_part_a(by_ds, spp_meta, v9)
    summary_rows, paired_q6_rows, verify_cases = evaluate_part_b()

    write_csv("partA_paired_device_decomposition.csv", paired_rows)
    write_csv("partA_paired_device_summary.csv", paired_summary)
    write_csv("partA_single_dataset_iono_and_gates.csv", single_rows)
    write_csv("partA_single_dataset_summary.csv", single_summary)
    write_csv("partB_accuracy_summary.csv", summary_rows)
    write_csv("partB_paired_common_q6.csv", paired_q6_rows)

    # Generate TERMINAL_TABLES.md
    t_pa_pair = md_table(
        ["时段", "共视星数", "小米-vivo ΔE (m)", "共视测量差(Oaxaca)", "权阵差(ΔK)", "非共视星", "其中原始码贡献", "其中OSB/钟/大气贡献", "闭合差(m)"],
        [[
            r["pair"], r["common_sats"], f"{r['actual_diff_E_m']:+.3f}",
            f"{r['shapley_meas_E_m']:+.3f}", f"{r['shapley_weight_E_m']:+.3f}",
            f"{r['only_a_E_m'] + r['only_b_E_m']:+.3f}",
            f"{r['shapley_raw_rel_E_m']:+.3f}",
            f"{r['shapley_osb_rel_E_m'] + r['shapley_sclk_rel_E_m'] + r['shapley_iono_rel_E_m'] + r['shapley_trop_rel_E_m']:+.3f}",
            f"{r['closure_diff_m']:.2e}",
        ] for r in paired_summary],
    )

    t_pa_iono = md_table(
        ["数据集", "星座组", "行数", "SPP E 贡献 (m)", "广播电离层-GIM E 推力", "SaaS-VMF3 E 推力", "扣除大气模型差后剩余 E", "FDE max|res|/max_z", "STARTQC max比值"],
        [[
            LABELS[r["dataset"]], r["group"], r["rows"], f"{r['Kv_E_m']:+.3f}",
            f"{r['iono_brdc_vs_gim_E_m']:+.3f}", f"{r['trop_saas_vs_vmf3_E_m']:+.3f}",
            f"{r['residual_after_ppp_atmo_E_m']:+.3f}",
            f"{r['fde_max_abs_res_m']:.2f}m / {r['fde_max_z_lev']:.2f}",
            f"{r['startqc_max_ratio']:.3f}",
        ] for r in single_summary],
    )

    t_pb = md_table(
        ["数据集", "方案", "首Q6 E/N/U (m)", "前20 H/U RMS", "前60 H/U RMS", "全段 H/U RMS", "末60s E/N/U 均值", "末60s H/U RMS"],
        [[
            r["label"], r["display"],
            f"{r['first_q6_E_m']:+.3f}/{r['first_q6_N_m']:+.3f}/{r['first_q6_U_m']:+.3f}",
            f"{r['first20_H_rms_m']:.3f}/{r['first20_U_rms_m']:.3f}",
            f"{r['first60_H_rms_m']:.3f}/{r['first60_U_rms_m']:.3f}",
            f"{r['all_H_rms_m']:.3f}/{r['all_U_rms_m']:.3f}",
            f"{r['tail60_E_mean_m']:+.3f}/{r['tail60_N_mean_m']:+.3f}/{r['tail60_U_mean_m']:+.3f}",
            f"{r['tail60_H_rms_m']:.3f}/{r['tail60_U_rms_m']:.3f}",
        ] for r in summary_rows],
    )

    t_pb_pair = md_table(
        ["时段", "方案", "共有 Q6", "小米 H/U RMS (m)", "小米 E/N 均值 (m)", "vivo H/U RMS (m)", "vivo E/N 均值 (m)"],
        [[
            r["pair"], DISPLAY[r["scheme"]], r["common_q6"],
            f"{r['xiaomi_H_rms_m']:.3f}/{r['xiaomi_U_rms_m']:.3f}",
            f"{r['xiaomi_E_mean_m']:+.3f}/{r['xiaomi_N_mean_m']:+.3f}",
            f"{r['vivo_H_rms_m']:.3f}/{r['vivo_U_rms_m']:.3f}",
            f"{r['vivo_E_mean_m']:+.3f}/{r['vivo_N_mean_m']:+.3f}",
        ] for r in paired_q6_rows],
    )

    terminal_md = (
        "# Step 10 终端汇总\n\n"
        "## Part A1 · 双机同秒共视星启动东向差物理分解\n\n" + t_pa_pair + "\n\n"
        "## Part A2 · SPP 广播大气 vs PPP GIM/VMF3 推力与启动门限\n\n" + t_pa_iono + "\n\n"
        "## Part B1 · 泛在手机非组合提精消融全指标（m）\n\n" + t_pb + "\n\n"
        "## Part B2 · 11:20 与 10:04 双机共有 Q6 配对精度（m）\n\n" + t_pb_pair + "\n"
    )
    (OUT / "TERMINAL_TABLES.md").write_text(terminal_md, encoding="utf-8")

    # Verification JSON
    out_csvs = (
        "partA_paired_device_decomposition.csv",
        "partA_paired_device_summary.csv",
        "partA_single_dataset_iono_and_gates.csv",
        "partA_single_dataset_summary.csv",
        "partB_accuracy_summary.csv",
        "partB_paired_common_q6.csv",
    )
    verification = dict(
        guard_files=len(guard),
        new_replays=len(verify_cases),
        baseline_reused=len(DATASETS),
        all_same_q_sequence=all(c["same_q_sequence"] for c in verify_cases),
        all_same_observations=all(c["same_observations"] for c in verify_cases),
        all_same_corrections=all(c["same_corrections"] for c in verify_cases),
        max_kv_closure_m=max(c["max_kv_closure_m"] for c in verify_cases),
        max_partA_decomp_closure_m=max(r["max_decomp_err_m"] for r in single_summary),
        max_partA_paired_closure_m=max(r["closure_diff_m"] for r in paired_summary),
        used_if=False,
        used_ar=False,
        reference_used_only_after_replay=True,
        no_production_changes=True,
        cases=verify_cases,
        sha256={
            **{n: sha(OUT / n) for n in (*out_csvs, "step10_probe.exe", "step10_private.patch", "step10_mods.inc")},
        },
    )
    save(OUT / "verification.json", verification)
    print(terminal_md)
    print("Verification max_kv_closure_m:", verification["max_kv_closure_m"])
    print("Verification max_partA_decomp_closure_m:", verification["max_partA_decomp_closure_m"])
    print("Verification max_partA_paired_closure_m:", verification["max_partA_paired_closure_m"])


if __name__ == "__main__":
    main()
