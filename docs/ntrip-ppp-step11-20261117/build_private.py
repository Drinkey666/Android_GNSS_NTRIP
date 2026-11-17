from pathlib import Path
import difflib
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CORE = ROOT / "core"
SRC = ROOT / "src"


def rewrite(folder: Path, name: str, rel_prefix: str, pairs):
    source = (folder / name).read_text(encoding="utf-8-sig")
    result = source
    for old, new in pairs:
        count = result.count(old)
        assert count == 1, (name, old[:80], count)
        result = result.replace(old, new)
    (OUT / f"private_{name}").write_text(result, encoding="utf-8")
    return "".join(
        difflib.unified_diff(
            source.splitlines(True),
            result.splitlines(True),
            fromfile=f"a/{rel_prefix}/{name}",
            tofile=f"b/{rel_prefix}/{name}",
        )
    )


patch = rewrite(
    CORE,
    "ppp.c",
    "core",
    [
        (
            "static int ionex_vertical_prior(gtime_t time, const nav_t* nav,\n"
            "    const double* pos, const double* azel, const prcopt_t* opt,\n"
            "    double* ion_v, double* var_v)\n"
            "{\n"
            "    double ion_s = 0.0, var_s = 0.0, mapf, sig;\n\n"
            "    if (!nav || !pos || !azel || azel[1] <= 0.0) return 0;\n"
            "    if ((mapf = ppp_iono_mapf(nav, pos, azel)) <= 0.0) return 0;\n"
            "    if (!iontec(time, nav, pos, azel, 1, &ion_s, &var_s)) return 0;\n\n"
            "    *ion_v = ion_s / mapf;\n"
            "    *var_v = var_s > 0.0 ? var_s / SQR(mapf) : 0.0;\n\n"
            "    sig = ion_constraint_sigma(opt);\n"
            "    if (*var_v < SQR(sig)) *var_v = SQR(sig);\n\n"
            "    if (!isfinite(*ion_v) || !isfinite(*var_v) || fabs(*ion_v) > 1E4 || *var_v <= 0.0) {\n"
            "        return 0;\n"
            "    }\n"
            "    return 1;\n"
            "}",
            "static int ionex_vertical_prior_floor(gtime_t time, const nav_t* nav,\n"
            "    const double* pos, const double* azel, const prcopt_t* opt,\n"
            "    double sig, double* ion_v, double* var_v)\n"
            "{\n"
            "    double ion_s = 0.0, var_s = 0.0, mapf;\n\n"
            "    if (!nav || !pos || !azel || azel[1] <= 0.0) return 0;\n"
            "    if ((mapf = ppp_iono_mapf(nav, pos, azel)) <= 0.0) return 0;\n"
            "    if (!iontec(time, nav, pos, azel, 1, &ion_s, &var_s)) return 0;\n\n"
            "    *ion_v = ion_s / mapf;\n"
            "    *var_v = var_s > 0.0 ? var_s / SQR(mapf) : 0.0;\n\n"
            "    if (*var_v < SQR(sig)) *var_v = SQR(sig);\n\n"
            "    if (!isfinite(*ion_v) || !isfinite(*var_v) || fabs(*ion_v) > 1E4 || *var_v <= 0.0) {\n"
            "        return 0;\n"
            "    }\n"
            "    return 1;\n"
            "}\n"
            "static int ionex_vertical_prior(gtime_t time, const nav_t* nav,\n"
            "    const double* pos, const double* azel, const prcopt_t* opt,\n"
            "    double* ion_v, double* var_v)\n"
            "{\n"
            "    return ionex_vertical_prior_floor(time, nav, pos, azel, opt,\n"
            "        ion_constraint_sigma(opt), ion_v, var_v);\n"
            "}\n"
            "#include \"step11_mods.inc\"",
        ),
        (
            "    ecef2pos(rtk->sol.rr, pos);\n\n    for (i = 0; i < n && i < MAXOBS; i++) {",
            "    ecef2pos(rtk->sol.rr, pos);\n"
            "    int s11_o1_on = s11_use_o1_robust(s11_scheme());\n"
            "    double s11_ud_delta = 0.0;\n"
            "    int s11_ud_ndf = 0;\n"
            "    if (s11_o1_on) {\n"
            "        s11_ud_delta = s11_df_iono_delta(rtk, obs, n, nav, rtk->x, pos, NULL, NULL, &s11_ud_ndf);\n"
            "    }\n\n"
            "    for (i = 0; i < n && i < MAXOBS; i++) {",
        ),
        (
            "            if ((smartphone_ppp_policy(&rtk->opt).atmosphere_constraints ||\n"
            "                rtk->opt.ppp_physical_atmosphere) &&\n"
            "                ionex_vertical_prior(obs[i].time, nav, pos, azel, &rtk->opt, &ion, &vari)) {\n"
            "                if (!rtk->opt.ppp_physical_atmosphere && fabs(ion) < 1E-8)\n"
            "                    ion = 1E-6; /* legacy active-state sentinel */",
            "            int s11_sf = s11_o1_on && s11_sat_freq_count(rtk, obs + i, nav) == 1;\n"
            "            double s11_sig = s11_sf ? 0.90 : ion_constraint_sigma(&rtk->opt);\n"
            "            if ((smartphone_ppp_policy(&rtk->opt).atmosphere_constraints ||\n"
            "                rtk->opt.ppp_physical_atmosphere) &&\n"
            "                ionex_vertical_prior_floor(obs[i].time, nav, pos, azel, &rtk->opt, s11_sig, &ion, &vari)) {\n"
            "                if (s11_sf) ion += s11_ud_delta;\n"
            "                if (!rtk->opt.ppp_physical_atmosphere && fabs(ion) < 1E-8)\n"
            "                    ion = 1E-6; /* legacy active-state sentinel */",
        ),
        (
            "            sinel = sin(MAX(azel[1], 5.0 * D2R));\n"
            "            rtk->P[j + j * rtk->nx] += SQR(rtk->opt.prn[1] / sinel) *",
            "            sinel = sin(MAX(azel[1], 5.0 * D2R));\n"
            "            int s11_sf = s11_o1_on && s11_sat_freq_count(rtk, obs + i, nav) == 1;\n"
            "            double s11_prn = s11_sf ? 0.7 * rtk->opt.prn[1] : rtk->opt.prn[1];\n"
            "            rtk->P[j + j * rtk->nx] += SQR(s11_prn / sinel) *",
        ),
        (
            "    int ionex_constraints = 0, vmf3_zwd_constraints = 0;",
            "    int ionex_constraints = 0, vmf3_zwd_constraints = 0;\n"
            "    int s11_sc = s11_scheme(), s11_cmd_inflated = 0, s11_cmd_rows = 0;\n"
            "    double s11_cmd_max_f = 1.0, s11_cmd_sum_f = 0.0;",
        ),
        (
            "            if (diag && frq < NFREQ)\n"
            "                diag->obs[i][frq].physical_sigma[code]=sigma0;\n"
            "            /* Never claim the white-noise variance reduction as independent",
            "            if (diag && frq < NFREQ)\n"
            "                diag->obs[i][frq].physical_sigma[code]=sigma0;\n"
            "            if (code == 1 && s11_use_cmd(s11_sc) && frq < NFREQ &&\n"
            "                s11_cmd_count[sat - 1][frq] >= 4) {\n"
            "                double denom = MAX(base_obs_var, 1.0);\n"
            "                double f_cmd = 0.5 * s11_cmd_var_ema[sat - 1][frq] / denom;\n"
            "                if (!isfinite(f_cmd) || f_cmd < 1.0) f_cmd = 1.0;\n"
            "                if (f_cmd > 16.0) f_cmd = 16.0;\n"
            "                if (!post) {\n"
            "                    s11_cmd_rows++;\n"
            "                    s11_cmd_sum_f += f_cmd;\n"
            "                    if (f_cmd > 1.0 + 1E-12) s11_cmd_inflated++;\n"
            "                    if (f_cmd > s11_cmd_max_f) s11_cmd_max_f = f_cmd;\n"
            "                }\n"
            "                if (f_cmd > 1.0) {\n"
            "                    double code_base = base_obs_var * signal_weight_ppp(sys, obs[i].code[frq], code, opt);\n"
            "                    if (sys == SYS_CMP) code_base *= bds_code_factor;\n"
            "                    if (!sat_has_phase && !rtk->ppp_code_warmup) code_base *= code_only_factor;\n"
            "                    var[nv] += (f_cmd - 1.0) * code_base;\n"
            "                }\n"
            "            }\n"
            "            /* Never claim the white-noise variance reduction as independent",
        ),
        (
            "    if ((smartphone_ppp_policy(opt).atmosphere_constraints || opt->ppp_physical_atmosphere) &&\n"
            "        !post && opt->ionoopt == IONOOPT_EST && v && H) {\n"
            "        unsigned char used[MAXSAT] = { 0 };\n"
            "        int logged_interval = 0;",
            "    if ((smartphone_ppp_policy(opt).atmosphere_constraints || opt->ppp_physical_atmosphere) &&\n"
            "        !post && opt->ionoopt == IONOOPT_EST && v && H) {\n"
            "        unsigned char used[MAXSAT] = { 0 };\n"
            "        int logged_interval = 0;\n"
            "        double s11_res_delta = 0.0;\n"
            "        int s11_res_ndf = 0, s11_res_nsf = 0;\n"
            "        if (s11_use_o1_robust(s11_sc)) {\n"
            "            s11_res_delta = s11_df_iono_delta(rtk, obs, n, nav, x, pos, azel, exc, &s11_res_ndf);\n"
            "        }",
        ),
        (
            "            if (!ionex_vertical_prior(obs[i].time, nav, pos, azel + i * 2,\n"
            "                opt, &ion_prior, &var_prior)) {\n"
            "                continue;\n"
            "            }",
            "            int s11_sf = s11_use_o1_robust(s11_sc) && s11_sat_freq_count(rtk, obs + i, nav) == 1;\n"
            "            double s11_sig = s11_sf ? 0.90 : ion_constraint_sigma(opt);\n"
            "            if (s11_sf) s11_res_nsf++;\n"
            "            if (!ionex_vertical_prior_floor(obs[i].time, nav, pos, azel + i * 2,\n"
            "                opt, s11_sig, &ion_prior, &var_prior)) {\n"
            "                continue;\n"
            "            }\n"
            "            if (s11_sf) ion_prior += s11_res_delta;",
        ),
        (
            "    if (!post && product_use) {\n"
            "        product_use[0] = ionex_constraints;\n"
            "        product_use[1] = vmf3_zwd_constraints;\n"
            "    }",
            "    if (!post && product_use) {\n"
            "        product_use[0] = ionex_constraints;\n"
            "        product_use[1] = vmf3_zwd_constraints;\n"
            "    }\n"
            "    if (!post) {\n"
            "        s11_last_cmd_inflated = s11_cmd_inflated;\n"
            "        s11_last_cmd_rows = s11_cmd_rows;\n"
            "        s11_last_cmd_max_f = s11_cmd_max_f;\n"
            "        s11_last_cmd_sum_f = s11_cmd_sum_f;\n"
            "        if (s11_use_o1_robust(s11_sc) && v && H) {\n"
            "            int s11_idx;\n"
            "            s11_last_delta_df = 0.0; s11_last_ndf = 0; s11_last_nsf = 0;\n"
            "            for (s11_idx = 0; s11_idx < n && s11_idx < MAXOBS; s11_idx++) {\n"
            "                if (!exc[s11_idx] && azel[1 + s11_idx * 2] >= opt->elmin && s11_sat_freq_count(rtk, obs + s11_idx, nav) == 1) {\n"
            "                    int s11_ii = II(obs[s11_idx].sat, opt);\n"
            "                    if (s11_ii >= 0 && s11_ii < nx && x[s11_ii] != 0.0) s11_last_nsf++;\n"
            "                }\n"
            "            }\n"
            "            s11_last_delta_df = s11_df_iono_delta(rtk, obs, n, nav, x, pos, azel, exc, &s11_last_ndf);\n"
            "        } else {\n"
            "            s11_last_delta_df = 0.0; s11_last_ndf = 0; s11_last_nsf = 0;\n"
            "        }\n"
            "    }",
        ),
        (
            "    ppp_diag_epoch_t diag, evidence;",
            "    ppp_diag_epoch_t diag, evidence;\n"
            "    const int step11_mode = s11_scheme();\n"
            "    double s11_before[3];",
        ),
        (
            "    /* 第 6 步：按开关处理地影和潮汐。",
            "    if (step11_mode < 0 || opt->ionoopt != IONOOPT_EST || opt->modear != ARMODE_OFF ||\n"
            "        !ppp_verified_joseph(opt) || opt->ppp_iekf) {\n"
            "        trace(2, \"$S11_INVALID_PROFILE\\n\");\n"
            "        rtk->ppp_failure = FILTER_BAD_DIM;\n"
            "        goto cleanup;\n"
            "    }\n"
            "    /* 第 6 步：按开关处理地影和潮汐。",
        ),
        (
            "    phase_osb_arcs_ppp(rtk,obs,n,nav);\n"
            "    /* 第 3 步：平滑及可选码阶段选择，各执行一次；严禁移进残差编辑循环，",
            "    s11_cmd_update(rtk, obs, n, nav);\n"
            "    phase_osb_arcs_ppp(rtk,obs,n,nav);\n"
            "    /* 第 3 步：平滑及可选码阶段选择，各执行一次；严禁移进残差编辑循环，",
        ),
        (
            "        else info=opt->ppp_physical_atmosphere?filter_physical(xp,Pp,H,v,R,rtk->nx,nv):\n"
            "            (opt->ppp_wet_correction || opt->ppp_rcb_datum)?filter_active(xp,Pp,H,v,R,rtk->nx,nv):\n"
            "            ppp_verified_joseph(opt)?filter_verified(xp,Pp,H,v,R,rtk->nx,nv):\n"
            "            filter(xp,Pp,H,v,R,rtk->nx,nv);",
            "        memcpy(s11_before, xp, sizeof(s11_before));\n"
            "        s11_gain_count = nv;\n"
            "        if (0) {}\n"
            "        else info=opt->ppp_physical_atmosphere?filter_physical(xp,Pp,H,v,R,rtk->nx,nv):\n"
            "            (opt->ppp_wet_correction || opt->ppp_rcb_datum)?filter_active(xp,Pp,H,v,R,rtk->nx,nv):\n"
            "            ppp_verified_joseph(opt)?filter_verified(xp,Pp,H,v,R,rtk->nx,nv):\n"
            "            filter(xp,Pp,H,v,R,rtk->nx,nv);\n"
            "        s11_gain_count = 0;",
        ),
        (
            "        update_stat(rtk, obs, n, stat);",
            "        update_stat(rtk, obs, n, stat);\n"
            "        if (rtk->sol.stat == SOLQ_PPP) s11_report(rtk, obs, nv, s11_before);",
        ),
    ],
)

patch += rewrite(
    CORE,
    "rtkcmn.c",
    "core",
    [
        (
            "static int filter_(const double *x,",
            "extern void s11_active_indices(const int *ix, int n);\n"
            "extern void s11_capture_gain(const double *K, const double *v, int n, int m);\n"
            "static int filter_(const double *x,",
        ),
        (
            "        matmul(\"NN\",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */",
            "        matmul(\"NN\",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */\n"
            "        s11_capture_gain(K, v, n, m);",
        ),
        (
            "    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);",
            "    s11_active_indices(ix, k);\n"
            "    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);",
        ),
    ],
)

patch += rewrite(
    SRC,
    "gnss_replay.c",
    "src",
    [
        (
            "#include \"pc_ssr_replay.h\"",
            "#include \"pc_ssr_replay.h\"\n"
            "extern void ppp_presmooth_wait(rtk_t *rtk, const obsd_t *obs, int n, const nav_t *nav);",
        ),
        (
            "        if(ready<4) {\n"
            "            /* No fake solution and no mutation of the last trusted filter state. */\n"
            "            tow=time2gpst(source_epoch,&week);",
            "        if(ready<4) {\n"
            "            /* No fake solution and no mutation of the last trusted filter state. */\n"
            "            ppp_presmooth_wait(rtk,obs,nobs,nav);\n"
            "            tow=time2gpst(source_epoch,&week);",
        ),
    ],
)

(OUT / "step11_private.patch").write_text(patch, encoding="utf-8")

script = (ROOT / "build/build.cmd").read_text(encoding="utf-8-sig").splitlines()
lines = script[:2]
link = next(l for l in script if l.startswith("link ") and "ppp_ssr_replay.exe" in l)
for folder, source in ((CORE, "ppp"), (CORE, "rtkcmn"), (SRC, "gnss_replay")):
    c = str(folder / f"{source}.c")
    obj = str(ROOT / "build" / f"{source}.obj")
    new = str(OUT / f"private_{source}.obj")
    line = next(l for l in script if l.startswith("cl ") and f'"{c}"' in l)
    lines.extend([
        line.replace(c, str(OUT / f"private_{source}.c")).replace(obj, new) + f' /I"{OUT}"',
        "if errorlevel 1 exit /b 1",
    ])
    link = link.replace(obj, new)
lines.append(link.replace(str(ROOT / "bin/ppp_ssr_replay.exe"), str(OUT / "step11_probe.exe")))
cmd = OUT / "build_private.cmd"
cmd.write_text("\n".join(lines) + "\n", encoding="utf-8")
with (OUT / "build_private.log").open("wb") as log:
    subprocess.run(["cmd", "/c", str(cmd)], cwd=OUT, stdout=log, stderr=subprocess.STDOUT, check=True)
print("Built step11_probe.exe successfully.")
