/* Private step 4 replay. One RTK session runs in each process. */
enum { STEP4_M1=1, STEP4_M2=2, STEP4_M3=4, STEP4_ROWS=MAXOBS*2*NFREQ+MAXSAT+3 };

typedef struct {
    gtime_t last;
    double anchor;
    unsigned char code, half, gim;
} step4_arc_t;

typedef struct {
    double r_before, m1, m2, m3, cmc_drift, gim_residual;
    int m1_gim, m3_gim;
} step4_weight_t;

typedef struct {
    int mask;
    step4_weight_t rows[STEP4_ROWS];
} step4_trial_t;

static step4_arc_t step4_arcs[MAXSAT][NFREQ];
static void step4_forget_arc(int sat,int f)
{
    step4_arcs[sat-1][f].last.time=0;
}

static int step4_gain_count;
static int step4_pos_row[3];
static double step4_delta[STEP4_ROWS][3];

static int step4_mask(void)
{
    const char *mode=getenv("STEP4_BIAS_MASK");
    return mode ? atoi(mode) : 0;
}

/* The instrumented filter supplies its exact active indices and K. */
extern void step4_active_indices(const int *ix,int n)
{
    int i;
    if(!step4_gain_count)return;
    step4_pos_row[0]=step4_pos_row[1]=step4_pos_row[2]=-1;
    for(i=0;i<n;i++)if(ix[i]>=0 && ix[i]<3)step4_pos_row[ix[i]]=i;
}

extern void step4_capture_gain(const double *K,const double *v,int n,int m)
{
    int i,k;
    if(!step4_gain_count || m!=step4_gain_count)return;
    for(i=0;i<m;i++)for(k=0;k<3;k++) {
        int pos=step4_pos_row[k];
        step4_delta[i][k]=pos>=0 ? K[pos+i*n]*v[i] : 0.0;
    }
}

static int step4_arc_matches(const step4_arc_t *arc,const ssat_t *ss,
                             const obsd_t *ob,int f,int gim)
{
    const double gap=timediff(ob->time,arc->last);
    return arc->last.time && gap>0.0 && gap<=3.0 &&
        arc->code==ob->code[f] && arc->half==((ob->LLI[f]&LLI_HALFC)!=0) &&
        arc->gim==gim && !((ob->LLI[f]|ss->slip[f])&LLI_SLIP) &&
        !ss->ppp_arc_reset[f] && !ss->ppp_arc_pending[f];
}

static void step4_save_arcs(const rtk_t *rtk,const obsd_t *obs,int n,const nav_t *nav,
    const double *dr,const double *azel,const ppp_diag_epoch_t *diag)
{
    const prcopt_t *opt=&rtk->opt;
    double rr[3],pos[3];
    int i,f;
    for(i=0;i<3;i++)rr[i]=rtk->x[i]+dr[i];
    ecef2pos(rr,pos);
    for(i=0;i<n;i++) {
        const int sat=obs[i].sat;
        const ssat_t *ss=&rtk->ssat[sat-1];
        double ion=0.0,var=0.0;
        const int gim=ionex_vertical_prior(obs[i].time,nav,pos,azel+i*2,opt,&ion,&var);
        const double dion_gim=gim ? ppp_iono_mapf(nav,pos,azel+i*2)*ion : 0.0;
        for(f=0;f<NF(opt) && f<NFREQ;f++) {
            const ppp_diag_signal_t *d=&diag->obs[i][f];
            step4_arc_t *arc=&step4_arcs[sat-1][f];
            double cmc,hz;
            if(!d->cmc_ok || !d->code_ok || !d->phase_ok)continue;
            hz=sat2freq(sat,obs[i].code[f],nav);
            if(hz<=0.0)continue;
            cmc=d->cmc;
            if(gim)cmc+=2.0*(d->iono-SQR(FREQL1/hz)*dion_gim);
            if(!isfinite(cmc))continue;
            if(!step4_arc_matches(arc,ss,obs+i,f,gim))arc->anchor=cmc;
            arc->last=obs[i].time;
            arc->code=obs[i].code[f];
            arc->half=(obs[i].LLI[f]&LLI_HALFC)!=0;
            arc->gim=(unsigned char)gim;
        }
    }
}

static void step4_prefit_gim(const rtk_t *rtk,const obsd_t *obs,int n,const nav_t *nav,
    const double *xp,const double *dr,const double *azel,const double *v,double *R,
    const ppp_innovation_meta_t *rows,int nv,step4_trial_t *probe)
{
    const prcopt_t *opt=&rtk->opt;
    unsigned char used[STEP4_ROWS]={0};
    unsigned int freq_slots[MAXSAT]={0};
    int counts[MAXSAT]={0},gim_ok[MAXOBS]={0};
    double rr[3],pos[3],delta_slant[MAXOBS]={0},gim_v[STEP4_ROWS];
    int i,j,k;
    for(i=0;i<3;i++)rr[i]=xp[i]+dr[i];
    ecef2pos(rr,pos);
    for(i=0;i<n;i++) {
        double ion,var;
        if(ionex_vertical_prior(obs[i].time,nav,pos,azel+i*2,opt,&ion,&var)) {
            gim_ok[i]=1;
            delta_slant[i]=ppp_iono_mapf(nav,pos,azel+i*2)*(xp[II(obs[i].sat,opt)]-ion);
        }
    }
    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=rows+i;
        gim_v[i]=v[i];
        if(m->measurement_class!=INNOV_GNSS_CODE)continue;
        if(!(freq_slots[m->sat-1]&(1U<<m->frequency_slot))) {
            freq_slots[m->sat-1]|=1U<<m->frequency_slot;
            counts[m->sat-1]++;
        }
        if(gim_ok[m->source_obs_index] && m->frequency_hz>0.0) {
            const double scaled=SQR(FREQL1/m->frequency_hz)*delta_slant[m->source_obs_index];
            if(isfinite(v[i]+scaled)) {
                gim_v[i]+=scaled;
                probe->rows[i].m1_gim=1;
            }
        }
        probe->rows[i].gim_residual=gim_v[i];
    }
    for(i=0;i<nv;i++) {
        int group[STEP4_ROWS],ns=0,ng=0;
        unsigned char seen[MAXSAT]={0};
        double work[MAXSAT],samples[STEP4_ROWS],med,mad;
        const ppp_innovation_meta_t *m=rows+i;
        if(used[i] || m->measurement_class!=INNOV_GNSS_CODE)continue;
        for(j=i;j<nv;j++) {
            const ppp_innovation_meta_t *s=rows+j;
            if(s->measurement_class!=INNOV_GNSS_CODE || s->sys!=m->sys || s->signal!=m->signal)continue;
            group[ng++]=j;
            used[j]=1;
        }
        for(j=0;j<ng;j++) {
            const int sat=rows[group[j]].sat;
            int same=0;
            if(seen[sat-1])continue;
            seen[sat-1]=1;
            for(k=j;k<ng;k++)if(rows[group[k]].sat==sat)samples[same++]=gim_v[group[k]];
            work[ns++]=ppp_median(samples,same);
        }
        if(ns<4)continue;
        med=ppp_median(work,ns);
        for(j=0;j<ns;j++)work[j]=fabs(work[j]-med);
        mad=1.4826*ppp_median(work,ns);
        for(j=0;j<ng;j++) {
            const int r=group[j];
            const int single=counts[rows[r].sat-1]<2;
            const double gate=MAX(single?2.5:3.2,2.5*MAX(mad,1.2));
            const double dev=fabs(gim_v[r]-med);
            if(dev<=gate)continue;
            probe->rows[r].m1=MIN(single?64.0:36.0,SQR(dev/gate));
            R[r+r*nv]*=probe->rows[r].m1;
        }
    }
}

static void step4_report(const rtk_t *rtk,const obsd_t *obs,int nv,int trial,
    const ppp_innovation_meta_t *meta,const double *v,const double *R,
    const double *before,const step4_trial_t *probe)
{
    double total[3]={0};
    int week,row,k;
    const double tow=time2gpst(obs[0].time,&week);
    for(row=0;row<nv;row++) {
        const ppp_innovation_meta_t *m=meta+row;
        const step4_weight_t *w=probe->rows+row;
        char sat[8];
        for(k=0;k<3;k++)total[k]+=step4_delta[row][k];
        if(m->measurement_class!=INNOV_GNSS_CODE)continue;
        satno2id(m->sat,sat);
        if(strcmp(sat,"G03") && strcmp(sat,"G10") && strcmp(sat,"G25") &&
            strcmp(sat,"E27") && strcmp(sat,"C19"))continue;
        trace(2,"$STEP4_CODE,%d,%.9f,%d,%s,%s,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%d,%.17g,%d,%.17g,%.17g,%.17g\n",
            week,tow,trial,sat,code2obs(m->signal),m->frequency_slot,v[row],w->r_before,R[row+row*nv],
            w->m1,w->m2,w->m3,w->m1_gim,w->cmc_drift,w->m3_gim,
            step4_delta[row][0],step4_delta[row][1],step4_delta[row][2]);
    }
    trace(2,"$STEP4_CLOSURE,%d,%.9f,%d,%.17g,%.17g,%.17g\n",week,tow,trial,
        rtk->x[0]-before[0]-total[0],rtk->x[1]-before[1]-total[1],rtk->x[2]-before[2]-total[2]);
}

