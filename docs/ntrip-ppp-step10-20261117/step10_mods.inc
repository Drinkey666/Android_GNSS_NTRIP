/* Private Step 10 Part A audit & Part B (O1/O2) experiment hooks. */
enum { S10_BASE=0, S10_O1=1, S10_O2=2, S10_O3=3, S10_ROWS=MAXOBS*2*NFREQ+MAXSAT+3 };

static int s10_gain_count = 0, s10_pos_row[3] = {-1,-1,-1};
static double s10_delta[S10_ROWS][3];
static double s10_last_delta_df = 0.0, s10_last_o2_max_f = 1.0;
static int s10_last_ndf = 0, s10_last_nsf = 0, s10_last_o2_inflated = 0;

static int s10_scheme(void)
{
    const char *s = getenv("STEP10_SCHEME");
    if (!s || !*s || !strcmp(s, "Baseline")) return S10_BASE;
    if (!strcmp(s, "O1_df_iono_anchor")) return S10_O1;
    if (!strcmp(s, "O2_arc_code_info")) return S10_O2;
    if (!strcmp(s, "O3_joint")) return S10_O3;
    return -1;
}

static int s10_use_o1(int scheme) { return scheme == S10_O1 || scheme == S10_O3; }
static int s10_use_o2(int scheme) { return scheme == S10_O2 || scheme == S10_O3; }

extern void s10_active_indices(const int *ix, int n)
{
    int i;
    if (!s10_gain_count) return;
    s10_pos_row[0] = s10_pos_row[1] = s10_pos_row[2] = -1;
    for (i = 0; i < n; i++) {
        if (ix[i] >= 0 && ix[i] < 3) s10_pos_row[ix[i]] = i;
    }
}

extern void s10_capture_gain(const double *K, const double *v, int n, int m)
{
    int i, k;
    if (!s10_gain_count || m != s10_gain_count) return;
    for (i = 0; i < m; i++) for (k = 0; k < 3; k++) {
        int j = s10_pos_row[k];
        s10_delta[i][k] = j >= 0 ? K[j + i * n] * v[i] : 0.0;
    }
}

static FILE *s10_parta_stream(void)
{
    static FILE *fp = NULL;
    static int initialized = 0;
    if (!initialized) {
        const char *path = getenv("STEP10_PARTA_FILE");
        initialized = 1;
        if (path && *path) fp = fopen(path, "w");
    }
    return fp;
}

static void s10_parta_startqc_group(gtime_t t, int grp, int code, int refcode,
    int peers, double centre, double mad, double gate, double pos_gate,
    int sat, int f, double residual)
{
    FILE *fp = s10_parta_stream();
    int week;
    double tow;
    char sid[8];
    if (!fp) return;
    tow = time2gpst(t, &week);
    satno2id(sat, sid);
    fprintf(fp, "STARTQC\t%d\t%.6f\t%s\t%d\t%d\t%s\t%s\t%d\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\n",
        week, tow, sid, f + 1, grp, code2obs((uint8_t)code),
        refcode ? code2obs((uint8_t)refcode) : "GEOMETRY", peers,
        residual, centre, mad, gate, pos_gate);
    fflush(fp);
}

static void s10_parta_ppp_row(gtime_t t, int sat, int frq, uint8_t code,
    double P_corr, double r, double minus_c_dts, double dtrp,
    double dion_l1_slant, double C, double ion_gim_vert, double mapf,
    double ion_var_prior, double base_obs_var, double vart, double vari,
    double var_rs, double sigma0, double res, double az_deg, double el_deg)
{
    FILE *fp = s10_parta_stream();
    int week;
    double tow;
    char sid[8];
    if (!fp) return;
    tow = time2gpst(t, &week);
    satno2id(sat, sid);
    fprintf(fp, "PPP_ROW\t%d\t%.6f\t%s\t%d\t%s\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.12f\t%.6f\t%.6f\n",
        week, tow, sid, frq + 1, code2obs(code), P_corr, r, minus_c_dts, dtrp,
        C * dion_l1_slant, ion_gim_vert, mapf, ion_var_prior, base_obs_var,
        vart, vari, var_rs, sigma0, res, az_deg, el_deg, dion_l1_slant, C);
    fflush(fp);
}

static int s10_sat_freq_count(const rtk_t *rtk, const obsd_t *ob, const nav_t *nav)
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

static double s10_df_iono_delta(const rtk_t *rtk, const obsd_t *obs, int n,
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
        if (s10_sat_freq_count(rtk, obs + i, nav) < 2) continue;
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

static void s10_report(const rtk_t *rtk, const obsd_t *obs, int nv,
    const double *before)
{
    double sum[3] = {0};
    int row, k, week;
    const double tow = time2gpst(obs[0].time, &week);
    const int scheme = s10_scheme();
    for (row = 0; row < nv; row++) {
        for (k = 0; k < 3; k++) sum[k] += s10_delta[row][k];
    }
    trace(2, "$S10_CLOSURE,%d,%.9f,%.17g,%.17g,%.17g\n", week, tow,
        rtk->x[0] - before[0] - sum[0],
        rtk->x[1] - before[1] - sum[1],
        rtk->x[2] - before[2] - sum[2]);
    if (s10_use_o1(scheme)) {
        trace(2, "$S10_O1,%d,%.9f,%d,%d,%.9f\n", week, tow,
            s10_last_ndf, s10_last_nsf, s10_last_delta_df);
    }
    if (s10_use_o2(scheme)) {
        trace(2, "$S10_O2,%d,%.9f,%d,%.6f\n", week, tow,
            s10_last_o2_inflated, s10_last_o2_max_f);
    }
}
