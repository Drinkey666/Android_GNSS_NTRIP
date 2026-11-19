/* One receiver/session per process. No position or time-of-day thresholds. */
typedef struct {
    gtime_t first,last;
    int n,slot[2],signal[2];
    double anchor[4],ring[5][4];
} field_arc_t;
typedef struct {double code[NFREQ],iono;} field_weight_t;
static field_arc_t field_arc[MAXSAT];
static field_weight_t field_w[MAXSAT];
static int field_collect,field_mature;
static int field_is(const char *name)
{
    const char *v=getenv("FIELD_METHOD");
    return v && !strcmp(v,name);
}
extern int field_seed_covariance(gtime_t time,double *P,int nx,double *variance);
extern void field_finish_seed(int stage);

static void field_observe(const rtk_t *rtk,const obsd_t *o,const nav_t *nav,int sys,
    const double *L,const double *P,const double *x,int gim_ok,double G,const unsigned char *edits)
{
    int s=o->sat-1,slot[2],n=0;
    const ssat_t *ss=rtk->ssat+s;
    field_arc_t *arc=field_arc+s;
    double a[2],z[4],change[4]={0};
    if(!gim_ok || !isfinite(G) || rtk->ppp_code_warmup){arc->n=0;return;}
    for(int f=0;f<NF(&rtk->opt)&&f<NFREQ&&n<2;f++){
        if(!o->code[f] || !P[f] || !L[f] || !isfinite(P[f]) || !isfinite(L[f]) ||
           !ppp_signal_supported(sys,f,o->code[f],&rtk->opt) ||
           (f && !ppp_code_modelled(sys,f,o->code[f],&rtk->opt)) ||
           ss->ppp_code_bad[f] || ss->ppp_arc_pending[f] || ss->ppp_arc_reset[f] ||
           ((ss->slip[f]|o->LLI[f])&LLI_SLIP) || ppp_phase_quarantined(ss,f,o->time) ||
           !x[IB(o->sat,f,&rtk->opt)] || (edits && (edits[2*f] || edits[2*f+1])))continue;
        const double freq=sat2freq(o->sat,o->code[f],nav);
        if(freq<=0)continue;
        const double scale=SQR(FREQL1/freq);
        if(n && fabs(scale-a[0])<0.1)continue;
        slot[n]=f;a[n]=scale;
        z[n]=P[f]-L[f]-2*scale*G;
        z[2+n]=L[f]+scale*G;
        n++;
    }
    if(n<2){arc->n=0;return;}
    const double dt=timediff(o->time,arc->last);
    if(arc->n && dt==0)return;
    if(!arc->n || dt<=0 || dt>1.5 || arc->slot[0]!=slot[0] || arc->slot[1]!=slot[1] ||
       arc->signal[0]!=o->code[slot[0]] || arc->signal[1]!=o->code[slot[1]]){
        memset(arc,0,sizeof(*arc));arc->first=o->time;
        for(int j=0;j<2;j++){arc->slot[j]=slot[j];arc->signal[j]=o->code[slot[j]];}
    }
    arc->last=o->time;
    for(int j=0;j<4;j++){
        arc->ring[arc->n%5][j]=z[j];
        if(arc->n<5)arc->anchor[j]+=z[j]/5.0;
    }
    arc->n++;
    if(arc->n<10 || timediff(o->time,arc->first)<20.0)return;
    field_mature++;
    for(int j=0;j<4;j++){
        for(int k=0;k<5;k++)change[j]+=arc->ring[k][j]/5.0;
        change[j]-=arc->anchor[j];
    }
    const double phase=change[2]-change[3];
    const double i0=change[0]/(2*a[0]),i1=change[1]/(2*a[1]);
    const double common=fmin(fabs(i0),fabs(i1)),diff=a[0]-a[1];
    if(i0*i1>0 && common>=0.5 && fabs(i0-i1)<=0.5 && fabs(phase)>=0.1 &&
       fabs(phase+diff*i0)<=0.15 && fabs(phase+diff*i1)<=0.15){
        field_w[s].iono=fmin(9.0,SQR(common/0.5));
    }else if(fabs(phase)<=0.15){
        for(int j=0;j<2;j++)if(fabs(change[j])>2.0 && fabs(change[1-j])<=1.0)
            field_w[s].code[slot[j]]=fmin(9.0,SQR(change[j]/2.0));
    }
}
static void field_apply(int nv,double *R,const ppp_innovation_meta_t *rows,
                        int *nc,int *ni,double *mc,double *mi)
{
    *nc=*ni=0;*mc=*mi=1.0;
    for(int j=0;j<nv;j++){
        const ppp_innovation_meta_t *m=rows+j;
        if(m->sat<1 || m->sat>MAXSAT)continue;
        const field_weight_t *w=field_w+m->sat-1;
        if(m->measurement_class==INNOV_GNSS_CODE && m->frequency_slot>=0 &&
           m->frequency_slot<NFREQ && w->code[m->frequency_slot]>1.0){
            const double f=w->code[m->frequency_slot];
            R[j+j*nv]*=f;(*nc)++;*mc=fmax(*mc,f);
        }else if(m->measurement_class==INNOV_IONO_PRIOR && w->iono>1.0){
            R[j+j*nv]*=w->iono;(*ni)++;*mi=fmax(*mi,w->iono);
        }
    }
}
