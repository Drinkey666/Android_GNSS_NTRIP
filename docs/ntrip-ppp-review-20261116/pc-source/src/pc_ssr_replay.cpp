#include "pc_ssr_replay.h"
#include "ntrip_ssr.h"
#include <fstream>
#include <sstream>
#include <memory>
#include <string>
#include <vector>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <array>

namespace {
struct Arrival {
    unsigned long long seq=0,utc=0,elapsed=0,offset=0,length=0;
    int channel=0;
    std::string event,reason;
};
unsigned long long number(const std::string &s) {
    if(s.empty() || s.find_first_not_of("0123456789")!=std::string::npos)
        throw std::runtime_error("TIMELINE_NUMBER_INVALID");
    size_t used=0;auto n=std::stoull(s,&used);
    if(used!=s.size())throw std::runtime_error("TIMELINE_NUMBER_INVALID");
    return n;
}
Arrival parse(std::string line) {
    if(!line.empty()&&line.back()=='\r')line.pop_back();
    if(line.size()>2048)throw std::runtime_error("TIMELINE_ROW_TOO_LARGE");
    std::vector<std::string> cols;std::stringstream in(line);std::string col;
    while(std::getline(in,col,','))cols.push_back(col);
    if(!line.empty()&&line.back()==',')cols.emplace_back();
    if(cols.size()!=8)throw std::runtime_error("TIMELINE_COLUMNS_INVALID");
    Arrival a;
    a.seq=number(cols[0]);a.utc=number(cols[1]);a.elapsed=number(cols[2]);
    const auto channel=number(cols[3]);
    if(channel>2)throw std::runtime_error("TIMELINE_CHANNEL_INVALID");
    a.channel=(int)channel;a.event=cols[4];a.offset=number(cols[5]);a.length=number(cols[6]);a.reason=cols[7];
    if(a.utc<315964800000000000ULL || a.utc>9000000000000000000ULL || a.length>16384)
        throw std::runtime_error("TIMELINE_RANGE_INVALID");
    if(a.event!="DATA"&&a.event!="START"&&a.event!="RESET"&&a.event!="CONNECTED"&&a.event!="CLOSED"&&a.event!="END")
        throw std::runtime_error("TIMELINE_EVENT_INVALID");
    if((a.event=="DATA") != (a.length>0))throw std::runtime_error("TIMELINE_LENGTH_INVALID");
    if(a.reason.find_first_not_of("ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789abcdefghijklmnopqrstuvwxyz")!=std::string::npos)
        throw std::runtime_error("TIMELINE_REASON_INVALID");
    return a;
}
gtime_t utc_from_ns(unsigned long long ns) {
    gtime_t t{};t.time=(time_t)(ns/1000000000ULL);t.sec=(ns%1000000000ULL)*1e-9;return t;
}
unsigned long long utc_ns(gtime_t gpst) {
    const auto u=gpst2utc(gpst);
    if(u.time<0 || !std::isfinite(u.sec))throw std::runtime_error("OBS_TIME_INVALID");
    return (unsigned long long)u.time*1000000000ULL+(unsigned long long)std::llround(u.sec*1e9);
}
class Replay {
public:
    std::ifstream timeline,raw[3];
    int channels=2;
    struct Decision {double gps;unsigned long long callback,elapsed,seq;};
    std::vector<Decision> decisions;size_t decision_index=0;
    std::unique_ptr<NtripSsr> ssr;
    std::ofstream log;
    Arrival next;
    unsigned long long start=0,end=0,previous_epoch=0,latency_ns=0,consumed=0;
    bool pending=false;
    Replay(const std::string &dir,const std::string &csv,double latency,const std::string &profile="GENERIC_STRICT") {
        if(!std::isfinite(latency)||latency<0.0||latency>10000.0)throw std::runtime_error("LATENCY_INVALID");
        latency_ns=(unsigned long long)std::llround(latency*1e6);
        timeline.open(dir+"/arrivals.csv",std::ios::binary);
        raw[0].open(dir+"/ssr.rtcm3",std::ios::binary);
        raw[1].open(dir+"/broadcast.rtcm3",std::ios::binary);
        if(!timeline||!raw[0]||!raw[1])throw std::runtime_error("CAPTURE_FILES_MISSING");
        raw[2].open(dir+"/bias.rtcm3",std::ios::binary);
        if(raw[2])channels=3;
        std::string header,line;std::getline(timeline,header);
        if(!header.empty()&&header.back()=='\r')header.pop_back();
        if(header!="seq,utc_ns,elapsed_ns,channel,event,offset,length,reason")throw std::runtime_error("TIMELINE_HEADER_INVALID");
        const auto data_start=timeline.tellg();
        std::array<unsigned long long,3> sizes{},offset{};
        std::array<bool,3> started{},ended{};
        for(int i=0;i<channels;i++){raw[i].seekg(0,std::ios::end);sizes[i]=(unsigned long long)raw[i].tellg();raw[i].seekg(0);}
        unsigned long long seq=0,previous_time=0,previous_elapsed=0;
        while(std::getline(timeline,line)) {
            auto a=parse(line);
            if(a.channel>=channels)throw std::runtime_error("TIMELINE_CHANNEL_NOT_RECORDED");
            if(a.seq!=seq++ || a.utc<previous_time || a.elapsed<previous_elapsed)
                throw std::runtime_error("TIMELINE_ORDER_INVALID");
            if(a.offset!=offset[a.channel] || a.length>sizes[a.channel]-offset[a.channel])
                throw std::runtime_error("TIMELINE_OFFSET_INVALID");
            offset[a.channel]+=a.length;
            if(ended[a.channel])throw std::runtime_error("TIMELINE_DATA_AFTER_END");
            if(a.event=="START"){if(started[a.channel])throw std::runtime_error("TIMELINE_REPEATED_START");started[a.channel]=true;}
            if(!started[a.channel])throw std::runtime_error("TIMELINE_MISSING_START");
            if(a.event=="END")ended[a.channel]=true;
            if(!start)start=a.utc;
            end=a.utc;previous_time=a.utc;previous_elapsed=a.elapsed;
        }
        if(!seq || !ended[0] || !ended[1] || (channels==3&&!ended[2]) || sizes!=offset)throw std::runtime_error("CAPTURE_INCOMPLETE");
        std::ifstream ledger(dir+"/epochs.csv");
        if(ledger) {
            if(latency_ns)throw std::runtime_error("LEDGER_LATENCY_MUST_BE_ZERO");
            std::getline(ledger,line);if(!line.empty()&&line.back()=='\r')line.pop_back();
            if(line!="week,tow,callback_elapsed_ns,decision_elapsed_ns,applied_seq,status")throw std::runtime_error("LEDGER_HEADER_INVALID");
            double last_gps=-1;unsigned long long last_seq=0,last_callback=0;
            while(std::getline(ledger,line)) {
                std::stringstream cells(line);std::vector<std::string> c;std::string item;
                while(std::getline(cells,item,','))c.push_back(item);
                if(c.size()!=6)throw std::runtime_error("LEDGER_COLUMNS_INVALID");
                const auto week=number(c[0]);size_t used=0;const double tow=std::stod(c[1],&used);
                Decision d{week*604800.0+tow,number(c[2]),number(c[3]),number(c[4])};
                if(used!=c[1].size()||!std::isfinite(tow)||tow<0||tow>=604800||week<1000||week>10000||
                    d.gps<=last_gps||d.seq>=seq||d.seq<last_seq||d.callback<last_callback||d.elapsed<d.callback||d.elapsed>previous_elapsed)
                    throw std::runtime_error("LEDGER_ORDER_OR_RANGE_INVALID");
                decisions.push_back(d);last_gps=d.gps;last_seq=d.seq;last_callback=d.callback;
            }
        }
        timeline.clear();timeline.seekg(data_start);
        ssr=std::make_unique<NtripSsr>();
        if(!ssr->init())throw std::runtime_error("RTCM_ALLOCATION_FAILED");
        if(profile==NtripSsr::WHU_CONTINUITY_PROFILE || profile==NtripSsr::WHU_FIRST_COMPLETE_PROFILE) {
            if(channels!=3||!ssr->useWhuOsb("SSRC00WHU0","OSBC00WHU1",true,
                profile==NtripSsr::WHU_FIRST_COMPLETE_PROFILE))throw std::runtime_error("WHU_PROFILE_REQUIRES_THREE_STREAMS");
        } else if(profile!="GENERIC_STRICT")throw std::runtime_error("SSR_PROFILE_INVALID");
        if(!csv.empty()) {
            log.open(csv,std::ios::out|std::ios::trunc);
            if(!log)throw std::runtime_error("DIAGNOSTIC_OPEN_FAILED");
            log<<"week,tow,epoch_utc_ns,release_cutoff_utc_ns,records_released,raw_satellites,corrected_satellites,corrected_codes,corrections_ready,reason,status\n";
        }
        advance();
    }
    void advance() {
        std::string line;
        pending=bool(std::getline(timeline,line));
        if(pending)next=parse(line);
    }
    void release(gtime_t epoch,nav_t *nav,bool inspect=false) {
        const auto time=utc_ns(epoch);
        if(decisions.empty() && (time<start || time>end))throw std::runtime_error("TXT_OUTSIDE_CAPTURE_TIME");
        if(previous_epoch && time<=previous_epoch)throw std::runtime_error("OBS_EPOCH_ORDER_INVALID");
        previous_epoch=time;
        const auto cutoff=time+latency_ns;
        const Decision *decision=nullptr;
        if(!inspect && !decisions.empty()) {
            int week=0;double tow=time2gpst(epoch,&week);double gps=week*604800.0+tow;
            while(decision_index<decisions.size() && decisions[decision_index].gps<gps-1e-5)decision_index++;
            if(decision_index>=decisions.size() || std::fabs(decisions[decision_index].gps-gps)>1e-5)
                throw std::runtime_error("OBS_EPOCH_NOT_IN_ANDROID_LEDGER");
            decision=&decisions[decision_index++];
        }
        while(pending && (decision?next.seq<=decision->seq:next.utc<=cutoff)) {
            if(decision && next.elapsed>decision->elapsed)throw std::runtime_error("LEDGER_FUTURE_RECEIPT");
            if(next.event=="RESET")ssr->resetTransport(next.channel);
            if(next.event=="DATA") {
                std::vector<unsigned char> data((size_t)next.length);
                raw[next.channel].seekg((std::streamoff)next.offset);
                raw[next.channel].read((char*)data.data(),(std::streamsize)data.size());
                if((size_t)raw[next.channel].gcount()!=data.size())throw std::runtime_error("RTCM_TRUNCATED");
                // Decode week/day relative to arrival, never relative to a future observation.
                ssr->feed(nav,next.channel,data.data(),(int)data.size(),utc2gpst(utc_from_ns(next.utc)));
            }
            consumed++;advance();
        }
    }
    int prepare(gtime_t epoch,nav_t *nav,const prcopt_t *opt,obsd_t *obs,int n) {
        release(epoch,nav);
        const int out=ssr->prepare(nav,opt,epoch,obs,n);
        if(log) {
            int week;double tow=time2gpst(epoch,&week);
            log.precision(17);
            log<<week<<','<<tow<<','<<previous_epoch<<','<<previous_epoch+latency_ns<<','<<consumed<<','
               <<n<<','<<out<<','<<ssr->accepted_codes<<','<<(out>=4?1:0)<<','<<ssr->reason<<','<<ssr->status()<<'\n';
        }
        return out;
    }
};
std::unique_ptr<Replay> replay;
std::string failure;
}
extern "C" int pc_ssr_open(const char *dir,const char *log,const char *datum,double latency,nav_t *nav,prcopt_t *opt) {
    return pc_ssr_open_profile(dir,log,datum,latency,nav,opt,"GENERIC_STRICT");
}
extern "C" int pc_ssr_open_profile(const char *dir,const char *log,const char *datum,double latency,nav_t *nav,prcopt_t *opt,const char *profile) {
    pc_ssr_close();
    try {
        if(!dir||!nav||!opt||!datum)throw std::runtime_error("SSR_ARGUMENT_INVALID");
        if(std::strcmp(datum,"APC")&&std::strcmp(datum,"COM"))throw std::runtime_error("SSR_DATUM_INVALID");
        if(!profile || (std::strcmp(profile,"GENERIC_STRICT") && std::strcmp(datum,"COM")))
            throw std::runtime_error("WHU_PROFILE_REQUIRES_COM");
        replay=std::make_unique<Replay>(dir,log?log:"",latency,profile);
        opt->sateph=!std::strcmp(datum,"APC")?EPHOPT_SSRAPC:EPHOPT_SSRCOM;
        NtripSsr::setReference(nav);
        return 1;
    } catch(const std::exception &e){failure=e.what();replay.reset();return 0;}
}
extern "C" int pc_ssr_active(void){return bool(replay);}
extern "C" gtime_t pc_ssr_start(void){return replay?utc2gpst(utc_from_ns(replay->start)):gtime_t{};}
extern "C" int pc_ssr_prepare(gtime_t epoch,nav_t *nav,const prcopt_t *opt,obsd_t *obs,int n) {
    if(!replay)return n;
    try{return replay->prepare(epoch,nav,opt,obs,n);}
    catch(const std::exception &e){failure=e.what();return -1;}
}
extern "C" const char *pc_ssr_error(void){return failure.c_str();}
extern "C" void pc_ssr_close(void){replay.reset();failure.clear();}
extern "C" int pc_ssr_inspect(const char *directory,FILE *out) {
    return pc_ssr_inspect_profile(directory,out,"GENERIC_STRICT");
}
extern "C" int pc_ssr_inspect_profile(const char *directory,FILE *out,const char *profile) {
    nav_t *nav=(nav_t*)std::calloc(1,sizeof(nav_t));
    if(!nav)return 0;
    try {
        Replay session(directory,"",0,profile?profile:"");
        const auto epoch=utc2gpst(utc_from_ns(session.end));
        session.release(epoch,nav,true);
        int complete=0,signals=0,matched=0,all_components=0,iod_mismatch=0,identity_mismatch=0,bias_count=0;
        double min_bias_age=1e100,max_bias_age=-1e100;
        for(int j=0;j<MAXSAT;j++) {
            const auto &s=session.ssr->committed[j];
            if(s.t0[4].time) {
                const double age=timediff(epoch,s.t0[4]);bias_count++;
                if(age<min_bias_age)min_bias_age=age;if(age>max_bias_age)max_bias_age=age;
            }
            if(s.t0[0].time&&s.t0[1].time&&s.t0[4].time) {
                all_components++;
                if(s.iod[0]!=s.iod[1]||s.iod[0]!=s.iod[4])iod_mismatch++;
                if(s.provider[0]!=s.provider[1]||s.provider[0]!=s.provider[4]||s.solution[0]!=s.solution[1]||s.solution[0]!=s.solution[4])identity_mismatch++;
            }
            if(!session.ssr->usable(j+1,epoch))continue;
            complete++;
            for(int k=0;k<MAXCODE;k++)if(s.cbias_valid[k])signals++;
            const int sys=satsys(j+1,nullptr);
            if(sys!=SYS_GPS && sys!=SYS_GAL && sys!=SYS_CMP)continue;
            nav->ssr[j]=s;double rs[6]{},dt[2]{},variance=0;int health=0;
            if(satpos(timeadd(epoch,-.075),epoch,j+1,EPHOPT_SSRAPC,nav,rs,dt,&variance,&health)&&!health)matched++;
        }
        fprintf(out,"{\"ssr_profile\":\"%s\",\"inventory_only\":true,\"checks_antex\":false,\"orbit_clock_bias_satellites\":%d,\"iod_mismatch_satellites\":%d,\"identity_mismatch_satellites\":%d,"
                    "\"bias_age_min_s\":%.6f,\"bias_age_max_s\":%.6f,\"bias_crc_failures\":%lu,\"bias_provider\":%d,\"bias_solution\":%d,"
                    "\"bias_frames\":%lu,\"ssr_frames\":%lu,\"broadcast_frames\":%lu,\"ssr_crc_failures\":%lu,\"broadcast_crc_failures\":%lu,"
                    "\"broadcast_ephemerides\":%d,\"coherent_ssr_satellites_at_end\":%d,\"code_bias_signals\":%d,"
                    "\"provider\":%d,\"solution\":%d,\"blocked\":%s,\"decode_errors\":%lu,\"matching_broadcast_satellites\":%d,\"reason\":\"%s\"}\n",
            session.ssr->profileName(),
            all_components,iod_mismatch,identity_mismatch,bias_count?min_bias_age:0,bias_count?max_bias_age:0,
            session.ssr->crc_errors[2],session.ssr->bias_provider,session.ssr->bias_solution,
            session.ssr->frames[2],session.ssr->frames[0],session.ssr->frames[1],session.ssr->crc_errors[0],session.ssr->crc_errors[1],
            nav->n,complete,signals,session.ssr->provider,session.ssr->solution,session.ssr->blocked?"true":"false",session.ssr->decode_errors[0],matched,
            session.ssr->blocked?session.ssr->reason.c_str():complete?"SSR_INVENTORY_READY":"NO_COHERENT_SSR_AT_CAPTURE_END");
        std::free(nav->eph);std::free(nav);return 1;
    } catch(const std::exception &e){failure=e.what();std::free(nav->eph);std::free(nav);return 0;}
}
extern "C" void pc_ssr_preserve_rejected_arcs(rtk_t *rtk,const obsd_t *before,int n,const obsd_t *after,int accepted) {
    NtripSsr::preserveRejectedArcs(rtk,before,n,after,accepted);
}
