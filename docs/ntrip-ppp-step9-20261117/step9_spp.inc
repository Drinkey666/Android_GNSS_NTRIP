/* Included only by the private pntpos translation unit, after NX is defined. */
static FILE *s9_log;
static int s9_call, s9_attempt, s9_winner, s9_parent, s9_omitted;
static int s9_iteration=-1, s9_postfit;
static const char *s9_role;

static void s9_vector(const double *values, int n)
{
    int i;
    for (i=0; i<n; i++) fprintf(s9_log,"\t%.17g",values[i]);
}

static void s9_time(gtime_t time)
{
    int week=0;
    double tow=time2gpst(time,&week);
    fprintf(s9_log,"\t%d\t%.17g",week,tow);
}

static void s9_open(void)
{
    if (!s9_log) {
        const char *path=getenv("STEP9_AUDIT_FILE");
        if (!path || !*path) return;
        s9_log=fopen(path,"w");
        if (!s9_log) { perror(path); exit(EXIT_FAILURE); }
    }
}

static void s9_begin(gtime_t time, int startup, int ephopt)
{
    s9_open();
    if (!s9_log) return;
    s9_call++;
    s9_winner=s9_parent=s9_omitted=0;
    s9_role="initial";
    fprintf(s9_log,"CALL\t%d",s9_call);
    s9_time(time);
    fprintf(s9_log,"\t%d\t%d\t%d\n",startup,ephopt,NX);
}

static void s9_hypothesis(const char *role, int omit, int parent)
{
    s9_role=role;
    s9_omitted=omit;
    s9_parent=parent;
}

static void s9_try(void)
{
    if (!s9_log) return;
    fprintf(s9_log,"TRY\t%d\t%d\t%d\t%s\t%d\n",
            s9_call,++s9_attempt,s9_parent,s9_role,s9_omitted);
}

static void s9_selection(const char *role, int round, int sat, int winner)
{
    s9_winner=winner;
    if (s9_log) fprintf(s9_log,"SELECT\t%d\t%d\t%s\t%d\t%d\n",
                        s9_call,winner,role,round,sat);
}

static void s9_result(const char *status, int it, int wrote_position)
{
    if (s9_log) fprintf(s9_log,"RESULT\t%d\t%d\t%s\t%d\t%d\n",
                        s9_call,s9_attempt,status,it,wrote_position);
}

static void s9_metrics(int candidate, int dof, double score, double z, double metres)
{
    if (s9_log) fprintf(s9_log,"METRICS\t%d\t%d\t%d\t%d\t%.17g\t%.17g\t%.17g\n",
                        s9_call,s9_winner,candidate,dof,score,z,metres);
}

static void s9_row(int j, int oi, const obsd_t *o, int datum, int sys,
                   const double *azel, double corrected_p, double r, double dt,
                   double ion, double trop, double vare, double vmeas,
                   double vion, double vtrp, double varerr, double total,
                   double v, const double *H)
{
    char sat[8]="-";
    if (!s9_log || s9_iteration<0) return;
    if (s9_postfit) {
        fprintf(s9_log,"POST\t%d\t%d\t%d\t%d\t%.17g\n",s9_call,s9_attempt,oi,datum,v);
        return;
    }
    if (o) satno2id(o->sat,sat);
    fprintf(s9_log,"ROW\t%d\t%d\t%d\t%d\t%d\t%s\t%d\t%s\t%d",
            s9_call,s9_attempt,s9_iteration,j,oi,sat,sys,o?code2obs(o->code[0]):"-",datum);
    {
        const double values[]={azel?azel[1]*R2D:0.0,azel?azel[0]*R2D:0.0,
            o?o->SNR[0]*SNR_UNIT:0.0,o?o->P[0]:0.0,corrected_p,r,dt,ion,trop,
            vare,vmeas,vion,vtrp,varerr,total,v};
        s9_vector(values,(int)(sizeof(values)/sizeof(*values)));
    }
    s9_vector(H,NX);
    fputc('\n',s9_log);
}

static void s9_step(int iteration, int nv, const double *before, const double *dx,
                    const double *after)
{
    if (!s9_log) return;
    fprintf(s9_log,"STEP\t%d\t%d\t%d\t%d",s9_call,s9_attempt,iteration,nv);
    s9_vector(before,NX);
    s9_vector(dx,NX);
    s9_vector(after,NX);
    fputc('\n',s9_log);
}

static void s9_end(int ok, const sol_t *sol)
{
    if (!s9_log) return;
    fprintf(s9_log,"END\t%d\t%d\t%d\t%d",s9_call,s9_winner,ok,sol->stat);
    s9_vector(sol->rr,3);
    s9_vector(sol->dtr,NX-3);
    fputc('\n',s9_log);
}

void s9_state(gtime_t time, const char *stage, const rtk_t *rtk,
              const double *position, double clock_m, int flag1, int flag2)
{
    s9_open();
    if (!s9_log) return;
    fputs("STATE",s9_log);
    s9_time(time);
    fprintf(s9_log,"\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%.17g\t%.17g\t%.17g",
            stage,s9_call,flag1,flag2,rtk->sol.stat,rtk->ppp_failure,
            rtk->ppp_spp_clock_valid,rtk->ppp_clock_valid,rtk->ppp_spp_clock_m,
            CLIGHT*rtk->sol.dtr[0],clock_m);
    s9_vector(position,3);
    s9_vector(rtk->sol.rr,3);
    fputc('\n',s9_log);
}
