/* Private Step 11 Part B (S1..S4) experiment & closure hooks. */
enum {
    S11_BASE = 0,
    S11_S1 = 1,
    S11_S2 = 2,
    S11_S3 = 3,
    S11_S4 = 4,
    S11_ROWS = MAXOBS * 2 * NFREQ + MAXSAT + 3
};

static int s11_gain_count = 0, s11_pos_row[3] = {-1, -1, -1};
static double s11_delta[S11_ROWS][3];
static double s11_last_delta_df = 0.0, s11_last_cmd_max_f = 1.0, s11_last_cmd_sum_f = 0.0;
static int s11_last_ndf = 0, s11_last_nsf = 0;
static int s11_last_cmd_inflated = 0, s11_last_cmd_rows = 0;
static int s11_q0_wait_epochs = 0, s11_q0_wait_smoothed = 0;

static double s11_cmd_prev_p[MAXSAT][NFREQ];
static double s11_cmd_prev_d[MAXSAT][NFREQ];
static gtime_t s11_cmd_prev_t[MAXSAT][NFREQ];
static double s11_cmd_var_ema[MAXSAT][NFREQ];
static uint8_t s11_cmd_code[MAXSAT][NFREQ];
static int s11_cmd_valid[MAXSAT][NFREQ];
static int s11_cmd_count[MAXSAT][NFREQ];
static gtime_t s11_cmd_last_epoch = {0};

static int s11_scheme(void)
{
    const char *s = getenv("STEP11_SCHEME");
    if (!s || !*s || !strcmp(s, "Baseline")) return S11_BASE;
    if (!strcmp(s, "S1_O1_robust")) return S11_S1;
    if (!strcmp(s, "S2_Q0_presmooth")) return S11_S2;
    if (!strcmp(s, "S3_presmooth_cmd")) return S11_S3;
    if (!strcmp(s, "S4_joint")) return S11_S4;
    return -1;
}

static int s11_use_o1_robust(int sc) { return sc == S11_S1 || sc == S11_S4; }
static int s11_use_presmooth(int sc) { return sc == S11_S2 || sc == S11_S3 || sc == S11_S4; }
static int s11_use_cmd(int sc) { return sc == S11_S3 || sc == S11_S4; }

extern void s11_active_indices(const int *ix, int n)
{
    int i;
    if (!s11_gain_count) return;
    s11_pos_row[0] = s11_pos_row[1] = s11_pos_row[2] = -1;
    for (i = 0; i < n; i++) {
        if (ix[i] >= 0 && ix[i] < 3) s11_pos_row[ix[i]] = i;
    }
}

extern void s11_capture_gain(const double *K, const double *v, int n, int m)
{
    int i, k;
    if (!s11_gain_count || m != s11_gain_count) return;
    for (i = 0; i < m; i++) for (k = 0; k < 3; k++) {
        int j = s11_pos_row[k];
        s11_delta[i][k] = j >= 0 ? K[j + i * n] * v[i] : 0.0;
    }
}

static int s11_sat_freq_count(const rtk_t *rtk, const obsd_t *ob, const nav_t *nav)
{
    const prcopt_t *opt = &rtk->opt;
    int sat = ob->sat, sys = satsys(sat, NULL), f, count = 0;
    const ssat_t *ss;
    if (sat < 1 || sat > MAXSAT || !sys) return 0;
    ss = rtk->ssat + sat - 1;
    for (f = 0; f < NF(opt) && f < NFREQ; f++) {
        int code = ob->code[f];
        int cbias_ok = 1;
        int code_ok, phase_ok;
        if (!ppp_signal_supported(sys, f, code, opt) ||
            sat2freq(sat, code, nav) <= 0.0) continue;
#ifdef PPP_NTRIP_SSR
        if (opt->sateph == EPHOPT_SSRAPC || opt->sateph == EPHOPT_SSRCOM) {
            cbias_ok = (code > 0 && code <= MAXCODE && nav->ssr[sat - 1].cbias_valid[code - 1]);
        }
#endif
        code_ok = (ob->P[f] != 0.0 && !ss->ppp_code_bad[f] &&
                   ppp_code_modelled(sys, f, code, opt) && cbias_ok);
        phase_ok = (ob->L[f] != 0.0 && !(ob->LLI[f] & LLI_HALFC) &&
                    !rtk->ppp_code_warmup &&
                    !(smartphone_ppp_policy(opt).quality_learning &&
                      ppp_phase_quarantined(ss, f, ob->time)));
        if (code_ok || phase_ok) count++;
    }
    return count;
}

static double s11_df_iono_delta(const rtk_t *rtk, const obsd_t *obs, int n,
    const nav_t *nav, const double *x, const double *pos, const double *azel_arr,
    const int *exc, int *ndf_out)
{
    double diffs[MAXSAT];
    unsigned char seen[MAXSAT] = {0};
    int i, ndf = 0;
    const prcopt_t *opt = &rtk->opt;
    if (ndf_out) *ndf_out = 0;
    for (i = 0; i < n && i < MAXOBS; i++) {
        int sat = obs[i].sat, ii;
        const double *az = azel_arr ? (azel_arr + i * 2) : rtk->ssat[sat - 1].azel;
        double ion_gim, var_gim;
        if (sat < 1 || sat > MAXSAT || seen[sat - 1]) continue;
        seen[sat - 1] = 1;
        if (exc && exc[i]) continue;
        if (az[1] < opt->elmin) continue;
        if (s11_sat_freq_count(rtk, obs + i, nav) < 2) continue;
        ii = II(sat, opt);
        if (ii < 0 || ii >= rtk->nx) continue;
        if (x[ii] == 0.0 || rtk->P[ii + ii * rtk->nx] <= 0.0) continue;
        if (!ionex_vertical_prior_floor(obs[i].time, nav, pos, az, opt,
                ion_constraint_sigma(opt), &ion_gim, &var_gim)) continue;
        diffs[ndf++] = x[ii] - ion_gim;
    }
    if (ndf_out) *ndf_out = ndf;
    if (ndf < 3) return 0.0;
    {
        double d = ppp_median(diffs, ndf);
        if (d < -2.0) d = -2.0;
        if (d > 2.0) d = 2.0;
        return d;
    }
}

static void s11_cmd_reset_slot(int s, int f)
{
    s11_cmd_valid[s][f] = 0;
    s11_cmd_count[s][f] = 0;
    s11_cmd_var_ema[s][f] = 0.0;
    s11_cmd_code[s][f] = 0;
    s11_cmd_prev_p[s][f] = 0.0;
    s11_cmd_prev_d[s][f] = 0.0;
    s11_cmd_prev_t[s][f].time = 0;
    s11_cmd_prev_t[s][f].sec = 0.0;
}

static void s11_cmd_update(const rtk_t *rtk, const obsd_t *obs, int n, const nav_t *nav)
{
    enum { NWORK = MAXOBS * NFREQ };
    const prcopt_t *opt = &rtk->opt;
    const int sc = s11_scheme();
    double c_val[NWORK], work[NWORK], med_cmd[NCLK_PPP] = {0};
    int c_s[NWORK], c_f[NWORK], c_g[NWORK];
    int c_cnt[NCLK_PPP] = {0};
    unsigned char c_seen[NCLK_PPP][MAXSAT] = {{0}};
    unsigned char skip_update[MAXOBS][NFREQ] = {{0}};
    int i, f, k, q, nc = 0, grp;

    if (!s11_use_cmd(sc) || !obs || n <= 0 || !nav) return;
    if (s11_cmd_last_epoch.time &&
        fabs(timediff(obs[0].time, s11_cmd_last_epoch)) < 1E-6) {
        return;
    }
    s11_cmd_last_epoch = obs[0].time;

    for (i = 0; i < n && i < MAXOBS; i++) {
        int sat = obs[i].sat, s = sat - 1, sys = satsys(sat, NULL);
        if (sat < 1 || sat > MAXSAT || (grp = ppp_clk_index(sys)) < 0) continue;
        for (f = 0; f < opt->nf && f < NFREQ; f++) {
            const ssat_t *ss = rtk->ssat + s;
            double freq = sat2freq(sat, obs[i].code[f], nav);
            double dt;
            if (!ppp_signal_supported(sys, f, obs[i].code[f], opt) ||
                !ppp_code_modelled(sys, f, obs[i].code[f], opt) ||
                freq <= 0.0 ||
                obs[i].P[f] == 0.0 || !isfinite(obs[i].P[f]) ||
                obs[i].D[f] == 0.0 || !isfinite(obs[i].D[f]) ||
                fabs(obs[i].D[f]) > 20000.0 ||
                (obs[i].LLI[f] & LLI_SLIP) ||
                (ss->slip[f] & LLI_SLIP) ||
                ss->ppp_code_bad[f]) {
                s11_cmd_reset_slot(s, f);
                skip_update[i][f] = 1;
                continue;
            }
            if (s11_cmd_valid[s][f] && obs[i].code[f] != s11_cmd_code[s][f]) {
                s11_cmd_reset_slot(s, f);
            }
            if (!s11_cmd_valid[s][f]) continue;
            dt = timediff(obs[i].time, s11_cmd_prev_t[s][f]);
            if (dt < 0.0 || dt > 5.0) {
                s11_cmd_reset_slot(s, f);
            } else if (dt < 0.2) {
                skip_update[i][f] = 1;
            } else if (nc < NWORK) {
                double lambda = CLIGHT / freq;
                double avgd = 0.5 * (s11_cmd_prev_d[s][f] + obs[i].D[f]);
                double raw_cmd = (obs[i].P[f] - s11_cmd_prev_p[s][f]) + lambda * avgd * dt;
                if (isfinite(raw_cmd)) {
                    c_val[nc] = raw_cmd;
                    c_s[nc] = s;
                    c_f[nc] = f;
                    c_g[nc] = grp;
                    if (!c_seen[grp][s]) {
                        c_seen[grp][s] = 1;
                        c_cnt[grp]++;
                    }
                    nc++;
                }
            }
        }
    }

    for (grp = 0; grp < NCLK_PPP; grp++) {
        if (c_cnt[grp] < 3) continue;
        for (k = q = 0; k < nc; k++) {
            if (c_g[k] == grp) work[q++] = c_val[k];
        }
        med_cmd[grp] = ppp_median(work, q);
    }

    for (k = 0; k < nc; k++) {
        int s = c_s[k], f = c_f[k];
        double res_cmd;
        if (c_cnt[c_g[k]] < 3) continue;
        res_cmd = c_val[k] - med_cmd[c_g[k]];
        if (!isfinite(res_cmd) || fabs(res_cmd) > 30.0) continue;
        if (s11_cmd_count[s][f] == 0) {
            s11_cmd_var_ema[s][f] = SQR(res_cmd);
        } else {
            const double alpha = 0.25;
            s11_cmd_var_ema[s][f] = (1.0 - alpha) * s11_cmd_var_ema[s][f] + alpha * SQR(res_cmd);
        }
        s11_cmd_count[s][f]++;
    }

    for (i = 0; i < n && i < MAXOBS; i++) {
        int sat = obs[i].sat, s = sat - 1;
        if (sat < 1 || sat > MAXSAT) continue;
        for (f = 0; f < opt->nf && f < NFREQ; f++) {
            if (skip_update[i][f]) continue;
            s11_cmd_prev_p[s][f] = obs[i].P[f];
            s11_cmd_prev_d[s][f] = obs[i].D[f];
            s11_cmd_prev_t[s][f] = obs[i].time;
            s11_cmd_code[s][f] = obs[i].code[f];
            s11_cmd_valid[s][f] = 1;
        }
    }
}

static int s11_sanitize_wait(const obsd_t *in, int n, obsd_t *out)
{
    int i, f, k = 0;
    for (i = 0; i < n; i++) {
        if (in[i].rcv != 1) continue;
        if (in[i].sat < 1 || in[i].sat > MAXSAT) continue;
        if (k >= MAXOBS) break;
        out[k] = in[i];
        for (f = 0; f < NFREQ + NEXOBS; f++) {
            if (!isfinite(out[k].P[f]) || (out[k].P[f] != 0.0 &&
                (out[k].P[f] < 1E6 || out[k].P[f] > 1E8))) {
                out[k].P[f] = 0.0;
            }
            if (!isfinite(out[k].L[f]) || fabs(out[k].L[f]) > 1E12) {
                out[k].L[f] = 0.0;
                out[k].LLI[f] |= LLI_SLIP;
            }
            if (!isfinite(out[k].D[f]) || fabs(out[k].D[f]) > 20000.0) {
                out[k].D[f] = 0.0;
            }
        }
        k++;
    }
    return k;
}

static void prepare_signal_quality_ppp(rtk_t *rtk, const obsd_t *obs, int n);
static void precheck_obs_ppp(rtk_t *rtk, const obsd_t *obs, int n, const nav_t *nav);
static int uddoppsm_ppp(rtk_t *rtk, const obsd_t *obs, int n, const nav_t *nav, const double *rs);

extern void ppp_presmooth_wait(rtk_t *rtk, const obsd_t *obs, int n, const nav_t *nav)
{
    const int sc = s11_scheme();
    obsd_t clean_obs[MAXOBS];
    int nc, ns, week;
    double tow;

    if (!s11_use_presmooth(sc) || !rtk || !obs || n <= 0 || !nav) return;
    if (rtk->opt.ionoopt != IONOOPT_EST || rtk->ppp_clock_valid) return;

    nc = s11_sanitize_wait(obs, n, clean_obs);
    if (nc <= 0) return;

    prepare_signal_quality_ppp(rtk, clean_obs, nc);
    if (smartphone_ppp_policy(&rtk->opt).corrected_lifecycle ||
        pppopt_number(&rtk->opt, "-PREPROC=", 0.0, 0.0, 1.0) >= 0.5) {
        precheck_obs_ppp(rtk, clean_obs, nc, nav);
    }
    s11_cmd_update(rtk, clean_obs, nc, nav);
    ns = uddoppsm_ppp(rtk, clean_obs, nc, nav, NULL);
    s11_q0_wait_epochs++;
    s11_q0_wait_smoothed += ns;
    tow = time2gpst(clean_obs[0].time, &week);
    trace(3, "$S11_WAIT_SMOOTH,%d,%.9f,nc=%d,smoothed=%d\n", week, tow, nc, ns);
}

static void s11_report(const rtk_t *rtk, const obsd_t *obs, int nv, const double *before)
{
    double sum[3] = {0};
    int row, k, week;
    const double tow = time2gpst(obs[0].time, &week);
    const int sc = s11_scheme();
    const double cmd_mean = s11_last_cmd_rows > 0 ?
        (s11_last_cmd_sum_f / (double)s11_last_cmd_rows) : 1.0;

    for (row = 0; row < nv; row++) {
        for (k = 0; k < 3; k++) sum[k] += s11_delta[row][k];
    }
    trace(2, "$S11_CLOSURE,%d,%.9f,%.17g,%.17g,%.17g\n", week, tow,
        rtk->x[0] - before[0] - sum[0],
        rtk->x[1] - before[1] - sum[1],
        rtk->x[2] - before[2] - sum[2]);
    trace(2, "$S11_INFO,%d,%.9f,%d,%d,%.9f,%d,%d,%d,%d,%.6f,%.6f\n",
        week, tow, s11_last_ndf, s11_last_nsf, s11_last_delta_df,
        s11_q0_wait_epochs, s11_q0_wait_smoothed,
        s11_last_cmd_rows, s11_last_cmd_inflated, s11_last_cmd_max_f, cmd_mean);
}
