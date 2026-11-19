/* Invert only subblocks of the precision matrix for the currently admitted rows. */
static int use_block,use_consensus,restore_vertical,n_groups,agree_groups,affected_rows;
static double nominal_ku[FRESH_CAP],test_t[FRESH_CAP],test_z[FRESH_CAP],group_du[8];
static int test_df[FRESH_CAP];
static double model_terms[FRESH_CAP][7];
void midpoint_model(int row,double y_minus_raw,double range_minus_raw,double clk,double satclk,
                    double trop,double ion,double codebias)
{
    if(row<0 || row>=FRESH_CAP)abort();
    double *m=model_terms[row];m[0]=y_minus_raw;m[1]=range_minus_raw;m[2]=clk;
    m[3]=satclk;m[4]=trop;m[5]=ion;m[6]=codebias;
}
static void method_begin(const char *arm)
{
    use_block=arm && !strcmp(arm,"carry_block");
    use_consensus=arm && !strcmp(arm,"consensus");
    restore_vertical=n_groups=agree_groups=affected_rows=0;
    memset(group_du,0,sizeof(group_du));memset(test_df,0,sizeof(test_df));
}
static void code_block(const double *J,int m)
{
    const double chi95[]={0.,3.841459,5.991465,7.814728,9.487729};
    int done[MAXSAT+1]={0};
    for(int i=0;i<m;i++){
        int sat=fresh_rows[i].sat,ix[NFREQ],b=0;
        if(fresh_rows[i].kind!=INNOV_GNSS_CODE || done[sat])continue;
        done[sat]=1;
        for(int j=i;j<m;j++)if(fresh_rows[j].sat==sat && fresh_rows[j].kind==INNOV_GNSS_CODE){
            if(b>=NFREQ)abort();ix[b++]=j;
        }
        double A[NFREQ*NFREQ],res[NFREQ]={0},t=0.;
        for(int j=0;j<b;j++)for(int k=0;k<b;k++)A[j+b*k]=J[ix[j]+m*ix[k]];
        if(matinv(A,b))abort();
        for(int j=0;j<b;j++){
            for(int k=0;k<b;k++)res[j]+=A[j+b*k]*rr[ix[k]].score;
            t+=res[j]*rr[ix[j]].score;
        }
        for(int j=0;j<b;j++){
            int row=ix[j];double z=res[j]/sqrt(A[j+j*b]);
            test_t[row]=t;test_z[row]=z;test_df[row]=b;
            if(use_block && fresh_done && t>chi95[b] && fabs(z)>1.5)
                rr[row].factor=fmin(4.,fmax(t/chi95[b],z*z/2.25));
        }
    }
}
static void vertical_evidence(const double *J,const double *F,int n,int m)
{
    int marks[FRESH_CAP]={0},same=0;double first=0.;
    for(int i=0;i<m;i++)if(rr[i].factor>1.)affected_rows++;
    if(!use_consensus || !affected_rows)return;
    double um[FRESH_CAP];
    for(int j=0;j<m;j++){
        um[j]=0.;for(int a=0;a<3;a++)um[j]+=fresh_up[a]*F[s13_pos_index[a]+n*j];
    }
    for(int i=0;i<m;i++){nominal_ku[i]=0.;for(int j=0;j<m;j++)nominal_ku[i]+=um[j]*J[j+m*i];}
    for(int i=0;i<m;i++)if(rr[i].factor>1. && !marks[i]){
        int ix[FRESH_CAP],b=0;
        for(int j=i;j<m;j++)if(rr[j].factor>1. && fresh_rows[j].sys==fresh_rows[i].sys){ix[b++]=j;marks[j]=1;}
        double *A=mat(b,b),effect=0.;
        for(int j=0;j<b;j++)for(int k=0;k<b;k++)
            A[j+b*k]=J[ix[j]+m*ix[k]]+(j==k?1./((rr[ix[j]].factor-1.)*rr[ix[j]].r0):0.);
        if(matinv(A,b))abort();
        for(int j=0;j<b;j++)for(int k=0;k<b;k++)effect-=nominal_ku[ix[j]]*A[j+b*k]*rr[ix[k]].score;
        free(A);if(n_groups>=8)abort();group_du[n_groups++]=effect;
        if(fabs(effect)<=1.e-6)continue;
        if(first==0.)first=effect;if(first*effect>0.)same++;
    }
    agree_groups=n_groups>=2 && same==n_groups;restore_vertical=!agree_groups;
}
static void vertical_gain(double *K,int n,int m)
{
    if(!restore_vertical)return;
    for(int j=0;j<m;j++){
        double u=0.;for(int a=0;a<3;a++)u+=fresh_up[a]*K[s13_pos_index[a]+n*j];
        for(int a=0;a<3;a++)K[s13_pos_index[a]+n*j]+=fresh_up[a]*(nominal_ku[j]-u);
    }
}
static void midpoint_report(gtime_t t)
{
    int w;double tow=time2gpst(t,&w),age=fresh_first.time?timediff(t,fresh_first):0.;
    if(use_consensus && affected_rows)trace(2,"$MID_V,%d,%.9f,%d,%d,%d,%d,%d\n",w,tow,fresh_trial,
                                            affected_rows,n_groups,agree_groups,restore_vertical);
    if(age>=60.)return;
    for(int i=0;i<fresh_nv;i++)if(fresh_rows[i].kind==INNOV_GNSS_CODE){
        const double *m=model_terms[i];char sv[16];satno2id(fresh_rows[i].sat,sv);
        trace(2,"$MID_MODEL,%d,%.9f,%d,%d,%s,%s,%d,%.15g,%.15g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g,%.17g\n",
              w,tow,fresh_trial,i,sv,code2obs(fresh_rows[i].signal),test_df[i],test_t[i],test_z[i],
              m[0],m[1],m[2],m[3],m[4],m[5],m[6]);
    }
}
