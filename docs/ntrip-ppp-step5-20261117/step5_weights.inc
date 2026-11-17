/* Independent observer and code-measurement experiments for one replay process. */
enum { STEP5_ROWS=MAXOBS*2*NFREQ+MAXSAT+3 };
static int step5_remove_sys;
static double step5_gate;
static int step5_gain_count,step5_pos_row[3];
static double step5_delta[STEP5_ROWS][3];

typedef struct {
    double before, geom_factor, huber_factor, dev, scale, gim_v;
    int gim;
} step5_weight_t;

static void step5_config(void)
{
    const char *s=getenv("STEP5_SCHEME");
    if(!s)return;
    if(!strcmp(s,"NoGPSCode"))step5_remove_sys=SYS_GPS;
    else if(!strcmp(s,"NoGALCode"))step5_remove_sys=SYS_GAL;
    else if(!strcmp(s,"NoBDSCode"))step5_remove_sys=SYS_CMP;
    else if(!strcmp(s,"M1_v2_3.0"))step5_gate=3.0;
    else if(!strcmp(s,"M1_v2_2.5"))step5_gate=2.5;
}

extern void step5_active_indices(const int *ix,int n)
{
    int i;
    if(!step5_gain_count)return;
    step5_pos_row[0]=step5_pos_row[1]=step5_pos_row[2]=-1;
    for(i=0;i<n;i++)if(ix[i]>=0 && ix[i]<3)step5_pos_row[ix[i]]=i;
}

extern void step5_capture_gain(const double *K,const double *v,int n,int m)
{
    int i,k;
    if(!step5_gain_count || m!=step5_gain_count)return;
    for(i=0;i<m;i++)for(k=0;k<3;k++) {
        int pos=step5_pos_row[k];
        step5_delta[i][k]=pos>=0 ? K[pos+i*n]*v[i] : 0.0;
    }
}

static int step5_code_votes(const ppp_innovation_meta_t *meta,
    const step5_weight_t *weights,int nv,int sys,int signal,double *votes)
{
    unsigned char used[MAXSAT]={0};
    double samples[STEP5_ROWS];
    int i,j,n=0;
    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=&meta[i];
        int ns=0;
        if(m->measurement_class!=INNOV_GNSS_CODE || m->sys!=sys ||
            (signal && m->signal!=signal) || used[m->sat-1])continue;
        used[m->sat-1]=1;
        for(j=i;j<nv;j++) {
            const ppp_innovation_meta_t *s=&meta[j];
            if(s->measurement_class==INNOV_GNSS_CODE && s->sat==m->sat &&
                (!signal || s->signal==signal))samples[ns++]=weights[j].gim_v;
        }
        votes[n++]=ppp_median(samples,ns);
    }
    return n;
}

static void step5_pool_weights(const rtk_t *rtk,const obsd_t *obs,int n,const nav_t *nav,
    const double *xp,const double *dr,const double *azel,const double *v,double *R,
    const ppp_innovation_meta_t *meta,int nv,step5_weight_t *weights)
{
    const prcopt_t *opt=&rtk->opt;
    const int systems[]={SYS_GPS,SYS_GAL,SYS_CMP};
    double rr[3],pos[3],delta[MAXOBS]={0};
    int ok[MAXOBS]={0},i,j,k;
    for(i=0;i<3;i++)rr[i]=xp[i]+dr[i];
    ecef2pos(rr,pos);
    for(i=0;i<n;i++) {
        double ion,var;
        if(ionex_vertical_prior(obs[i].time,nav,pos,azel+i*2,opt,&ion,&var)) {
            ok[i]=1;
            delta[i]=ppp_iono_mapf(nav,pos,azel+i*2)*(xp[II(obs[i].sat,opt)]-ion);
        }
    }
    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=&meta[i];
        if(m->measurement_class!=INNOV_GNSS_CODE)continue;
        weights[i].gim_v=v[i];
        if(ok[m->source_obs_index] && m->frequency_hz>0.0) {
            const double correction=SQR(FREQL1/m->frequency_hz)*delta[m->source_obs_index];
            if(isfinite(v[i]+correction)) {
                weights[i].gim_v+=correction;
                weights[i].gim=1;
            }
        }
    }
    for(k=0;k<(int)(sizeof(systems)/sizeof(systems[0]));k++) {
        int sys=systems[k],count;
        unsigned char done[MAXCODE+1]={0};
        double votes[MAXSAT],center,scale;
        count=step5_code_votes(meta,weights,nv,sys,0,votes);
        if(count<4)continue;
        center=ppp_median(votes,count);
        for(i=0;i<count;i++)votes[i]=fabs(votes[i]-center);
        scale=MIN(2.5,MAX(1.2,1.4826*ppp_median(votes,count)));
        for(i=0;i<nv;i++) {
            int signal=meta[i].signal;
            double group_center=center;
            if(meta[i].measurement_class!=INNOV_GNSS_CODE || meta[i].sys!=sys ||
                signal<1 || signal>MAXCODE || done[signal])continue;
            done[signal]=1;
            count=step5_code_votes(meta,weights,nv,sys,signal,votes);
            if(count>=4) {
                group_center=ppp_median(votes,count);
                if(count==4)group_center=MIN(center+scale,MAX(center-scale,group_center));
            }
            for(j=i;j<nv;j++) {
                step5_weight_t *w=&weights[j];
                if(meta[j].measurement_class!=INNOV_GNSS_CODE || meta[j].sys!=sys ||
                    meta[j].signal!=signal)continue;
                w->scale=scale;
                w->dev=fabs(w->gim_v-group_center);
                if(w->dev<=step5_gate)continue;
                w->huber_factor=MIN(step5_gate==3.0?25.0:36.0,SQR(w->dev/step5_gate));
                R[j+j*nv]*=w->huber_factor;
            }
        }
    }
}

static void step5_report(const rtk_t *rtk,const obsd_t *obs,int nv,int trial,
    const ppp_innovation_meta_t *meta,const double *R,const double *before,
    const ppp_diag_epoch_t *diag,const step5_weight_t *weights)
{
    double sum[3]={0};
    int week,row,k;
    const double tow=time2gpst(obs[0].time,&week);
    for(row=0;row<nv;row++) {
        const ppp_innovation_meta_t *m=&meta[row];
        const step5_weight_t *w=&weights[row];
        const double *change=step5_delta[row];
        char sat[8]="-",signal[4]="-";
        int post_ok=0;
        double post_m=0.0;
        for(k=0;k<3;k++)sum[k]+=change[k];
        if(m->measurement_class==INNOV_GNSS_CODE || m->measurement_class==INNOV_GNSS_PHASE) {
            satno2id(m->sat,sat);
            snprintf(signal,sizeof(signal),"%s",code2obs(m->signal));
        }
        if(m->measurement_class==INNOV_GNSS_CODE) {
            const ppp_diag_signal_t *d=&diag->obs[m->source_obs_index][m->frequency_slot];
            post_ok=d->code_ok!=0;
            post_m=d->code_res;
        }
        if(step5_remove_sys && m->measurement_class!=INNOV_GNSS_PHASE)continue;
        if(step5_gate>0.0 && m->measurement_class!=INNOV_GNSS_CODE)continue;
        trace(2,"$S5_ROW,%d,%.9f,%d,%d,%s,%s,%d,%.17g,%.17g,%.17g,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%d\n",
            week,tow,trial,m->measurement_class,sat,signal,m->frequency_slot,
            change[0],change[1],change[2],post_ok,post_m,w->geom_factor,w->huber_factor,
            w->before,R[row+row*nv],w->dev,w->gim);
    }
    trace(2,"$S5_CLOSURE,%d,%.9f,%.17g,%.17g,%.17g\n",week,tow,
        rtk->x[0]-before[0]-sum[0],rtk->x[1]-before[1]-sum[1],rtk->x[2]-before[2]-sum[2]);
}

