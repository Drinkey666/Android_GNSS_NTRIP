from pathlib import Path
import difflib, subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
CORE = ROOT / "core"

def rewrite(name, pairs):
    source = (CORE / name).read_text(encoding="utf-8-sig")
    result = source
    for old, new in pairs:
        count = result.count(old)
        assert count == 1, (name, old[:80], count)
        result = result.replace(old, new)
    (OUT / f"private_{name}").write_text(result, encoding="utf-8")
    return "".join(difflib.unified_diff(
        source.splitlines(True), result.splitlines(True),
        fromfile=f"a/core/{name}", tofile=f"b/core/{name}"
    ))

patch = rewrite("ppp.c", [
    (
        "static inline void initx(rtk_t* rtk, double xi, double var, int i)",
        "static int s10_arc_lock[MAXSAT][NFREQ] = {{0}};\n"
        "static void s10_parta_startqc_group(gtime_t t, int grp, int code, int refcode,\n"
        "    int peers, double centre, double mad, double gate, double pos_gate,\n"
        "    int sat, int f, double residual);\n"
        "static inline void initx(rtk_t* rtk, double xi, double var, int i)"
    ),
    (
        "    ss->ppp_arc_pending[f]=ss->ppp_arc_reset[f]=1;\n    ss->psmvalid[f]=0;",
        "    ss->ppp_arc_pending[f]=ss->ppp_arc_reset[f]=1;\n    ss->psmvalid[f]=0;\n    s10_arc_lock[sat-1][f]=0;"
    ),
    (
        "            rtk->P[i + j * rtk->nx] = 0.0;\n            rtk->P[j + i * rtk->nx] = 0.0;\n        }\n    }\n}",
        "            rtk->P[i + j * rtk->nx] = 0.0;\n            rtk->P[j + i * rtk->nx] = 0.0;\n        }\n        s10_arc_lock[sat - 1][f] = 0;\n    }\n}"
    ),
    (
        "                ss->slip[f] = 0;\n                ss->psmvalid[f] = 0;",
        "                ss->slip[f] = 0;\n                ss->psmvalid[f] = 0;\n                s10_arc_lock[sat - 1][f] = 0;"
    ),
    (
        "static int ionex_vertical_prior(gtime_t time, const nav_t* nav,\n"
        "    const double* pos, const double* azel, const prcopt_t* opt,\n"
        "    double* ion_v, double* var_v)\n"
        "{\n"
        "    double ion_s = 0.0, var_s = 0.0, mapf, sig;\n"
        "\n"
        "    if (!nav || !pos || !azel || azel[1] <= 0.0) return 0;\n"
        "    if ((mapf = ppp_iono_mapf(nav, pos, azel)) <= 0.0) return 0;\n"
        "    if (!iontec(time, nav, pos, azel, 1, &ion_s, &var_s)) return 0;\n"
        "\n"
        "    *ion_v = ion_s / mapf;\n"
        "    *var_v = var_s > 0.0 ? var_s / SQR(mapf) : 0.0;\n"
        "\n"
        "    sig = ion_constraint_sigma(opt);\n"
        "    if (*var_v < SQR(sig)) *var_v = SQR(sig);\n"
        "\n"
        "    if (!isfinite(*ion_v) || !isfinite(*var_v) || fabs(*ion_v) > 1E4 || *var_v <= 0.0) {\n"
        "        return 0;\n"
        "    }\n"
        "    return 1;\n"
        "}",
        "static int ionex_vertical_prior_floor(gtime_t time, const nav_t* nav,\n"
        "    const double* pos, const double* azel, const prcopt_t* opt,\n"
        "    double sig, double* ion_v, double* var_v)\n"
        "{\n"
        "    double ion_s = 0.0, var_s = 0.0, mapf;\n"
        "\n"
        "    if (!nav || !pos || !azel || azel[1] <= 0.0) return 0;\n"
        "    if ((mapf = ppp_iono_mapf(nav, pos, azel)) <= 0.0) return 0;\n"
        "    if (!iontec(time, nav, pos, azel, 1, &ion_s, &var_s)) return 0;\n"
        "\n"
        "    *ion_v = ion_s / mapf;\n"
        "    *var_v = var_s > 0.0 ? var_s / SQR(mapf) : 0.0;\n"
        "\n"
        "    if (*var_v < SQR(sig)) *var_v = SQR(sig);\n"
        "\n"
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
        "#include \"step10_mods.inc\""
    ),
    (
        "        gate=MAX(30.0,MAX(6.0*mad,refcode[i]?0.0:position_gate));\n"
        "        for(j=0;j<count;j++)if(group[j]==group[i]&&code[j]==code[i]&&refcode[j]==refcode[i]&&fabs(residual[j]-centre)>gate) {",
        "        gate=MAX(30.0,MAX(6.0*mad,refcode[i]?0.0:position_gate));\n"
        "        if(!rtk->ppp_clock_valid) {\n"
        "            for(j=0;j<count;j++)if(group[j]==group[i]&&code[j]==code[i]&&refcode[j]==refcode[i]) {\n"
        "                s10_parta_startqc_group(obs[oi[j]].time, group[j], code[j], refcode[j],\n"
        "                    q, centre, mad, gate, position_gate, obs[oi[j]].sat, of[j], residual[j]);\n"
        "            }\n"
        "        }\n"
        "        for(j=0;j<count;j++)if(group[j]==group[i]&&code[j]==code[i]&&refcode[j]==refcode[i]&&fabs(residual[j]-centre)>gate) {"
    ),
    (
        "    ecef2pos(rtk->sol.rr, pos);\n\n    for (i = 0; i < n && i < MAXOBS; i++) {",
        "    ecef2pos(rtk->sol.rr, pos);\n"
        "    int s10_o1_on = s10_use_o1(s10_scheme());\n"
        "    double s10_ud_delta = 0.0;\n"
        "    int s10_ud_ndf = 0;\n"
        "    if (s10_o1_on) {\n"
        "        s10_ud_delta = s10_df_iono_delta(rtk, obs, n, nav, rtk->x, pos, NULL, NULL, &s10_ud_ndf);\n"
        "    }\n\n"
        "    for (i = 0; i < n && i < MAXOBS; i++) {"
    ),
    (
        "            if ((smartphone_ppp_policy(&rtk->opt).atmosphere_constraints ||\n"
        "                rtk->opt.ppp_physical_atmosphere) &&\n"
        "                ionex_vertical_prior(obs[i].time, nav, pos, azel, &rtk->opt, &ion, &vari)) {\n"
        "                if (!rtk->opt.ppp_physical_atmosphere && fabs(ion) < 1E-8)\n"
        "                    ion = 1E-6; /* legacy active-state sentinel */",
        "            int s10_sf = s10_o1_on && s10_sat_freq_count(rtk, obs + i, nav) == 1;\n"
        "            double s10_sig = s10_sf ? 0.60 : ion_constraint_sigma(&rtk->opt);\n"
        "            if ((smartphone_ppp_policy(&rtk->opt).atmosphere_constraints ||\n"
        "                rtk->opt.ppp_physical_atmosphere) &&\n"
        "                ionex_vertical_prior_floor(obs[i].time, nav, pos, azel, &rtk->opt, s10_sig, &ion, &vari)) {\n"
        "                if (s10_sf) ion += s10_ud_delta;\n"
        "                if (!rtk->opt.ppp_physical_atmosphere && fabs(ion) < 1E-8)\n"
        "                    ion = 1E-6; /* legacy active-state sentinel */"
    ),
    (
        "            sinel = sin(MAX(azel[1], 5.0 * D2R));\n"
        "            rtk->P[j + j * rtk->nx] += SQR(rtk->opt.prn[1] / sinel) *",
        "            sinel = sin(MAX(azel[1], 5.0 * D2R));\n"
        "            int s10_sf = s10_o1_on && s10_sat_freq_count(rtk, obs + i, nav) == 1;\n"
        "            double s10_prn = s10_sf ? 0.5 * rtk->opt.prn[1] : rtk->opt.prn[1];\n"
        "            rtk->P[j + j * rtk->nx] += SQR(s10_prn / sinel) *"
    ),
    (
        "                    if (smartphone_ppp_policy(&rtk->opt).corrected_lifecycle &&\n"
        "                        rtk->x[j]!=0.0)\n"
        "                        invalidate_arc_ppp(rtk,i+1,f,clk_jump?\"CLOCKJUMP\":reset_inst?\"INSTANT_AR\":\"OUTAGE\");\n"
        "                    else initx(rtk,0.0,0.0,j);",
        "                    if (smartphone_ppp_policy(&rtk->opt).corrected_lifecycle &&\n"
        "                        rtk->x[j]!=0.0)\n"
        "                        invalidate_arc_ppp(rtk,i+1,f,clk_jump?\"CLOCKJUMP\":reset_inst?\"INSTANT_AR\":\"OUTAGE\");\n"
        "                    else { initx(rtk,0.0,0.0,j); s10_arc_lock[i][f] = 0; }"
    ),
    (
        "                initx(rtk, bias[i], VAR_BIAS, j);\n"
        "                ppp_innovation_note_current_init(j,sat,f,1);",
        "                initx(rtk, bias[i], VAR_BIAS, j);\n"
        "                s10_arc_lock[sat - 1][f] = 0;\n"
        "                ppp_innovation_note_current_init(j,sat,f,1);"
    ),
    (
        "    int ionex_constraints = 0, vmf3_zwd_constraints = 0;",
        "    int ionex_constraints = 0, vmf3_zwd_constraints = 0;\n"
        "    int s10_sc = s10_scheme(), s10_o2_inflated = 0;\n"
        "    double s10_o2_max_f = 1.0;"
    ),
    (
        "            if (diag && frq < NFREQ)\n"
        "                diag->obs[i][frq].physical_sigma[code]=sigma0;\n"
        "            /* Never claim the white-noise variance reduction as independent",
        "            if (diag && frq < NFREQ)\n"
        "                diag->obs[i][frq].physical_sigma[code]=sigma0;\n"
        "            if (!post && code == 1 && !rtk->ppp_clock_valid) {\n"
        "                double ion_gim_v = 0.0, ion_gim_var = 0.0, mp = ppp_iono_mapf(nav, pos, azel + i * 2);\n"
        "                if (!ionex_vertical_prior(obs[i].time, nav, pos, azel + i * 2, opt, &ion_gim_v, &ion_gim_var)) {\n"
        "                    ion_gim_v = NAN; ion_gim_var = NAN;\n"
        "                }\n"
        "                s10_parta_ppp_row(obs[i].time, sat, frq, obs[i].code[frq],\n"
        "                    P[frq], r, -CLIGHT * dts[i * 2], dtrp, dion, C,\n"
        "                    ion_gim_v, mp, ion_gim_var, base_obs_var, vart, SQR(C) * vari, var_rs[i],\n"
        "                    sigma0, res, azel[i * 2] * R2D, azel[1 + i * 2] * R2D);\n"
        "            }\n"
        "            if (code == 1 && s10_use_o2(s10_sc) && frq < NFREQ) {\n"
        "                const ssat_t *s10_ss = rtk->ssat + sat - 1;\n"
        "                int phase_mexc = (mexc && (i * 2 * NFREQ + 2 * frq) >= 0 &&\n"
        "                    (i * 2 * NFREQ + 2 * frq) < MAXOBS * 2 * NFREQ &&\n"
        "                    mexc[i * 2 * NFREQ + 2 * frq]);\n"
        "                int phase_quar = smartphone_ppp_policy(opt).quality_learning &&\n"
        "                    ppp_phase_quarantined(s10_ss, frq, obs[i].time);\n"
        "                int b_idx = IB(sat, frq, opt);\n"
        "                int arc_lock = s10_arc_lock[sat - 1][frq];\n"
        "                if (L[frq] != 0.0 && !phase_mexc && !rtk->ppp_code_warmup && !phase_quar &&\n"
        "                    b_idx >= 0 && b_idx < nx && x[b_idx] != 0.0 &&\n"
        "                    !s10_ss->ppp_arc_reset[frq] && !(obs[i].LLI[frq] & LLI_SLIP) &&\n"
        "                    !(s10_ss->slip[frq] & LLI_SLIP) && doppsm_factor(opt) > 0.0 &&\n"
        "                    s10_ss->psmvalid[frq] && arc_lock >= 1) {\n"
        "                    double f_info = MIN(6.0, 1.0 + 5.0 * MIN(1.0, (double)arc_lock / 10.0));\n"
        "                    double code_base = base_obs_var * signal_weight_ppp(sys, obs[i].code[frq], code, opt);\n"
        "                    if (sys == SYS_CMP) code_base *= bds_code_factor;\n"
        "                    if (!sat_has_phase && !rtk->ppp_code_warmup) code_base *= code_only_factor;\n"
        "                    var[nv] += (f_info - 1.0) * code_base;\n"
        "                    s10_o2_inflated++;\n"
        "                    if (f_info > s10_o2_max_f) s10_o2_max_f = f_info;\n"
        "                }\n"
        "            }\n"
        "            /* Never claim the white-noise variance reduction as independent"
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
        "        double s10_res_delta = 0.0;\n"
        "        int s10_res_ndf = 0, s10_res_nsf = 0;\n"
        "        if (s10_use_o1(s10_sc)) {\n"
        "            s10_res_delta = s10_df_iono_delta(rtk, obs, n, nav, x, pos, azel, exc, &s10_res_ndf);\n"
        "        }"
    ),
    (
        "            if (!ionex_vertical_prior(obs[i].time, nav, pos, azel + i * 2,\n"
        "                opt, &ion_prior, &var_prior)) {\n"
        "                continue;\n"
        "            }",
        "            int s10_sf = s10_use_o1(s10_sc) && s10_sat_freq_count(rtk, obs + i, nav) == 1;\n"
        "            double s10_sig = s10_sf ? 0.60 : ion_constraint_sigma(opt);\n"
        "            if (s10_sf) s10_res_nsf++;\n"
        "            if (!ionex_vertical_prior_floor(obs[i].time, nav, pos, azel + i * 2,\n"
        "                opt, s10_sig, &ion_prior, &var_prior)) {\n"
        "                continue;\n"
        "            }\n"
        "            if (s10_sf) ion_prior += s10_res_delta;"
    ),
    (
        "            if (!opt->ppp_physical_atmosphere && zc > ION_CONSTR_ROBUST) {",
        "            if (!opt->ppp_physical_atmosphere && !s10_sf && zc > ION_CONSTR_ROBUST) {"
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
        "        s10_last_o2_inflated = s10_o2_inflated;\n"
        "        s10_last_o2_max_f = s10_o2_max_f;\n"
        "        if (s10_use_o1(s10_sc) && v && H) {\n"
        "            int s10_idx;\n"
        "            s10_last_delta_df = 0.0; s10_last_ndf = 0; s10_last_nsf = 0;\n"
        "            for (s10_idx = 0; s10_idx < n && s10_idx < MAXOBS; s10_idx++) {\n"
        "                if (!exc[s10_idx] && azel[1 + s10_idx * 2] >= opt->elmin && s10_sat_freq_count(rtk, obs + s10_idx, nav) == 1) {\n"
        "                    int s10_ii = II(obs[s10_idx].sat, opt);\n"
        "                    if (s10_ii >= 0 && s10_ii < nx && x[s10_ii] != 0.0) s10_last_nsf++;\n"
        "                }\n"
        "            }\n"
        "            s10_last_delta_df = s10_df_iono_delta(rtk, obs, n, nav, x, pos, azel, exc, &s10_last_ndf);\n"
        "        }\n"
        "    }"
    ),
    (
        "            rtk->ssat[obs[i].sat - 1].lock[j]++;\n"
        "            rtk->ssat[obs[i].sat - 1].outc[j] = 0;",
        "            rtk->ssat[obs[i].sat - 1].lock[j]++;\n"
        "            if (j < NFREQ) s10_arc_lock[obs[i].sat - 1][j]++;\n"
        "            rtk->ssat[obs[i].sat - 1].outc[j] = 0;"
    ),
    (
        "    ppp_diag_epoch_t diag, evidence;",
        "    ppp_diag_epoch_t diag, evidence;\n"
        "    const int step10_mode = s10_scheme();\n"
        "    double s10_before[3];"
    ),
    (
        "    /* 第 6 步：按开关处理地影和潮汐。",
        "    if (step10_mode < 0 || opt->ionoopt != IONOOPT_EST || opt->modear != ARMODE_OFF ||\n"
        "        !ppp_verified_joseph(opt) || opt->ppp_iekf) {\n"
        "        trace(2, \"$S10_INVALID_PROFILE\\n\");\n"
        "        rtk->ppp_failure = FILTER_BAD_DIM;\n"
        "        goto cleanup;\n"
        "    }\n"
        "    /* 第 6 步：按开关处理地影和潮汐。"
    ),
    (
        "        else info=opt->ppp_physical_atmosphere?filter_physical(xp,Pp,H,v,R,rtk->nx,nv):\n"
        "            (opt->ppp_wet_correction || opt->ppp_rcb_datum)?filter_active(xp,Pp,H,v,R,rtk->nx,nv):\n"
        "            ppp_verified_joseph(opt)?filter_verified(xp,Pp,H,v,R,rtk->nx,nv):\n"
        "            filter(xp,Pp,H,v,R,rtk->nx,nv);",
        "        memcpy(s10_before, xp, sizeof(s10_before));\n"
        "        s10_gain_count = nv;\n"
        "        if (0) {}\n"
        "        else info=opt->ppp_physical_atmosphere?filter_physical(xp,Pp,H,v,R,rtk->nx,nv):\n"
        "            (opt->ppp_wet_correction || opt->ppp_rcb_datum)?filter_active(xp,Pp,H,v,R,rtk->nx,nv):\n"
        "            ppp_verified_joseph(opt)?filter_verified(xp,Pp,H,v,R,rtk->nx,nv):\n"
        "            filter(xp,Pp,H,v,R,rtk->nx,nv);\n"
        "        s10_gain_count = 0;"
    ),
    (
        "        update_stat(rtk, obs, n, stat);",
        "        update_stat(rtk, obs, n, stat);\n"
        "        if (rtk->sol.stat == SOLQ_PPP) s10_report(rtk, obs, nv, s10_before);"
    ),
])

patch += rewrite("rtkcmn.c", [
    (
        "static int filter_(const double *x,",
        "extern void s10_active_indices(const int *ix, int n);\n"
        "extern void s10_capture_gain(const double *K, const double *v, int n, int m);\n"
        "static int filter_(const double *x,"
    ),
    (
        "        matmul(\"NN\",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */",
        "        matmul(\"NN\",n,m,m,F,Q,K);   /* K=P*H*Q^-1 */\n"
        "        s10_capture_gain(K, v, n, m);"
    ),
    (
        "    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);",
        "    s10_active_indices(ix, k);\n"
        "    info=filter_(x_,P_,H_,v,R,k,m,xp_,Pp_,physical);"
    ),
])

(OUT / "step10_private.patch").write_text(patch, encoding="utf-8")

script = (ROOT / "build/build.cmd").read_text(encoding="utf-8-sig").splitlines()
lines = script[:2]
link = next(l for l in script if l.startswith("link ") and "ppp_ssr_replay.exe" in l)
for source in ("ppp", "rtkcmn"):
    c = str(CORE / f"{source}.c")
    obj = str(ROOT / "build" / f"{source}.obj")
    new = str(OUT / f"private_{source}.obj")
    line = next(l for l in script if l.startswith("cl ") and f'"{c}"' in l)
    lines.extend([
        line.replace(c, str(OUT / f"private_{source}.c")).replace(obj, new) + f' /I"{OUT}"',
        "if errorlevel 1 exit /b 1",
    ])
    link = link.replace(obj, new)
lines.append(link.replace(str(ROOT / "bin/ppp_ssr_replay.exe"), str(OUT / "step10_probe.exe")))
cmd = OUT / "build_private.cmd"
cmd.write_text("\n".join(lines) + "\n", encoding="utf-8")
with (OUT / "build_private.log").open("wb") as log:
    subprocess.run(["cmd", "/c", str(cmd)], cwd=OUT, stdout=log, stderr=subprocess.STDOUT, check=True)
print("Built step10_probe.exe successfully.")
