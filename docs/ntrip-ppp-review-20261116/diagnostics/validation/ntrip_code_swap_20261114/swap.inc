/* Private single-session replay hook. Apply only code values after SSR admission. */
typedef struct {
    int week, second;
    char sat[8], signal[8];
    double tow, target, delta;
} swap_row_t;

static int swap_codes(obsd_t *obs,int n)
{
    static FILE *input, *log;
    static int initialized, pending;
    static swap_row_t row;
    const char *path;
    int week, second;
    double tow;
    if(!initialized) {
        char header[256];
        initialized=1;
        path=getenv("NTRIP_PRIVATE_SWAP_TABLE");
        if(!path)return 1;
        input=fopen(path,"r");
        path=getenv("NTRIP_PRIVATE_SWAP_LOG");
        if(!input||!path||!(log=fopen(path,"w"))||!fgets(header,sizeof(header),input))return 0;
        fputs("week,tow,sat,signal,original_P_m,delta_m,transferred_P_m\n",log);
        pending=1;
        row.week=-1;
    }
    if(!input)return 1;
    tow=time2gpst(obs[0].time,&week);
    second=(int)floor(tow+0.5);
    while(pending && (row.week<week || (row.week==week && row.second<=second))) {
        if(row.week==week && row.second==second) {
            int i,f,found=0;
            for(i=0;i<n;i++) {
                char id[8];
                satno2id(obs[i].sat,id);
                if(strcmp(id,row.sat))continue;
                for(f=0;f<NFREQ;f++) {
                    double before=obs[i].P[f];
                    if(!obs[i].code[f]||strcmp(code2obs(obs[i].code[f]),row.signal))continue;
                    if(found||fabs(time2gpst(obs[i].time,NULL)-row.tow)>1e-6||
                        !isfinite(row.delta)||fabs(before-row.target)>1e-6||before+row.delta<=0)return 0;
                    obs[i].P[f]=before+row.delta;
                    fprintf(log,"%d,%.9f,%s,%s,%.12f,%.9f,%.12f\n",
                        week,tow,row.sat,row.signal,before,row.delta,obs[i].P[f]);
                    found=1;
                }
            }
            if(!found)return 0;
        }
        {
            char line[256];
            double removed;
            pending=fgets(line,sizeof(line),input)!=NULL;
            if(pending && sscanf(line,"%d,%d,%7[^,],%7[^,],%lf,%lf,%lf,%lf",&row.week,
                &row.second,row.sat,row.signal,&row.tow,&row.target,&row.delta,&removed)!=8)return 0;
            if(!pending && ferror(input))return 0;
        }
    }
    return !ferror(log);
}
