/* S1/S2 private trial recentering for the B_VERIFIED non-combined replay. */
enum { S8_RCB_SLOTS=NIFB_PPP+1 };
typedef struct {
    int peers,eligible,used,ambiguities;
    double old,median,shift,updated,variance;
} s8_shift_t;
typedef struct {
    int kind,sat;
    double innovation,variance;
} s8_prior_t;
typedef struct {
    s8_shift_t isb[NCLK_PPP],rcb[S8_RCB_SLOTS];
    int pseudo_count,p_unchanged,pseudo_unchanged;
} s8_trial_t;

static int s8_with_A(void)
{
    const char *s=getenv("STEP8_SCHEME");
    return s && !strcmp(s,"S1S2A");
}

static int s8_prior_rows(const ppp_innovation_meta_t *meta,const double *v,const double *R,
                         int nv,s8_prior_t *rows)
{
    int i,n=0;
    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=meta+i;
        if(m->measurement_class==INNOV_GNSS_CODE || m->measurement_class==INNOV_GNSS_PHASE)continue;
        if(n>=MAXSAT+3)return -1;
        rows[n].kind=m->measurement_class;
        rows[n].sat=m->sat;
        rows[n].innovation=v[i];
        rows[n].variance=R[i+i*nv];
        n++;
    }
    return n;
}

static int s8_same_priors(const s8_prior_t *rows,int count,const ppp_innovation_meta_t *meta,
                          const double *v,const double *R,int nv)
{
    s8_prior_t current[MAXSAT+3];
    int i,n=s8_prior_rows(meta,v,R,nv,current);
    if(count<0 || count!=n)return 0;
    for(i=0;i<n;i++)if(current[i].kind!=rows[i].kind || current[i].sat!=rows[i].sat ||
        current[i].innovation!=rows[i].innovation || current[i].variance!=rows[i].variance)return 0;
    return 1;
}

static int s8_recenter(const rtk_t *rtk,double *xp,int state,double *samples,int n,s8_shift_t *audit)
{
    double next;
    audit->peers=n;
    audit->old=audit->updated=xp[state];
    audit->variance=rtk->P[state+state*rtk->nx];
    audit->eligible=fabs(rtk->x[state])<=1E-5 && audit->variance>0.;
    if(!audit->eligible || n<3)return 0;
    audit->median=ppp_median(samples,n);
    next=xp[state]+audit->median;
    if(!isfinite(next))return 0;
    if(next==0.)next=1E-6;
    audit->updated=next;
    audit->shift=next-xp[state];
    audit->used=1;
    xp[state]=next;
    return 1;
}

static int s8_isb(const rtk_t *rtk,double *xp,const double *v,const ppp_innovation_meta_t *rows,
                  int nv,s8_trial_t *audit)
{
    const prcopt_t *opt=&rtk->opt;
    double work[S7_ROWS];
    int g,i,n,used=0;
    for(g=1;g<NCLK_PPP;g++) {
        for(i=n=0;i<nv;i++) {
            const ppp_innovation_meta_t *m=rows+i;
            if(m->measurement_class==INNOV_GNSS_CODE && m->frequency_slot==0 &&
                ppp_clk_index(m->sys)==g)work[n++]=v[i];
        }
        used+=s8_recenter(rtk,xp,IC(g,opt),work,n,&audit->isb[g]);
    }
    return used;
}

static int s8_rcb(const rtk_t *rtk,double *xp,const double *v,const ppp_innovation_meta_t *rows,
    int nv,const int seed_source[MAXSAT][NFREQ],s8_trial_t *audit)
{
    const prcopt_t *opt=&rtk->opt;
    double work[S7_ROWS];
    int d,i,n,s,f,used=0;
    for(d=0;d<ND(opt);d++) {
        s8_shift_t *event=&audit->rcb[d];
        for(i=n=0;i<nv;i++) {
            const ppp_innovation_meta_t *m=rows+i;
            if(m->measurement_class==INNOV_GNSS_CODE && m->frequency_slot>0 &&
                ppp_ifb_index(m->sys,m->frequency_slot,m->signal,opt)==d)work[n++]=v[i];
        }
        if(!s8_recenter(rtk,xp,ID(d,opt),work,n,event))continue;
        used++;
        for(s=0;s<MAXSAT;s++)for(f=1;f<NF(opt) && f<NFREQ;f++)if(seed_source[s][f]==d+1) {
            const int state=IB(s+1,f,opt);
            xp[state]+=event->shift;
            if(xp[state]==0.)xp[state]=1E-6;
            event->ambiguities++;
        }
    }
    return used;
}

static void s8_emit_shift(int week,double tow,int trial,const char *kind,int slot,const s8_shift_t *s)
{
    trace(2,"$S8_SEED,%d,%.9f,%d,%s,%d,%d,%d,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%d\n",
        week,tow,trial,kind,slot,s->peers,s->eligible,s->used,s->old,s->median,
        s->shift,s->updated,s->variance,s->ambiguities);
}

static void s8_report(const rtk_t *rtk,const obsd_t *obs,int nv,int trial,
    const ppp_innovation_meta_t *meta,const double *before,const s8_trial_t *audit)
{
    double sum[3]={0};
    int i,k,week;
    const double tow=time2gpst(obs[0].time,&week);
    for(i=1;i<NCLK_PPP;i++)s8_emit_shift(week,tow,trial,"ISB",i,audit->isb+i);
    for(i=0;i<ND(&rtk->opt);i++)s8_emit_shift(week,tow,trial,"RCB",i,audit->rcb+i);
    for(i=0;i<nv;i++) {
        const double *d=s7_delta[i];
        for(k=0;k<3;k++)sum[k]+=d[k];
        if(meta[i].measurement_class==INNOV_GNSS_CODE) {
            char sat[8];
            satno2id(meta[i].sat,sat);
            trace(2,"$S8_CODE,%d,%.9f,%s,%s,%.17g,%.17g,%.17g\n",
                week,tow,sat,code2obs(meta[i].signal),d[0],d[1],d[2]);
        }
    }
    trace(2,"$S8_CLOSURE,%d,%.9f,%d,%d,%d,%d,%.17g,%.17g,%.17g\n",week,tow,trial,
        audit->p_unchanged,audit->pseudo_unchanged,audit->pseudo_count,
        rtk->x[0]-before[0]-sum[0],rtk->x[1]-before[1]-sum[1],rtk->x[2]-before[2]-sum[2]);
}

