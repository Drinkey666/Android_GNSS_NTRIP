/* Private replay, one receiver/session per process. Row class follows ppp_innovation_diag.h. */
#include "ppp_innovation_diag.h"
#define FRESH_CAP (2*NFREQ*MAXOBS+MAXSAT+16)
typedef struct { int sat,sys,signal,slot,kind,chosen; double hz,du,w,g,kv[3]; } fresh_row_t;
static fresh_row_t fresh_rows[FRESH_CAP];
static unsigned char fresh_seen[MAXSAT+1];
static gtime_t fresh_first;
static int fresh_done,fresh_nv,fresh_trial,fresh_n;
static double fresh_up[3],fresh_var,fresh_b,fresh_posterior,fresh_clock_leak;

void fresh_prepare(gtime_t time,int trial,const double *x,const double *H,const double *R,
                   int nx,int nv,const ppp_innovation_meta_t *meta,double sigma,int enabled)
{
    int chosen[MAXSAT+1];
    if(nv>FRESH_CAP || !meta)abort();
    fresh_nv=nv;fresh_trial=trial;fresh_n=0;
    fresh_var=fresh_b=fresh_posterior=fresh_clock_leak=0.0;
    memset(fresh_rows,0,nv*sizeof(*fresh_rows));
    for(int s=0;s<=MAXSAT;s++)chosen[s]=-1;
    double llh[3];ecef2pos(x,llh);
    fresh_up[0]=cos(llh[0])*cos(llh[1]);fresh_up[1]=cos(llh[0])*sin(llh[1]);fresh_up[2]=sin(llh[0]);
    const double age=fresh_first.time?timediff(time,fresh_first):-1.0;
    const int active=enabled && !fresh_done && age>0.0 && age<60.0 && sigma>0.0;
    for(int i=0;i<nv;i++){
        const ppp_innovation_meta_t *m=meta+i;fresh_row_t *r=fresh_rows+i;
        r->sat=m->sat;r->sys=m->sys;r->slot=m->frequency_slot;r->signal=m->signal;
        r->kind=m->measurement_class;r->hz=m->frequency_hz;
        if(!active || r->kind!=INNOV_GNSS_CODE || r->sat<1 || r->sat>MAXSAT ||
           fresh_seen[r->sat] || r->hz<=0.0 || R[i+i*nv]<=0.0)continue;
        int last=chosen[r->sat];
        if(last>=0 && fresh_rows[last].slot<=r->slot)continue;
        chosen[r->sat]=i;r->du=dot(fresh_up,H+i*nx,3);r->w=1.0/R[i+i*nv];
    }
    if(!active)return;
    int contrasts=0;
    for(int s=1;s<=MAXSAT;s++)if(chosen[s]>=0){
        fresh_row_t *r=fresh_rows+chosen[s];
        if(r->chosen)continue;
        double sw=0.0,sh=0.0,spread=0.0,leak=0.0;int count=0;
        for(int k=s;k<=MAXSAT;k++)if(chosen[k]>=0){
            fresh_row_t *v=fresh_rows+chosen[k];
            if(v->sys!=r->sys || v->signal!=r->signal)continue;
            count++;sw+=v->w;sh+=v->w*v->du;
        }
        if(!count)continue;
        const double mean=sh/sw;
        for(int k=s;k<=MAXSAT;k++)if(chosen[k]>=0){
            fresh_row_t *v=fresh_rows+chosen[k];
            if(v->sys==r->sys && v->signal==r->signal){
                v->chosen=1;spread+=v->w*SQR(v->du-mean);
            }
        }
        if(count<2 || sqrt(spread/sw)<0.10)continue;
        for(int k=s;k<=MAXSAT;k++)if(chosen[k]>=0){
            fresh_row_t *v=fresh_rows+chosen[k];
            if(v->sys==r->sys && v->signal==r->signal){
                v->g=v->du-mean;leak+=v->w*v->g;fresh_n++;
            }
        }
        contrasts+=count-1;fresh_clock_leak=fmax(fresh_clock_leak,fabs(leak)/sw);
    }
    if(contrasts>=2)fresh_var=sigma*sigma;
}

/* Augment the observation model with a scalar startup vertical correction b.
 * Cov(x,b)=0 a priori. Output y=x+up*b. Original observations are used once. */
static void fresh_innovation(double *S,int m)
{
    for(int i=0;i<m;i++)for(int j=0;j<m;j++)
        S[i+j*m]+=fresh_var*fresh_rows[i].g*fresh_rows[j].g;
}
static void fresh_cross(double *F,int n,int m)
{
    for(int a=0;a<3;a++)for(int j=0;j<m;j++)
        F[s13_pos_index[a]+j*n]+=fresh_up[a]*fresh_var*fresh_rows[j].g;
}
static void fresh_bias(const double *Sinv,const double *v,int m)
{
    fresh_posterior=fresh_var;
    for(int j=0;j<m;j++){
        double bgain=0.0;
        for(int i=0;i<m;i++)bgain+=fresh_var*fresh_rows[i].g*Sinv[i+j*m];
        fresh_b+=bgain*v[j];
        fresh_posterior-=bgain*fresh_var*fresh_rows[j].g;
    }
}
static void fresh_joseph(double *Pp,const double *K,int n,int m,double *work)
{
    for(int i=0;i<n;i++){
        work[i]=0.0;
        for(int a=0;a<3;a++)if(i==s13_pos_index[a])work[i]=fresh_up[a];
        for(int j=0;j<m;j++)work[i]-=K[i+j*n]*fresh_rows[j].g;
    }
    for(int i=0;i<n;i++)for(int j=0;j<n;j++)Pp[i+j*n]+=fresh_var*work[i]*work[j];
}
void fresh_commit(gtime_t t,int q)
{
    int w;double tow=time2gpst(t,&w);
    if(q==SOLQ_PPP && !fresh_first.time)fresh_first=t;
    if(fresh_var>0){
        fresh_done=1;
        trace(2,"$NEW_EVENT,%d,%.9f,%d,%d,%d,%.12g,%.15g,%.12g,%.12g\n",w,tow,q,
              fresh_trial,fresh_n,fresh_var,fresh_b,fresh_posterior,fresh_clock_leak);
    }
    for(int i=0;i<fresh_nv;i++){
        const fresh_row_t *r=fresh_rows+i;
        char sat[16]="-";
        if(r->sat>0 && r->sat<=MAXSAT){
            satno2id(r->sat,sat);
            if(r->kind==INNOV_GNSS_CODE)fresh_seen[r->sat]=1;
        }
        if(q==SOLQ_PPP)trace(2,"$NEW_ROW,%d,%.9f,%d,%d,%d,%s,%s,%d,%.3f,%.12g,%.17g,%.17g,%.17g\n",
            w,tow,fresh_trial,i,r->kind,sat,r->signal?code2obs(r->signal):"-",r->slot,r->hz,
            fresh_var>0?r->g:0.,r->kv[0],r->kv[1],r->kv[2]);
    }
}
