/* Private M1_v4 experiment and committed gain observer. */
enum { S7_A=1,S7_STD,S7_TIGHT,S7_SF_ONLY,S7_ROWS=MAXOBS*2*NFREQ+MAXSAT+3 };
typedef struct {
    int codes,has_phase,peers,df_peers,gim;
    double checked,center,scale,gate,dev,multiplier,original_r;
} s7_row_t;
static int s7_gain_count,s7_pos_row[3];
static double s7_delta[S7_ROWS][3];

static int s7_scheme(void)
{
    const char *s=getenv("STEP7_SCHEME");
    if(!s)return 0;
    if(!strcmp(s,"A"))return S7_A;
    if(!strcmp(s,"M1_v4_std"))return S7_STD;
    if(!strcmp(s,"M1_v4_tight"))return S7_TIGHT;
    if(!strcmp(s,"M1_v4_sf_only"))return S7_SF_ONLY;
    return 0;
}

extern void s7_active_indices(const int *ix,int n)
{
    int i;
    if(!s7_gain_count)return;
    s7_pos_row[0]=s7_pos_row[1]=s7_pos_row[2]=-1;
    for(i=0;i<n;i++)if(ix[i]>=0 && ix[i]<3)s7_pos_row[ix[i]]=i;
}

extern void s7_capture_gain(const double *K,const double *v,int n,int m)
{
    int i,k;
    if(!s7_gain_count || m!=s7_gain_count)return;
    for(i=0;i<m;i++)for(k=0;k<3;k++) {
        int j=s7_pos_row[k];
        s7_delta[i][k]=j>=0 ? K[j+i*n]*v[i] : 0.0;
    }
}

static int s7_reference_code(const ppp_innovation_meta_t *m)
{
    if(m->measurement_class!=INNOV_GNSS_CODE || m->frequency_slot!=0)return 0;
    return ((m->sys==SYS_GPS || m->sys==SYS_GAL) && m->signal==CODE_L1C) ||
           (m->sys==SYS_CMP && m->signal==CODE_L2I);
}

static double s7_gate(int scheme,const s7_row_t *a,double scale)
{
    if(scheme==S7_A)return a->has_phase ? MAX(3.0,2.5*scale) : 2.0;
    if(a->codes>=2)return scheme==S7_TIGHT ? MAX(3.0,2.3*scale) : MAX(3.2,2.5*scale);
    if(!a->has_phase)return MAX(2.0,1.8*scale);
    return scheme==S7_TIGHT ? MAX(2.4,2.0*scale) : MAX(2.6,2.2*scale);
}

static void s7_apply(int scheme,const rtk_t *rtk,const obsd_t *obs,int n,const nav_t *nav,
    const double *xp,const double *dr,const double *azel,const double *v,double *R,
    const ppp_innovation_meta_t *meta,int nv,s7_row_t *audit)
{
    const prcopt_t *opt=&rtk->opt;
    unsigned int slots[MAXSAT]={0};
    unsigned char codes[MAXSAT]={0},phase[MAXSAT]={0},grouped[S7_ROWS]={0};
    int i,j;
    double rr[3],pos[3];
    for(i=0;i<3;i++)rr[i]=xp[i]+dr[i];
    ecef2pos(rr,pos);
    memset(audit,0,(size_t)nv*sizeof(*audit));

    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=meta+i;
        if(m->measurement_class==INNOV_GNSS_PHASE)phase[m->sat-1]=1;
        if(m->measurement_class==INNOV_GNSS_CODE && !(slots[m->sat-1]&(1U<<m->frequency_slot))) {
            slots[m->sat-1]|=1U<<m->frequency_slot;
            codes[m->sat-1]++;
        }
    }
    for(i=0;i<nv;i++) {
        const ppp_innovation_meta_t *m=meta+i;
        s7_row_t *a=audit+i;
        if(m->measurement_class!=INNOV_GNSS_CODE)continue;
        a->codes=codes[m->sat-1];
        a->has_phase=phase[m->sat-1];
        a->original_r=R[i+i*nv];
        a->multiplier=1.0;
        a->checked=v[i];
        if(s7_reference_code(m) && (scheme!=S7_A || a->codes==1) && m->frequency_hz>0.0) {
            const int oi=m->source_obs_index;
            double ion,var;
            if(oi>=0 && oi<n && ionex_vertical_prior(obs[oi].time,nav,pos,azel+oi*2,opt,&ion,&var)) {
                const double alpha=a->codes==1 ? 1.0 : 0.5;
                const double l1=ppp_iono_mapf(nav,pos,azel+oi*2)*(xp[II(m->sat,opt)]-ion);
                const double corrected=v[i]+alpha*SQR(FREQL1/m->frequency_hz)*l1;
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
        double all[MAXSAT],dual[MAXSAT],med,scale,*sample;
        int np=0,nd=0,ns;
        if(grouped[i] || !s7_reference_code(m))continue;
        for(j=i;j<nv;j++) {
            const ppp_innovation_meta_t *g=meta+j;
            if(!s7_reference_code(g) || g->sys!=m->sys || g->signal!=m->signal)continue;
            grouped[j]=1;
            if(distinct[g->sat-1])continue;
            distinct[g->sat-1]=1;
            all[np++]=audit[j].checked;
            if(audit[j].codes>=2)dual[nd++]=audit[j].checked;
        }
        sample=scheme==S7_A && nd>=2 ? dual : all;
        ns=sample==dual ? nd : np;
        med=ppp_median(sample,ns);
        if(scheme!=S7_A && nd>=4)med=0.5*(med+ppp_median(dual,nd));
        for(j=0;j<ns;j++)sample[j]=fabs(sample[j]-med);
        scale=1.4826*ppp_median(sample,ns);
        scale=scheme==S7_A ? MIN(2.2,MAX(scale,1.2)) :
            MIN(scheme==S7_TIGHT?1.5:1.6,MAX(scale,1.1));
        for(j=i;j<nv;j++) {
            const ppp_innovation_meta_t *g=meta+j;
            s7_row_t *a=audit+j;
            int eligible=scheme==S7_A ? a->codes==1 || !a->has_phase : scheme!=S7_SF_ONLY || a->codes==1;
            if(!s7_reference_code(g) || g->sys!=m->sys || g->signal!=m->signal)continue;
            a->peers=np;
            a->df_peers=nd;
            if(np<4)continue;
            a->center=med;
            a->scale=scale;
            a->gate=s7_gate(scheme,a,scale);
            a->dev=fabs(a->checked-med);
            if(eligible && a->dev>a->gate) {
                a->multiplier=MIN(36.0,SQR(a->dev/a->gate));
                R[j+j*nv]*=a->multiplier;
            }
        }
    }
}

static void s7_report(const rtk_t *rtk,const obsd_t *obs,int nv,
    const ppp_innovation_meta_t *meta,const double *v,const double *R,
    const double *before,const s7_row_t *audit)
{
    double sum[3]={0};
    int row,k,week;
    const double tow=time2gpst(obs[0].time,&week);
    for(row=0;row<nv;row++) {
        const ppp_innovation_meta_t *m=meta+row;
        const s7_row_t *a=audit+row;
        const double *d=s7_delta[row];
        char sat[8];
        for(k=0;k<3;k++)sum[k]+=d[k];
        if(m->measurement_class!=INNOV_GNSS_CODE)continue;
        satno2id(m->sat,sat);
        trace(2,"$S7_CODE,%d,%.9f,%s,%s,%d,%d,%d,%d,%d,%d,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n",
            week,tow,sat,code2obs(m->signal),m->frequency_slot,a->codes,a->has_phase,a->peers,a->df_peers,a->gim,
            v[row],a->checked,a->center,a->scale,a->gate,a->dev,a->multiplier,a->original_r,R[row+row*nv],
            d[0],d[1],d[2]);
    }
    trace(2,"$S7_CLOSURE,%d,%.9f,%.17g,%.17g,%.17g\n",week,tow,
        rtk->x[0]-before[0]-sum[0],rtk->x[1]-before[1]-sum[1],rtk->x[2]-before[2]-sum[2]);
}

