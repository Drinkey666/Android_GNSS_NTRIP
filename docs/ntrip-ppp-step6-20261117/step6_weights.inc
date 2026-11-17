/* M1_v3 isolated validation: one receiver session per replay process. */
enum { STEP6_ROWS=MAXOBS*2*NFREQ+MAXSAT+3 };
typedef struct {
    int codes, has_phase, peers, df_peers, gim;
    double checked, center, scale, gate, dev, huber, gps, original_r;
} step6_row_t;
static int step6_seen_q6;

static char step6_scheme(void)
{
    const char *setting=getenv("STEP6_SCHEME");
    return setting && setting[1]=='\0' && (*setting=='A'||*setting=='B'||*setting=='C') ? *setting : '\0';
}

static int step6_reference_code(const ppp_innovation_meta_t *row)
{
    if(row->measurement_class!=INNOV_GNSS_CODE || row->frequency_slot!=0)return 0;
    return ((row->sys==SYS_GPS || row->sys==SYS_GAL) && row->signal==CODE_L1C) ||
           (row->sys==SYS_CMP && row->signal==CODE_L2I);
}

static int step6_apply(char scheme,const rtk_t *rtk,const obsd_t *obs,int n,const nav_t *nav,
    const double *xp,const double *dr,const double *azel,const double *v,double *R,
    const ppp_innovation_meta_t *meta,int nv,step6_row_t *audit)
{
    const prcopt_t *opt=&rtk->opt;
    unsigned int slots[MAXSAT]={0};
    unsigned char code_count[MAXSAT]={0},phase[MAXSAT]={0},grouped[STEP6_ROWS]={0};
    int phase_sat=0,i,j;
    double rr[3],pos[3];
    for(i=0;i<3;i++)rr[i]=xp[i]+dr[i];
    ecef2pos(rr,pos);
    memset(audit,0,(size_t)nv*sizeof(*audit));

    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=meta+i;
        if(m->measurement_class==INNOV_GNSS_PHASE && !phase[m->sat-1]) {
            phase[m->sat-1]=1;
            phase_sat++;
        }
        if(m->measurement_class==INNOV_GNSS_CODE && !(slots[m->sat-1]&(1U<<m->frequency_slot))) {
            slots[m->sat-1]|=1U<<m->frequency_slot;
            code_count[m->sat-1]++;
        }
    }
    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=meta+i;
        step6_row_t *a=audit+i;
        if(m->measurement_class!=INNOV_GNSS_CODE)continue;
        a->codes=code_count[m->sat-1];
        a->has_phase=phase[m->sat-1];
        a->original_r=R[i+i*nv];
        a->huber=a->gps=1.0;
        a->checked=v[i];
        if(step6_reference_code(m) && a->codes==1 && m->frequency_hz>0.0) {
            const int oi=m->source_obs_index;
            double ion,var;
            if(oi>=0 && oi<n && ionex_vertical_prior(obs[oi].time,nav,pos,azel+oi*2,opt,&ion,&var)) {
                const double l1=ppp_iono_mapf(nav,pos,azel+oi*2)*(xp[II(m->sat,opt)]-ion);
                const double corrected=v[i]+SQR(FREQL1/m->frequency_hz)*l1;
                if(isfinite(corrected)) {
                    a->gim=1;
                    a->checked=corrected;
                }
            }
        }
    }

    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=meta+i;
        unsigned char distinct[MAXSAT]={0};
        double votes[MAXSAT],dual[MAXSAT],med,mad,scale;
        int np=0,nd=0,nv_ref;
        double *reference;
        if(grouped[i] || !step6_reference_code(m))continue;
        for(j=i;j<nv;j++) {
            const ppp_innovation_meta_t *g=meta+j;
            if(!step6_reference_code(g) || g->sys!=m->sys || g->signal!=m->signal)continue;
            grouped[j]=1;
            if(distinct[g->sat-1])continue;
            distinct[g->sat-1]=1;
            votes[np++]=audit[j].checked;
            if(audit[j].codes>=2)dual[nd++]=audit[j].checked;
        }
        reference=nd>=2 ? dual : votes;
        nv_ref=nd>=2 ? nd : np;
        med=ppp_median(reference,nv_ref);
        for(j=0;j<nv_ref;j++)reference[j]=fabs(reference[j]-med);
        mad=1.4826*ppp_median(reference,nv_ref);
        scale=MIN(2.2,MAX(mad,1.2));
        for(j=i;j<nv;j++) {
            const ppp_innovation_meta_t *g=meta+j;
            step6_row_t *a=audit+j;
            if(!step6_reference_code(g) || g->sys!=m->sys || g->signal!=m->signal)continue;
            a->peers=np;
            a->df_peers=nd;
            if(np<4)continue;
            a->center=med;
            a->scale=scale;
            a->gate=a->has_phase ? MAX(3.0,2.5*scale) : 2.0;
            a->dev=fabs(a->checked-med);
            if((a->codes==1 || !a->has_phase) && a->dev>a->gate) {
                a->huber=MIN(36.0,SQR(a->dev/a->gate));
            }
        }
    }

    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=meta+i;
        step6_row_t *a=audit+i;
        if(!step6_reference_code(m))continue;
        if(m->sys==SYS_GPS && a->codes==1) {
            if(scheme=='B')a->gps=2.5;
            else if(scheme=='C' && step6_seen_q6 && phase_sat>=6)a->gps=3.0;
        }
        if(a->huber>1.0 || a->gps>1.0)R[i+i*nv]*=a->huber*a->gps;
    }
    return phase_sat;
}

static void step6_log(const obsd_t *obs,int nv,int phase_sat,const double *v,const double *R,
                     const ppp_innovation_meta_t *meta,const step6_row_t *audit)
{
    int i,week;
    const double tow=time2gpst(obs[0].time,&week);
    trace(2,"$S6_EPOCH,%d,%.9f,%d,%d\n",week,tow,phase_sat,step6_seen_q6);
    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=meta+i;
        const step6_row_t *a=audit+i;
        char id[8];
        if(m->measurement_class!=INNOV_GNSS_CODE)continue;
        satno2id(m->sat,id);
        trace(2,"$S6_CODE,%d,%.9f,%s,%s,%d,%d,%d,%d,%d,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n",
            week,tow,id,code2obs(m->signal),m->frequency_slot,a->codes,a->has_phase,
            a->peers,a->df_peers,a->gim,v[i],a->checked,a->center,a->scale,a->gate,
            a->dev,a->huber,a->gps,a->original_r,R[i+i*nv]);
    }
}

