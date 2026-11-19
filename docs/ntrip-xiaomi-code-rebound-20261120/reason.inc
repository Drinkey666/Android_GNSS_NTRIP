/* Private single-receiver replay. History advances only on a committed Q6. */
typedef struct {
    int valid,slip,amb;
    double v,r0,peer,peer_v,peer_k,z,cond,precision,score,factor,gain[3],lift;
} reason_row_t;
typedef struct {gtime_t time; int sig,n,next; double z[20];} reason_history_t;
static reason_row_t rr[FRESH_CAP];
static reason_history_t rh[MAXSAT+1][NFREQ];
static gtime_t reason_time;
static double *effective_R,compressed_lift[MAXSAT*(NFREQ+2)+256];
static int reason_select,reason_carry,reason_lifts;
static int double_order(const void *a,const void *b)
{
    const double x=*(const double *)a,y=*(const double *)b;
    return (x>y)-(x<y);
}
static double middle(double *v,int n)
{
    qsort(v,n,sizeof(double),double_order);
    return (v[(n-1)/2]+v[n/2])*0.5;
}
void reason_start(gtime_t t,int nv,double *R,const ppp_innovation_meta_t *meta)
{
    const char *arm=getenv("FIELD_METHOD");
    reason_select=arm && !strcmp(arm,"selective");
    reason_carry=arm && !strcmp(arm,"carry");
    reason_time=t;effective_R=R;reason_lifts=0;
    memset(rr,0,nv*sizeof(*rr));
    for(int j=0;j<nv;j++){rr[j].r0=R[j+j*nv];rr[j].factor=1.;rr[j].amb=-1;rr[j].slip=meta[j].slip_flag;}
}
void reason_ambiguity(int j,int idx,const double *xyz_H)
{
    rr[j].amb=idx;rr[j].lift=-dot(xyz_H,fresh_up,3);
}
static void reason_compress(const int *ix,int n)
{
    if(n>(int)(sizeof(compressed_lift)/sizeof(*compressed_lift)))abort();
    memset(compressed_lift,0,n*sizeof(double));
    for(int a=0;a<3;a++)if(s13_pos_index[a]>=0)compressed_lift[s13_pos_index[a]]=fresh_up[a];
    if(!reason_carry || !fresh_var)return;
    for(int j=0;j<fresh_nv;j++)if(rr[j].amb>=0){
        int i=0;while(i<n && ix[i]!=rr[j].amb)i++;
        if(i==n || compressed_lift[i]!=0.)abort();
        compressed_lift[i]=rr[j].lift;reason_lifts++;
    }
}
static int same_signal(int i,int j)
{
    return i!=j && fresh_rows[i].sys==fresh_rows[j].sys && fresh_rows[i].signal==fresh_rows[j].signal &&
           fresh_rows[i].kind==fresh_rows[j].kind && fresh_rows[i].sat!=fresh_rows[j].sat;
}
static int reason_prefit(double *S,const double *v,int m)
{
    double *precision=mat(m,m);matcpy(precision,S,m,m);
    int info=matinv(precision,m);
    if(info){free(precision);return info;}
    for(int i=0;i<m;i++){
        const fresh_row_t *r=fresh_rows+i;reason_row_t *a=rr+i;
        if(r->kind!=INNOV_GNSS_CODE && r->kind!=INNOV_GNSS_PHASE)continue;
        double d=precision[i+i*m],score=0.,p[MAXOBS],e[MAXOBS];int peers=0;
        if(!(d>0.)){free(precision);return FILTER_NOT_PSD;}
        for(int j=0;j<m;j++){
            score+=precision[i+j*m]*v[j];
            if(same_signal(i,j)){if(peers>=MAXOBS)abort();p[peers]=rr[j].r0;e[peers++]=v[j];}
        }
        a->v=v[i];a->precision=d;a->score=score;a->cond=score/d;a->z=score/sqrt(d);
        a->peer=peers?middle(p,peers):NAN;a->peer_v=peers?middle(e,peers):NAN;
        if(!reason_select || r->kind!=INNOV_GNSS_CODE || peers<3 || a->r0>a->peer || a->slip)continue;
        const reason_history_t *h=&rh[r->sat][r->slot];
        double dt=timediff(reason_time,h->time);
        if(h->n<12 || h->sig!=r->signal || dt<=0 || dt>2.0)continue;
        double mean=0.;int agree=0;
        for(int k=0;k<h->n;k++){
            mean+=h->z[k]/h->n;if(h->z[k]*a->z>0)agree++;
        }
        if(agree*4<3*h->n || fabs(mean)<0.5 || fabs(a->z)<0.5 || mean*a->z<=0)continue;
        a->factor=fmin(4.,1.+2.*mean*mean);
    }
    for(int i=0;i<m;i++)if(rr[i].factor>1.){
        double add=(rr[i].factor-1.)*rr[i].r0;
        S[i+i*m]+=add;effective_R[i+i*m]+=add;
    }
    free(precision);return 0;
}
static void reason_report(gtime_t t,int q)
{
    if(q!=SOLQ_PPP)return;
    int week;const double tow=time2gpst(t,&week);
    for(int i=0;i<fresh_nv;i++){
        const fresh_row_t *r=fresh_rows+i;reason_row_t *a=rr+i;
        if(r->kind!=INNOV_GNSS_CODE && r->kind!=INNOV_GNSS_PHASE)continue;
        double peers[MAXOBS];int n=0;
        for(int j=0;j<fresh_nv;j++)if(same_signal(i,j)){if(n>=MAXOBS)abort();peers[n++]=fabs(dot(rr[j].gain,fresh_up,3));}
        a->peer_k=n?middle(peers,n):NAN;
        if(r->kind==INNOV_GNSS_CODE && reason_select){
            reason_history_t *h=&rh[r->sat][r->slot];double dt=timediff(t,h->time);
            if(h->sig!=r->signal || a->slip || dt<=0. || dt>2.0){h->n=h->next=0;}
            h->sig=r->signal;h->time=t;h->z[h->next]=fmax(-3.,fmin(3.,a->z));
            h->next=(h->next+1)%20;if(h->n<20)h->n++;
        }
        char sv[16];satno2id(r->sat,sv);
        trace(2,"$REASON,%d,%.9f,%d,%d,%d,%s,%s,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n",
              week,tow,fresh_trial,i,r->kind,sv,code2obs(r->signal),a->v,a->r0,a->peer,a->peer_v,
              a->z,a->cond,a->precision,a->factor,a->gain[0],a->gain[1],a->gain[2],a->peer_k,
              reason_carry && fresh_var?a->lift:0.);
    }
    if(reason_carry && fresh_var)trace(2,"$REASON_LIFT,%d,%.9f,%d,%d\n",week,tow,fresh_trial,reason_lifts);
}
