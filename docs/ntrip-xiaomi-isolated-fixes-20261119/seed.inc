/* This replay process owns exactly one receiver and one session. */
typedef struct {
    gtime_t first, last;
    double seed[3], up[3], omission, recent[3], extra;
    int count, seed_done, confirm_done;
} seed_quality_t;
static seed_quality_t quality;

static double omission_up(const obsd_t *obs,int n,const double *rs,const double *dts,
    const double *vare,const int *svh,const nav_t *nav,const prcopt_t *opt,
    const ssat_t *ssat,const sol_t *sol,const int *accepted,const double *up)
{
    obsd_t clean[MAXOBS];
    double x[NX]={0}, v[MAXOBS+NX],H[NX*(MAXOBS+NX)],var[MAXOBS+NX];
    double azel[MAXOBS*2],resp[MAXOBS],dx[NX],Q[NX*NX],maximum=0.0;
    int used[MAXOBS],ns,nv;
    if(n>MAXOBS)return 0.0;
    memcpy(clean,obs,sizeof(*obs)*n);
    for(int i=0;i<n;i++)if(!accepted[i])memset(clean[i].P,0,sizeof(clean[i].P));
    for(int j=0;j<3;j++)x[j]=sol->rr[j];
    for(int j=3;j<NX;j++)x[j]=sol->dtr[j-3]*CLIGHT;
    nv=rescode(1,clean,n,rs,dts,vare,svh,nav,x,opt,ssat,v,H,var,azel,used,resp,&ns);
    if(nv<=NX || ns!=sol->ns)return 0.0;
    for(int i=0;i<n;i++)if((used[i]!=0)!=(accepted[i]!=0))return 0.0;
    for(int i=0;i<nv;i++){
        if(!isfinite(var[i]) || var[i]<=0)return 0.0;
        const double sigma=sqrt(var[i]); v[i]/=sigma;
        for(int j=0;j<NX;j++)H[j+i*NX]/=sigma;
    }
    if(lsq(H,v,NX,nv,dx,Q))return 0.0;
    for(int i=0;i<ns;i++){
        const double *h=H+i*NX;
        double qh[NX]={0};
        for(int j=0;j<NX;j++)for(int k=0;k<NX;k++)qh[j]+=Q[j+k*NX]*h[k];
        const double denominator=1.0-dot(h,qh,NX);
        if(denominator<=1e-8)continue; /* rank lost by that omission */
        const double shift=-dot(up,qh,3)*(v[i]-dot(h,dx,NX))/denominator;
        if(isfinite(shift) && fabs(shift)>maximum)maximum=fabs(shift);
    }
    return maximum;
}

static void observe_seed(const obsd_t *obs,int n,const double *rs,const double *dts,
    const double *vare,const int *svh,const nav_t *nav,const prcopt_t *opt,
    const ssat_t *ssat,const sol_t *sol,const int *accepted)
{
    const gtime_t now=obs[0].time;
    if(!quality.first.time){
        double llh[3];
        ecef2pos(sol->rr,llh);
        quality.up[0]=cos(llh[0])*cos(llh[1]);quality.up[1]=cos(llh[0])*sin(llh[1]);
        quality.up[2]=sin(llh[0]);
        memcpy(quality.seed,sol->rr,sizeof(quality.seed));
        quality.first=quality.last=now;
        quality.omission=omission_up(obs,n,rs,dts,vare,svh,nav,opt,ssat,sol,accepted,quality.up);
        trace(2,"$FIELD_SEED,%.9f,%.9f\n",time2gpst(now,NULL),quality.omission);
        return;
    }
    const double age=timediff(now,quality.first),dt=timediff(now,quality.last);
    if(age>10.0 || dt<=0.0 || quality.confirm_done || quality.extra>0.0)return;
    if(dt>1.5)quality.count=0;
    quality.last=now;
    double delta[3];
    for(int j=0;j<3;j++)delta[j]=sol->rr[j]-quality.seed[j];
    quality.recent[quality.count%3]=dot(quality.up,delta,3);
    if(++quality.count<3)return;
    double lo=quality.recent[0],hi=lo,sum=lo;
    for(int j=1;j<3;j++){
        const double a=quality.recent[j];if(a<lo)lo=a;if(a>hi)hi=a;sum+=a;
    }
    const double median=sum-lo-hi, gate=MAX(1.0,quality.omission*0.5);
    if(hi-lo<=gate && fabs(median)>gate){
        double sigma=fmin(15.0,fmin(quality.omission,fabs(median)));
        quality.extra=sigma*sigma;
        trace(2,"$FIELD_CONFIRM,%.9f,%.6f,%.6f,%.6f\n",time2gpst(now,NULL),median,hi-lo,quality.extra);
    }
}

/* Add only local-Up variance to the trial covariance. Consume on Q6 commit. */
int field_seed_covariance(gtime_t time,double *P,int nx,double *variance)
{
    *variance=0.0;
    if(!quality.first.time || timediff(time,quality.first)>10.0)return 0;
    int stage=0;
    if(!quality.seed_done){
        const double sigma=fmin(15.0,quality.omission);
        *variance=sigma*sigma;stage=1;
    } else if(!quality.confirm_done && quality.extra>0.0){
        *variance=quality.extra;stage=2;
    }
    for(int i=0;i<3;i++)for(int j=0;j<3;j++)
        P[i+j*nx]+=(*variance)*quality.up[i]*quality.up[j];
    return stage;
}
void field_finish_seed(int stage)
{
    if(stage==1)quality.seed_done=1;
    if(stage==2)quality.confirm_done=1;
}
