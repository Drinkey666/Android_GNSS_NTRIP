#include "ntrip_ssr.h"
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>

NtripSsr::~NtripSsr() {
    for(auto *d:decoder) if(d){free_rtcm(d);free(d);}
}
bool NtripSsr::init() {
    for(auto &d:decoder) {
        d=(rtcm_t*)calloc(1,sizeof(rtcm_t));
        if(!d || !init_rtcm(d))return false;
        strcpy(d->opt,"-EPHALL");
    }
    return true;
}
bool NtripSsr::useWhuOsb(const std::string &orbit,const std::string &bias,bool com) {
    if(orbit!="SSRC00WHU0"||bias!="OSBC00WHU1"||!com||frames[0]||frames[1]||frames[2]) {
        reason="WHU_PROFILE_ENDPOINT_OR_DATUM_INVALID";return false;
    }
    whu_osb=true;reason="WHU_OSB_BOOTSTRAP";return true;
}
bool NtripSsr::observeWhuBias(int sat,const ssr_t &s,gtime_t receipt) {
    auto &c=bias_continuity[sat];
    if(timediff(receipt,s.t0[4]) < -1.0) {
        blocked=true;reason="WHU_OSB_FUTURE_EPOCH";return false;
    }
    if(c.epoch.time) {
        const double step=timediff(s.t0[4],c.epoch);
        if(step<0){blocked=true;reason="WHU_OSB_EPOCH_REGRESSION";return false;}
        if(timediff(receipt,c.received)>90.0) {
            c.consecutive=false;c.epoch=s.t0[4];c.received=c.advanced=receipt;return true;
        }
        if(step>0) {
            // Observe a NEW completed estimate, not just another copy of old bytes.
            c.consecutive=std::fabs(step-WHU_ESTIMATION_SECONDS)<1e-6 &&
                timediff(receipt,c.received)<=90.0;
            c.advanced=receipt;
        }
    } else c.advanced=receipt;
    c.epoch=s.t0[4];c.received=receipt;return true;
}
void NtripSsr::resetTransport(int channel) {
    if(channel<0||channel>2||!decoder[channel])return;
    auto *r=decoder[channel];r->nbyte=r->nbyte_invalid=0;
    frame_buffer[channel].clear();
    /* Roll back uncompleted multiple-message updates on reconnect. */
    if(channel!=1)memcpy(r->ssr,transport_committed[channel],sizeof(committed));
    if(whu_osb && channel==2) {
        // A transport discontinuity cannot use repeated old packets to re-establish trust.
        for(auto &c:bias_continuity)c=BiasContinuity{};
    }
}
void NtripSsr::setReference(nav_t *nav) {
    const int index[]={0,2,3};
    const int first[]={CODE_L1W,CODE_L1C,CODE_L2I};
    const int second[]={CODE_L2W,CODE_L5Q,CODE_L6I};
    const int a[]={1,1,2},b[]={2,5,6};
    for(int k=0;k<3;k++) {
        int i=index[k];nav->clock_ref_status[i]=1;
        nav->clock_ref_code[i][0]=first[k];nav->clock_ref_code[i][1]=second[k];
        nav->clock_ref_antex[i][0]=a[k];nav->clock_ref_antex[i][1]=b[k];
    }
}
void NtripSsr::mergeEphemeris(nav_t *nav,const rtcm_t *r) {
    /* GLONASS remains disabled in B_VERIFIED. Retain 4 versions per satellite,
     * bounded by 4*MAXSAT; SSR can still reference the previous broadcast IOD. */
    if(r->ephsat<1||r->ephsat>MAXSAT)return;
    const eph_t &e=r->nav.eph[r->ephsat-1+MAXSAT*r->ephset];
    if(!e.sat || !std::isfinite(e.A)||e.A<=0)return;
    int count=0,oldest=-1;
    for(int i=0;i<nav->n;i++) if(nav->eph[i].sat==e.sat) {
        if(nav->eph[i].iode==e.iode && nav->eph[i].code==e.code &&
           std::fabs(timediff(nav->eph[i].toe,e.toe))<1.0){nav->eph[i]=e;return;}
        count++;
        if(oldest<0 || timediff(nav->eph[i].toe,nav->eph[oldest].toe)<0)oldest=i;
    }
    if(count>=4){nav->eph[oldest]=e;return;}
    if(nav->n>=nav->nmax) {
        int cap=nav->n+MAXSAT;
        auto *p=(eph_t*)realloc(nav->eph,sizeof(eph_t)*cap);
        if(!p){reason="EPHEMERIS_ALLOCATION_FAILED";blocked=true;return;}
        nav->eph=p;nav->nmax=cap;
    }
    nav->eph[nav->n++]=e;
}
void NtripSsr::feed(nav_t *nav,int channel,const unsigned char *data,int count,gtime_t anchor) {
    if(channel<0||channel>2||!decoder[channel]||blocked)return;
    if(count<=0)return;
    if(!data || count>16384){blocked=true;reason="RTCM_INPUT_CHUNK_INVALID";return;}
    auto *r=decoder[channel];
    r->time=anchor; // only week/day disambiguation; message epoch is decoded from payload
    auto &pending=frame_buffer[channel];
    pending.insert(pending.end(),data,data+count);
    while(pending.size()>=3) {
        if(pending[0]!=0xD3 || (pending[1]&0xFC)){pending.erase(pending.begin());continue;}
        const size_t total=(((pending[1]&3)<<8)|pending[2])+6;
        if(pending.size()<total)break;
        if(rtk_crc24q(pending.data(),(int)total-3)!=getbitu(pending.data(),((int)total-3)*8,24)) {
            crc_errors[channel]++;pending.erase(pending.begin());continue;
        }
        // input_rtcm3f rewinds after a false preamble/CRC failure. A socket cannot
        // rewind: retain the bounded fragment here and pass complete validated frames.
        int ret=0;r->nbyte=r->nbyte_invalid=0;
        for(size_t i=0;i<total;i++)ret=input_rtcm3(r,pending[i]);
        frames[channel]++;
        const int type=(int)getbitu(pending.data(),24,12);
        if(ret>=0 && type>=1258 && type<=1263) {
            /* Standard RTCM BDS DF465 is BDT seconds-of-week. This bundled
             * RTKLIB decoder uses adjweek() without BDT->GPST conversion.
             * Normalize decoded fields once at the boundary; raw bytes remain
             * untouched. IGS 4076 BDS already uses GPST and MUST NOT enter here.
             * Compare against the just-decoded epoch so old multipart fields
             * are not shifted again when another BDS frame is received. */
            const int family=type-1258;
            for(int sat=0;sat<MAXSAT;sat++)if(satsys(sat+1,nullptr)==SYS_CMP) {
                for(int k:{0,1,2,3,4}) {
                    const bool field=(family==0&&k==0)||(family==1&&k==1)||(family==2&&k==4)||
                        (family==3&&(k==0||k==1))||(family==4&&k==3)||(family==5&&k==2);
                    if(field&&r->ssr[sat].t0[k].time&&std::fabs(timediff(r->ssr[sat].t0[k],r->time))<1e-7)
                        r->ssr[sat].t0[k]=bdt2gpst(r->ssr[sat].t0[k]);
                }
            }
            r->time=bdt2gpst(r->time);
        }
        const int subtype=type==4076?(int)getbitu(pending.data(),39,8):0;
        const bool code_message=type==1059||type==1065||type==1242||type==1248||type==1254||type==1260||
            (type==4076&&(subtype==25||subtype==45||subtype==65||subtype==85||subtype==105||subtype==125));
        if(channel!=1 && type==4076 && getbitu(pending.data(),36,3)!=1) {
            blocked=true;reason="IGS_SSR_VERSION_UNSUPPORTED";return;
        }
        pending.erase(pending.begin(),pending.begin()+total);
        if(ret<0){decode_errors[channel]++;if(channel==0)reason="RTCM_DECODE_ERROR";continue;}
        messages[channel]++;
        if(ret==2)mergeEphemeris(nav,r);
        if(channel==1 || ret!=10)continue; // commit only a complete SSR message sequence
        for(int sat=0;sat<MAXSAT;sat++) {
            if(!r->ssr[sat].update)continue;
            const auto &s=r->ssr[sat];
            transport_committed[channel][sat]=s;
            transport_committed[channel][sat].update=0;
            /* Header provider/solution must be stable throughout this session.
             * A change requires an explicit new filter session, not stale arcs. */
            int &pid=channel==2?bias_provider:provider;
            int &sid=channel==2?bias_solution:solution;
            for(int k: {0,1,4})if(s.t0[k].time && (channel==0 || k==4)) {
                if(pid<0){pid=s.provider[k];sid=s.solution[k];}
                if(pid!=s.provider[k]||sid!=s.solution[k]) {
                    blocked=true;reason="SSR_PROVIDER_CHANGED_RESTART_REQUIRED";return;
                }
            }
            if(whu_osb) {
                for(int k:{0,1})if(channel==0 && s.t0[k].time) {
                    if(whu_orbit_iod<0)whu_orbit_iod=s.iod[k];
                    if(whu_orbit_iod!=s.iod[k]){blocked=true;reason="WHU_ORBIT_CONFIG_CHANGED_RESTART_REQUIRED";return;}
                }
                if(channel==2 && s.t0[4].time) {
                    if(!code_message){blocked=true;reason="WHU_BIAS_TRANSPORT_WRONG_MESSAGE";return;}
                    if(whu_bias_iod<0)whu_bias_iod=s.iod[4];
                    if(whu_bias_iod!=s.iod[4]){blocked=true;reason="WHU_BIAS_CONFIG_CHANGED_RESTART_REQUIRED";return;}
                    if(!observeWhuBias(sat,s,anchor))return;
                }
            }
            auto &target=committed[sat];
            if(channel==0) {
                // Independent bias transport must not erase orbit/clock or vice versa.
                const auto previous=target;target=s;
                if(!s.t0[4].time && previous.t0[4].time) {
                    target.t0[4]=previous.t0[4];target.udi[4]=previous.udi[4];target.iod[4]=previous.iod[4];
                    target.provider[4]=previous.provider[4];target.solution[4]=previous.solution[4];
                    memcpy(target.cbias,previous.cbias,sizeof(target.cbias));
                    memcpy(target.cbias_valid,previous.cbias_valid,sizeof(target.cbias_valid));
                }
            } else if(s.t0[4].time) {
                target.t0[4]=s.t0[4];target.udi[4]=s.udi[4];target.iod[4]=s.iod[4];
                target.provider[4]=s.provider[4];target.solution[4]=s.solution[4];
                memcpy(target.cbias,s.cbias,sizeof(target.cbias));
                memcpy(target.cbias_valid,s.cbias_valid,sizeof(target.cbias_valid));
            }
            // coherent() still enforces matching identity/IOD and the existing age bound.
            // Receiving a second source is not permission to relax these guards.
            r->ssr[sat].update=0;
        }
    }
}
bool NtripSsr::usable(int sat,gtime_t epoch,std::string *why) const {
    if(sat<1||sat>MAXSAT){if(why)*why="SATELLITE_INVALID";return false;}
    const auto &s=committed[sat-1];
    if(!whu_osb)return coherent(s,epoch,why);
    const auto &c=bias_continuity[sat-1];const char *problem=nullptr;
    if(blocked)problem="WHU_SESSION_BLOCKED";
    else if(!s.t0[0].time||!s.t0[1].time||!s.t0[4].time)problem="MISSING_ORBIT_CLOCK_CODE_BIAS";
    else if(s.refd)problem="REGIONAL_DATUM_UNSUPPORTED";
    else if(s.iod[0]!=s.iod[1])problem="SSR_ORBIT_CLOCK_IOD_MISMATCH";
    else if(s.provider[0]!=s.provider[1]||s.solution[0]!=s.solution[1])problem="SSR_ORBIT_CLOCK_IDENTITY_MISMATCH";
    else for(int k:{0,1}) {
        const double age=timediff(epoch,s.t0[k]);
        if(age < -1.0){problem="FUTURE_SSR";break;}
        if(age > 90.0){problem="SSR_EXPIRED";break;}
    }
    if(!problem && (!c.consecutive||!c.received.time))problem="WHU_OSB_WAIT_NEXT_ESTIMATE";
    if(!problem && (s.provider[4]!=bias_provider||s.solution[4]!=bias_solution||
        s.iod[4]!=whu_bias_iod||std::fabs(timediff(s.t0[4],c.epoch))>1e-6))problem="WHU_CODE_BIAS_COMPONENT_MISMATCH";
    if(!problem && timediff(epoch,s.t0[4]) < -1.0)problem="FUTURE_SSR";
    if(!problem && timediff(epoch,c.received) < -1.0)problem="WHU_RECEIPT_CLOCK_MISMATCH";
    if(!problem && timediff(epoch,c.received)>90.0)problem="WHU_OSB_TRANSPORT_STALE";
    if(!problem && timediff(epoch,c.advanced)>WHU_ESTIMATION_SECONDS+WHU_SENDING_SECONDS)
        problem="WHU_OSB_ESTIMATE_NOT_ADVANCING";
    if(!problem)for(int k=0;k<3;k++)if(!std::isfinite(s.deph[k])||!std::isfinite(s.ddeph[k])||!std::isfinite(s.dclk[k])){problem="NONFINITE_SSR";break;}
    if(why)*why=problem?problem:"READY_WHU_OSB_CONTINUITY";
    return !problem;
}
bool NtripSsr::coherent(const ssr_t &s,gtime_t epoch,std::string *why) {
    const char *problem=nullptr;
    if(!s.t0[0].time||!s.t0[1].time||!s.t0[4].time)problem="MISSING_ORBIT_CLOCK_CODE_BIAS";
    else if(s.refd)problem="REGIONAL_DATUM_UNSUPPORTED";
    else if(s.iod[0]!=s.iod[1]||s.iod[0]!=s.iod[4])problem="SSR_IOD_MISMATCH";
    else if(s.provider[0]!=s.provider[1]||s.provider[0]!=s.provider[4]||
            s.solution[0]!=s.solution[1]||s.solution[0]!=s.solution[4])problem="SSR_IDENTITY_MISMATCH";
    else for(int k:{0,1,4}) {
        double age=timediff(epoch,s.t0[k]);
        /* Same 90 s hard ceiling as ephemeris.c::MAXAGESSR, with matching
         * IOD/provider/solution. UDI is an update interval, not a documented
         * 2*UDI expiry: do not invent that shorter validity from cadence.
         * Code biases use the same explicit conservative session ceiling.
         * The 1 s future tolerance covers transmit-time/epoch rounding. */
        double limit=90.0;
        if(age < -1.0){problem="FUTURE_SSR";break;}
        if(age>limit){problem="SSR_EXPIRED";break;}
    }
    if(!problem) for(int k=0;k<3;k++) {
        if(!std::isfinite(s.deph[k])||!std::isfinite(s.ddeph[k])||!std::isfinite(s.dclk[k])) {
            problem="NONFINITE_SSR";break;
        }
    }
    if(why)*why=problem?problem:"READY";
    return !problem;
}
int NtripSsr::prepare(nav_t *nav,const prcopt_t *opt,gtime_t epoch,obsd_t *obs,int n) {
    accepted_satellites=accepted_codes=0;
    memset(nav->ssr,0,sizeof(nav->ssr));
    if(blocked)return 0;
    int out=0;bool whu_pending=false;
    for(int i=0;i<n;i++) {
        int sat=obs[i].sat;
        if(sat<1||sat>MAXSAT||!(satsys(sat,nullptr)&opt->navsys))continue;
        ssr_t s=committed[sat-1];std::string why;
        if(!usable(sat,epoch,&why)){reason=why;if(why=="WHU_OSB_WAIT_NEXT_ESTIMATE")whu_pending=true;continue;}
        /* Auxiliary HRCLK/URA are optional and must not cross an identity/IOD. */
        for(int k:{2,3,5})if(s.iod[k]!=s.iod[0]||s.provider[k]!=s.provider[0]||
            s.solution[k]!=s.solution[0] || timediff(epoch,s.t0[k]) < -1.0 ||
            timediff(epoch,s.t0[k])>(k==2?10.0:90.0)) {
            s.t0[k]={};if(k==3)s.ura=0;
        }
        nav->ssr[sat-1]=s;
        const int system=satsys(sat,nullptr);
        const int ix=system==SYS_GPS?0:system==SYS_GAL?2:system==SYS_CMP?3:-1;
        double refpco[3]{};
        if(ix<0 || !pcv_antex_if_pco(nav->pcvs+sat-1,
            nav->clock_ref_antex[ix][0],nav->clock_ref_antex[ix][1],
            sat2freq(sat,nav->clock_ref_code[ix][0],nav),
            sat2freq(sat,nav->clock_ref_code[ix][1],nav),refpco)) {
            reason="SSR_REFERENCE_ANTEX_MISSING";continue;
        }
        double rs[6]{},dts[2]{},variance=0;int health=0;
        /* This validates broadcast IOD, age, orbit/clock magnitude and APC.
         * Approximate transmit epoch here is only a gate; satposs computes it. */
        if(!satpos(timeadd(epoch,-0.075),epoch,sat,opt->sateph,nav,rs,dts,&variance,&health)||health) {
            reason="BROADCAST_IOD_OR_SATPOS_NOT_READY";continue;
        }
        obsd_t row=obs[i];int codes=0;
        for(int f=0;f<NFREQ;f++) {
            const int code=row.code[f];
            if(code<=0||code>MAXCODE||!s.cbias_valid[code-1]) {
                row.P[f]=row.L[f]=row.D[f]=0;continue;
            }
            if(row.P[f]!=0.0)codes++;
        }
        if(!codes)continue;
        obs[out++]=row;accepted_satellites++;accepted_codes+=codes;
    }
    if(out>=4)reason="CORRECTIONS_READY";
    else if(whu_pending)reason="WHU_OSB_WAIT_NEXT_ESTIMATE";
    else if(reason=="CORRECTIONS_READY")reason="INSUFFICIENT_CORRECTED_SATELLITES";
    return out;
}
std::string NtripSsr::status() const {
    char buf[512];snprintf(buf,sizeof(buf),
        "%s; frames=%lu/%lu; CRC=%lu/%lu; provider=%d; solution=%d; corrected_sat=%d; code=%d; bias_frames=%lu; bias_provider=%d; bias_solution=%d",
        reason.c_str(),frames[0],frames[1],crc_errors[0],crc_errors[1],provider,solution,
        accepted_satellites,accepted_codes,frames[2],bias_provider,bias_solution);
    return std::string(buf)+(whu_osb?"; policy=WHU_OSB_CONTINUITY_V1; osb_iod="+std::to_string(whu_bias_iod):"");
}

void NtripSsr::preserveRejectedArcs(rtk_t *rtk,const obsd_t *before,int n,const obsd_t *after,int accepted) {
    if(!rtk||!before||n<1||n>MAXOBS||accepted<0||accepted>MAXOBS)return;
    obsd_t events[MAXOBS];int count=0;
    for(int i=0;i<n;i++) {
        if(!(satsys(before[i].sat,nullptr)&rtk->opt.navsys))continue;
        obsd_t event=before[i];bool keep=false;
        std::memset(event.LLI,0,sizeof(event.LLI));
        for(int f=0;f<NFREQ;f++)if(before[i].LLI[f]&LLI_SLIP) {
            bool forwarded=false;
            if(accepted>=4 && after)for(int j=0;j<accepted;j++)if(after[j].sat==before[i].sat &&
                after[j].code[f]==before[i].code[f] && (after[j].P[f]||after[j].L[f]))forwarded=true;
            if(!forwarded){event.LLI[f]=before[i].LLI[f];keep=true;}
        }
        if(keep)events[count++]=event;
    }
    if(count)ppp_input_failure_arcs(rtk,events,count);
}
