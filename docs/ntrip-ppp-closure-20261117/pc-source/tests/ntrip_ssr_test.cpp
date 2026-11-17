#include "ntrip_ssr.h"
#include "verified_profile.h"
#include <vector>
#include <memory>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <limits>
#include "fixtures/whu1261_reference.h"

extern "C" double ntrip_test_code(const obsd_t*,const nav_t*,const prcopt_t*);
extern "C" double ntrip_test_spp_code(const obsd_t*,const nav_t*,const prcopt_t*);
static int checks=0;
#define CHECK(x) do{checks++;if(!(x)){printf("FAIL line %d: %s\n",__LINE__,#x);return 1;}}while(0)
static std::vector<unsigned char> frame(int family,int iod,int provider,int solution,
                                       bool igs=false,bool more=false,int bias=125,int epoch=100000,bool bds=false,int bds_iod=7) {
    std::vector<unsigned char> b(256,0);int at=24;
    auto u=[&](int n,unsigned v){setbitu(b.data(),at,n,v);at+=n;};
    auto s=[&](int n,int v){setbits(b.data(),at,n,v);at+=n;};
    u(12,igs?4076:(bds?(family==3?1260:family==1?1258:1261):(family==3?1059:family==1?1057:1060)));
    if(igs){u(3,1);u(8,bds?(family==3?105:family==1?101:103):(family==3?25:family==1?21:23));}
    u(20,epoch);u(4,2);u(1,more?1:0);
    if(family!=3&&!igs)u(1,0);
    u(4,iod);u(16,provider);u(4,solution);
    if(family!=3&&igs)u(1,0);
    u(6,1);u(6,1); // one satellite, G01 or C01
    if(family==3) {
        u(5,2);u(5,0);s(14,bias);u(5,15);s(14,0); // C1C=1.25m, C5Q=valid zero
    } else {
        if(bds&&!igs){u(10,0);u(8,bds_iod);}else u(8,7);
        s(22,10000);s(20,0);s(20,0); // radial=1m
        s(21,0);s(19,0);s(19,0);
        if(family!=1){s(22,20000);s(21,0);s(27,0);} // combined clock=2m
    }
    int bytes=(at+7)/8;setbitu(b.data(),0,8,0xD3);setbitu(b.data(),14,10,bytes-3);
    setbitu(b.data(),bytes*8,24,rtk_crc24q(b.data(),bytes));b.resize(bytes+3);return b;
}
int main() {
    auto stream=std::make_unique<NtripSsr>();CHECK(stream->init());
    auto nav=std::unique_ptr<nav_t,decltype(&free)>((nav_t*)calloc(1,sizeof(nav_t)),free);
    const gtime_t t=gpst2time(2400,100000);
    auto orbit=frame(4,2,12,1),code=frame(3,2,12,1);
    stream->feed(nav.get(),0,orbit.data(),4,t);CHECK(stream->frames[0]==0);
    stream->feed(nav.get(),0,orbit.data()+4,(int)orbit.size()-4,t);
    CHECK(stream->frames[0]==1);CHECK(stream->committed[0].iode==7);
    CHECK(stream->committed[0].provider[0]==12);CHECK(stream->committed[0].solution[1]==1);
    CHECK(!NtripSsr::coherent(stream->committed[0],t));
    stream->feed(nav.get(),0,code.data(),(int)code.size(),t);
    CHECK(NtripSsr::coherent(stream->committed[0],t));
    CHECK(std::fabs(stream->committed[0].cbias[CODE_L1C-1]-1.25)<1e-12);
    CHECK(stream->committed[0].cbias_valid[CODE_L5Q-1]);
    CHECK(stream->committed[0].cbias[CODE_L5Q-1]==0.0);
    CHECK(!stream->committed[0].cbias_valid[CODE_L1W-1]);
    auto bad=code;bad.back()^=1;
    stream->feed(nav.get(),0,bad.data(),(int)bad.size(),t);
    CHECK(stream->crc_errors[0]==1);CHECK(stream->frames[0]==2);
    CHECK(NtripSsr::coherent(stream->committed[0],timeadd(t,11)));
    CHECK(!NtripSsr::coherent(stream->committed[0],timeadd(t,91)));
    CHECK(!NtripSsr::coherent(stream->committed[0],timeadd(t,-2)));
    ssr_t copy=stream->committed[0];copy.iod[4]++;CHECK(!NtripSsr::coherent(copy,t));
    copy=stream->committed[0];copy.provider[4]++;CHECK(!NtripSsr::coherent(copy,t));
    copy=stream->committed[0];copy.refd=1;CHECK(!NtripSsr::coherent(copy,t));
    copy=stream->committed[0];copy.dclk[0]=std::numeric_limits<double>::quiet_NaN();
    CHECK(!NtripSsr::coherent(copy,t));
    stream->feed(nav.get(),0,orbit.data(),5,t);stream->resetTransport(0);
    CHECK(stream->decoder[0]->nbyte==0);CHECK(NtripSsr::coherent(stream->committed[0],t));
    auto partial=frame(3,2,12,1,false,true,200);
    stream->feed(nav.get(),0,partial.data(),(int)partial.size(),t);
    CHECK(stream->committed[0].cbias[CODE_L1C-1]==1.25);
    stream->resetTransport(0);CHECK(stream->decoder[0]->ssr[0].cbias[CODE_L1C-1]==1.25);

    auto separate=std::make_unique<NtripSsr>();CHECK(separate->init());
    separate->feed(nav.get(),0,orbit.data(),(int)orbit.size(),t);
    separate->feed(nav.get(),2,code.data(),(int)code.size(),t);
    CHECK(NtripSsr::coherent(separate->committed[0],t));
    separate->feed(nav.get(),0,orbit.data(),(int)orbit.size(),t);
    CHECK(separate->committed[0].cbias[CODE_L1C-1]==1.25);
    separate->resetTransport(0);separate->resetTransport(2);
    CHECK(separate->decoder[0]->ssr[0].t0[4].time==0);
    CHECK(separate->decoder[2]->ssr[0].t0[0].time==0);
    separate->feed(nav.get(),0,orbit.data(),(int)orbit.size(),t);
    CHECK(!separate->blocked && NtripSsr::coherent(separate->committed[0],t));
    auto incompatible=std::make_unique<NtripSsr>();CHECK(incompatible->init());
    auto othercode=frame(3,5,1,1);
    incompatible->feed(nav.get(),0,orbit.data(),(int)orbit.size(),t);
    incompatible->feed(nav.get(),2,othercode.data(),(int)othercode.size(),t);
    CHECK(!incompatible->blocked);
    CHECK(!NtripSsr::coherent(incompatible->committed[0],t));
    CHECK(incompatible->committed[0].iod[0]==2 && incompatible->committed[0].iod[4]==5);

    auto whu=std::make_unique<NtripSsr>();CHECK(whu->init());
    CHECK(!whu->useWhuOsb("SSRA00WHU0","OSBC00WHU1",false));
    CHECK(whu->useWhuOsb("SSRC00WHU0","OSBC00WHU1",true));
    std::string why;
    for(int sec=0;sec<=300;sec+=5) {
        auto wo=frame(4,0,0,0,false,false,125,100000+sec);
        auto wb=frame(3,5,1,1,false,false,125,sec<300?99600:99900);
        auto now=timeadd(t,sec);
        whu->feed(nav.get(),0,wo.data(),(int)wo.size(),now);
        whu->feed(nav.get(),2,wb.data(),(int)wb.size(),now);
        if(sec<300)CHECK(!whu->usable(1,now,&why));
    }
    CHECK(whu->usable(1,timeadd(t,300),&why));
    CHECK(why=="READY_WHU_OSB_CONTINUITY");
    CHECK(!NtripSsr::coherent(whu->committed[0],timeadd(t,300))); // generic policy is unchanged
    CHECK(whu->committed[0].iod[0]==0 && whu->committed[0].iod[4]==5); // no rewritten header
    CHECK(std::fabs(timediff(timeadd(t,300),whu->committed[0].t0[4])-400)<1e-9); // no restamp
    CHECK(!whu->useWhuOsb("SSRC00WHU0","OSBC00WHU1",true)); // cannot switch a running session
    CHECK(!whu->usable(1,timeadd(t,391),&why)); // orbit still has its 90s expiry
    CHECK(why=="SSR_EXPIRED");
    for(int sec=305;sec<=610;sec+=5) {
        auto wo=frame(4,0,0,0,false,false,125,100000+sec);
        auto wb=frame(3,5,1,1,false,false,125,99900);
        whu->feed(nav.get(),0,wo.data(),(int)wo.size(),timeadd(t,sec));
        whu->feed(nav.get(),2,wb.data(),(int)wb.size(),timeadd(t,sec));
    }
    CHECK(!whu->usable(1,timeadd(t,610),&why));CHECK(why=="WHU_OSB_ESTIMATE_NOT_ADVANCING");
    auto recovered=frame(3,5,1,1,false,false,125,100200);
    auto recovered_orbit=frame(4,0,0,0,false,false,125,100615);
    whu->feed(nav.get(),0,recovered_orbit.data(),(int)recovered_orbit.size(),timeadd(t,615));
    whu->feed(nav.get(),2,recovered.data(),(int)recovered.size(),timeadd(t,615));
    CHECK(whu->usable(1,timeadd(t,615),&why)); // a new genuine estimate may recover after the watchdog
    auto fresh_orbit=frame(4,0,0,0,false,false,125,100706);
    whu->feed(nav.get(),0,fresh_orbit.data(),(int)fresh_orbit.size(),timeadd(t,706));
    CHECK(!whu->usable(1,timeadd(t,706),&why));CHECK(why=="WHU_OSB_TRANSPORT_STALE");
    whu->resetTransport(2);
    CHECK(!whu->usable(1,timeadd(t,706),&why));CHECK(why=="WHU_OSB_WAIT_NEXT_ESTIMATE");
    auto changed_iod=frame(3,6,1,1,false,false,125,100200);
    whu->feed(nav.get(),2,changed_iod.data(),(int)changed_iod.size(),timeadd(t,710));
    CHECK(whu->blocked && whu->reason=="WHU_BIAS_CONFIG_CHANGED_RESTART_REQUIRED");
    auto future_whu=std::make_unique<NtripSsr>();CHECK(future_whu->init());
    CHECK(future_whu->useWhuOsb("SSRC00WHU0","OSBC00WHU1",true));
    auto future_bias=frame(3,5,1,1,false,false,125,100010);
    future_whu->feed(nav.get(),2,future_bias.data(),(int)future_bias.size(),t);
    CHECK(future_whu->blocked&&future_whu->reason=="WHU_OSB_FUTURE_EPOCH");
    auto reverse_whu=std::make_unique<NtripSsr>();CHECK(reverse_whu->init());
    CHECK(reverse_whu->useWhuOsb("SSRC00WHU0","OSBC00WHU1",true));
    auto first_bias=frame(3,5,1,1,false,false,125,99600);
    auto older_bias=frame(3,5,1,1,false,false,125,99599);
    reverse_whu->feed(nav.get(),2,first_bias.data(),(int)first_bias.size(),t);
    reverse_whu->feed(nav.get(),2,older_bias.data(),(int)older_bias.size(),timeadd(t,5));
    CHECK(reverse_whu->blocked&&reverse_whu->reason=="WHU_OSB_EPOCH_REGRESSION");

    auto first_complete=std::make_unique<NtripSsr>();CHECK(first_complete->init());
    CHECK(first_complete->useWhuOsb("SSRC00WHU0","OSBC00WHU1",true,true));
    CHECK(std::strcmp(first_complete->profileName(),NtripSsr::WHU_FIRST_COMPLETE_PROFILE)==0);
    auto feed_first=[&](int channel,const std::vector<unsigned char> &bytes,int second) {
        first_complete->feed(nav.get(),channel,bytes.data(),(int)bytes.size(),timeadd(t,second));
    };
    feed_first(0,orbit,0);
    CHECK(!first_complete->usable(1,t,&why));CHECK(why=="MISSING_ORBIT_CLOCK_CODE_BIAS");
    auto incomplete=frame(3,5,1,1,false,true,125,99600);
    feed_first(2,incomplete,0);
    CHECK(!first_complete->usable(1,t,&why));
    feed_first(2,first_bias,0);
    CHECK(first_complete->usable(1,t,&why));CHECK(why=="READY_WHU_OSB_FIRST_COMPLETE");
    CHECK(!first_complete->usable(1,timeadd(t,91),&why));CHECK(why=="SSR_EXPIRED");
    auto late_orbit=frame(4,2,12,1,false,false,125,100306);
    feed_first(0,late_orbit,306);
    CHECK(!first_complete->usable(1,timeadd(t,306),&why));CHECK(why=="WHU_OSB_TRANSPORT_STALE");
    feed_first(2,first_bias,306);
    CHECK(!first_complete->usable(1,timeadd(t,306),&why));CHECK(why=="WHU_OSB_ESTIMATE_NOT_ADVANCING");
    first_complete->resetTransport(2);
    CHECK(!first_complete->usable(1,timeadd(t,306),&why));CHECK(why=="WHU_OSB_WAIT_COMPLETE_ESTIMATE");
    feed_first(2,first_bias,307);
    CHECK(!first_complete->usable(1,timeadd(t,307),&why));CHECK(why=="WHU_OSB_ESTIMATE_NOT_ADVANCING");
    auto next_bias=frame(3,5,1,1,false,false,125,99900);
    feed_first(2,next_bias,308);
    CHECK(first_complete->usable(1,timeadd(t,308),&why));
    first_complete->resetTransport(2);
    feed_first(2,first_bias,309);
    CHECK(first_complete->blocked&&first_complete->reason=="WHU_OSB_EPOCH_REGRESSION");

    for(bool start_with_first_bias:{false,true}) {
        auto isolated=std::make_unique<NtripSsr>();CHECK(isolated->init());
        CHECK(isolated->useWhuOsb("SSRC00WHU0","OSBC00WHU1",true,start_with_first_bias));
        auto embedded=frame(3,9,77,3,false,false,475,99999);
        auto orbit_only=frame(4,2,12,1);
        auto independent=frame(3,5,1,1,false,false,125,99900);
        auto update_orbit=frame(4,2,12,1,false,false,125,100001);
        auto feed_isolated=[&](int channel,const std::vector<unsigned char> &bytes,gtime_t receipt) {
            isolated->feed(nav.get(),channel,bytes.data(),(int)bytes.size(),receipt);
        };
        auto &cached=isolated->committed[0];
        feed_isolated(0,embedded,t);
        CHECK(!isolated->blocked && isolated->provider==-1);
        CHECK(isolated->decoder[0]->ssr[0].cbias[CODE_L1C-1]==4.75);
        CHECK(!cached.t0[4].time && !cached.cbias_valid[CODE_L1C-1] && !cached.update);
        if(!start_with_first_bias)feed_isolated(2,first_bias,timeadd(t,-5));
        feed_isolated(2,independent,t);
        const ssr_t bias_snapshot=cached;
        CHECK(timediff(cached.t0[4],t)==-100.0 && cached.udi[4]==5.0);
        CHECK(cached.iod[4]==5 && cached.provider[4]==1 && cached.solution[4]==1);
        CHECK(cached.cbias_valid[CODE_L1C-1] && cached.cbias[CODE_L1C-1]==1.25);
        CHECK(cached.cbias_valid[CODE_L5Q-1] && cached.cbias[CODE_L5Q-1]==0.0);
        CHECK(!cached.cbias_valid[CODE_L1W-1]);
        auto bias_preserved=[&]() {
            return timediff(cached.t0[4],bias_snapshot.t0[4])==0.0 &&
                cached.udi[4]==bias_snapshot.udi[4] && cached.iod[4]==bias_snapshot.iod[4] &&
                cached.provider[4]==bias_snapshot.provider[4] && cached.solution[4]==bias_snapshot.solution[4] &&
                std::memcmp(cached.cbias,bias_snapshot.cbias,sizeof(cached.cbias))==0 &&
                std::memcmp(cached.cbias_valid,bias_snapshot.cbias_valid,sizeof(cached.cbias_valid))==0;
        };
        feed_isolated(0,embedded,t);
        CHECK(!isolated->blocked && !cached.t0[0].time && bias_preserved());
        feed_isolated(0,orbit_only,t);
        CHECK(!isolated->blocked && isolated->provider==12 && isolated->solution==1 && bias_preserved());
        CHECK(isolated->usable(1,t,&why));
        CHECK(why==(start_with_first_bias?"READY_WHU_OSB_FIRST_COMPLETE":"READY_WHU_OSB_CONTINUITY"));
        const auto later=timeadd(t,1);
        feed_isolated(0,embedded,later);
        CHECK(!isolated->blocked && timediff(cached.t0[0],t)==0.0 && bias_preserved());
        CHECK(isolated->usable(1,later,&why));
        feed_isolated(0,update_orbit,later);
        CHECK(!isolated->blocked && bias_preserved());
        CHECK(timediff(cached.t0[0],later)==0.0 && timediff(cached.t0[1],later)==0.0);
        CHECK(isolated->usable(1,later,&why));
    }

    auto bds=std::make_unique<NtripSsr>();CHECK(bds->init());
    const int c01=satno(SYS_CMP,1)-1;
    auto bo=frame(4,2,12,1,false,false,125,99986,true);
    auto bc=frame(3,2,12,1,false,false,125,99986,true);
    bds->feed(nav.get(),0,bo.data(),(int)bo.size(),t);
    bds->feed(nav.get(),0,bc.data(),(int)bc.size(),t);
    CHECK(bds->committed[c01].bds_iod_mode==1);
    CHECK(bds->committed[c01].iode==7 && bds->committed[c01].bds_toe_mod==0);
    CHECK(bds->committed[c01].cbias_valid[CODE_L2I-1]);
    CHECK(!bds->committed[c01+1].t0[4].time); // direct C01, no +1 satellite shift
    CHECK(std::fabs(timediff(bds->committed[c01].t0[0],t))<1e-9);
    CHECK(std::fabs(timediff(bds->committed[c01].t0[1],t))<1e-9);
    CHECK(std::fabs(timediff(bds->committed[c01].t0[4],t))<1e-9);
    bds->feed(nav.get(),0,bc.data(),(int)bc.size(),t); // retransmission cannot shift previous epochs twice
    CHECK(std::fabs(timediff(bds->committed[c01].t0[0],t))<1e-9);
    CHECK(std::fabs(timediff(bds->committed[c01].t0[4],t))<1e-9);
    auto bi=std::make_unique<NtripSsr>();CHECK(bi->init());
    auto bio=frame(4,2,12,1,true,false,125,100000,true);
    bi->feed(nav.get(),0,bio.data(),(int)bio.size(),t);
    CHECK(bi->committed[c01].bds_iod_mode==0); // IGS retains its own layout
    CHECK(std::fabs(timediff(bi->committed[c01].t0[0],t))<1e-9); // IGS BDS is already GPST
    auto boundary=frame(4,2,12,1,false,false,125,604795,true);
    const auto nextweek=gpst2time(2401,9);
    bds->feed(nav.get(),0,boundary.data(),(int)boundary.size(),nextweek);
    CHECK(std::fabs(timediff(bds->committed[c01].t0[0],nextweek))<1e-9);

    // The original 24-bit-draft decoder writes only 11 slots for this 35-sat frame.
    auto separate_bds=std::make_unique<NtripSsr>();CHECK(separate_bds->init());
    auto sep=frame(1,2,12,1,false,false,125,99986,true,138);
    separate_bds->feed(nav.get(),0,sep.data(),(int)sep.size(),t);
    CHECK(separate_bds->committed[c01].iode==138 && separate_bds->committed[c01].bds_iod_mode==1);
    CHECK(std::fabs(separate_bds->committed[c01].deph[0]-1)<1e-12);
    CHECK(!separate_bds->committed[c01].t0[1].time);
    auto edge=bo;setbitu(edge.data(),92,6,63);
    setbitu(edge.data(),((int)edge.size()-3)*8,24,rtk_crc24q(edge.data(),(int)edge.size()-3));
    auto edge_bds=std::make_unique<NtripSsr>();CHECK(edge_bds->init());
    edge_bds->feed(nav.get(),0,edge.data(),(int)edge.size(),t);
    CHECK(edge_bds->committed[satno(SYS_CMP,63)-1].iode==7);
    CHECK(!edge_bds->committed[c01].t0[0].time);
    auto zero=bo;setbitu(zero.data(),92,6,0);
    setbitu(zero.data(),((int)zero.size()-3)*8,24,rtk_crc24q(zero.data(),(int)zero.size()-3));
    auto zero_bds=std::make_unique<NtripSsr>();CHECK(zero_bds->init());
    zero_bds->feed(nav.get(),0,zero.data(),(int)zero.size(),t);
    CHECK(!zero_bds->decoder[0]->ssr[c01].t0[0].time); // no alias of invalid PRN zero
    auto real_bds=std::make_unique<NtripSsr>();CHECK(real_bds->init());
    real_bds->feed(nav.get(),0,whu1261_frame,sizeof(whu1261_frame),gpst2time(2442,21983));
    CHECK(real_bds->decode_errors[0]==0);
    int real_count=0;
    for(int i=0;i<MAXSAT;i++)if(satsys(i+1,nullptr)==SYS_CMP && real_bds->decoder[0]->ssr[i].t0[0].time)real_count++;
    CHECK(real_count==35);
    const double scales[]={1e-4,4e-4,4e-4,1e-6,4e-6,4e-6,1e-4,1e-6,2e-8};
    for(const auto &expected:whu1261_expected) {
        const auto &s=real_bds->decoder[0]->ssr[satno(SYS_CMP,expected[0])-1];
        CHECK(s.bds_iod_mode==1 && s.bds_toe_mod==expected[1] && s.iode==expected[2]);
        CHECK(std::fabs(timediff(s.t0[0],gpst2time(2442,21975)))<1e-9);
        for(int i=0;i<9;i++) {
            const double actual=i<3?s.deph[i]:i<6?s.ddeph[i-3]:s.dclk[i-6];
            CHECK(std::fabs(actual-expected[i+3]*scales[i])<1e-10);
        }
    }
    std::vector<unsigned char> truncated(whu1261_frame,whu1261_frame+sizeof(whu1261_frame)-4);
    setbitu(truncated.data(),14,10,(int)truncated.size()-3);
    const int shortened=(int)truncated.size();truncated.resize(shortened+3);
    setbitu(truncated.data(),shortened*8,24,rtk_crc24q(truncated.data(),shortened));
    auto short_bds=std::make_unique<NtripSsr>();CHECK(short_bds->init());
    short_bds->feed(nav.get(),0,truncated.data(),(int)truncated.size(),t);
    CHECK(short_bds->decode_errors[0]==1);
    CHECK(!short_bds->decoder[0]->ssr[c01].t0[0].time); // no partial satellite writes

    NtripSsr::setReference(nav.get());
    CHECK(nav->clock_ref_code[0][1]==CODE_L2W);
    CHECK(nav->clock_ref_code[2][1]==CODE_L5Q);
    CHECK(nav->clock_ref_code[3][1]==CODE_L6I);
    nav->ssr[0]=stream->committed[0];prcopt_t opt{};char error[256]{};
    CHECK(pc_b_verified_configure(&opt,nullptr,error,sizeof(error)));
    opt.sateph=EPHOPT_SSRAPC;
    obsd_t obs{};obs.sat=1;obs.time=t;obs.code[0]=CODE_L1C;obs.P[0]=24000000.0;
    CHECK(std::fabs(ntrip_test_code(&obs,nav.get(),&opt)-(24000000+1.25))<1e-9);
    CHECK(std::fabs(ntrip_test_spp_code(&obs,nav.get(),&opt)-(24000000+1.25))<1e-9);
    obs.code[0]=CODE_L5Q;
    CHECK(ntrip_test_code(&obs,nav.get(),&opt)==24000000);
    obs.code[0]=CODE_L1W;CHECK(ntrip_test_code(&obs,nav.get(),&opt)==0.0);

    // Deterministic broadcast orbit, SSR frame already has matching IODE=7.
    nav->eph=(eph_t*)calloc(1,sizeof(eph_t));nav->n=nav->nmax=1;
    auto &e=nav->eph[0];e.sat=1;e.iode=7;e.iodc=7;e.A=26560000;
    e.e=.01;e.i0=.94;e.OMG0=1;e.omg=.5;e.M0=.2;e.toe=e.toc=t;e.toes=100000;
    double br[6]{},sr[6]{},bd[2]{},sd[2]{},bv=0,sv=0;int bh=0,sh=0;
    CHECK(satpos(t,t,1,EPHOPT_BRDC,nav.get(),br,bd,&bv,&bh));
    CHECK(satpos(t,t,1,EPHOPT_SSRAPC,nav.get(),sr,sd,&sv,&sh));
    double delta[3];for(int i=0;i<3;i++)delta[i]=sr[i]-br[i];
    CHECK(std::fabs(norm(delta,3)-1.0)<1e-7);
    CHECK(std::fabs((sd[0]-bd[0])*CLIGHT-2.0)<1e-4);
    e.iode=8;CHECK(!satpos(t,t,1,EPHOPT_SSRAPC,nav.get(),sr,sd,&sv,&sh));
    e.iode=7;
    obs.code[0]=CODE_L1C;
    CHECK(stream->prepare(nav.get(),&opt,t,&obs,1)==0); // no ANTEX: cannot silently apply zero PCO
    CHECK(stream->reason=="SSR_REFERENCE_ANTEX_MISSING");
    nav->pcvs[0].sat=1;nav->pcvs[0].antex_pco_mask=(1<<1)|(1<<2)|(1<<5);
    CHECK(stream->prepare(nav.get(),&opt,t,&obs,1)==1);
    CHECK(stream->accepted_codes==1 && stream->accepted_satellites==1);
    obs.code[0]=CODE_L1W;CHECK(stream->prepare(nav.get(),&opt,t,&obs,1)==0);
    obs.code[0]=CODE_L1C;
    CHECK(stream->prepare(nav.get(),&opt,timeadd(t,100),&obs,1)==0);
    CHECK(stream->accepted_satellites==0);

    // Modern BDS SSR matches GPST TOC-derived IOD, never broadcast AODE.
    const int c20=satno(SYS_CMP,20);e.sat=c20;e.iode=4;e.iodc=4;
    auto match_bds=std::make_unique<NtripSsr>();CHECK(match_bds->init());
    auto match_orbit=frame(4,2,12,1,false,false,125,99986,true,138);
    match_bds->feed(nav.get(),0,match_orbit.data(),(int)match_orbit.size(),t);
    nav->ssr[c20-1]=match_bds->committed[c01];
    CHECK(satpos(t,t,c20,EPHOPT_BRDC,nav.get(),br,bd,&bv,&bh));
    CHECK(satpos(t,t,c20,EPHOPT_SSRAPC,nav.get(),sr,sd,&sv,&sh));
    for(int i=0;i<3;i++)delta[i]=sr[i]-br[i];
    CHECK(std::fabs(norm(delta,3)-1.0)<1e-7);
    CHECK(e.iode==4); // broadcast state remains untouched
    nav->ssr[c20-1].iode=139;
    CHECK(!satpos(t,t,c20,EPHOPT_SSRAPC,nav.get(),sr,sd,&sv,&sh)); // no nearest-IOD fallback
    nav->ssr[c20-1].iode=138;e.toe=timeadd(t,-MAXDTOE_CMP-2.0);
    CHECK(!satpos(t,t,c20,EPHOPT_SSRAPC,nav.get(),sr,sd,&sv,&sh));
    free(nav->eph);nav->eph=nullptr;nav->n=nav->nmax=0;

    auto igs=std::make_unique<NtripSsr>();CHECK(igs->init());
    auto io=frame(4,3,9,2,true),ic=frame(3,3,9,2,true);
    igs->feed(nav.get(),0,io.data(),(int)io.size(),t);
    igs->feed(nav.get(),0,ic.data(),(int)ic.size(),t);
    CHECK(NtripSsr::coherent(igs->committed[0],t));
    CHECK(igs->committed[0].provider[4]==9);CHECK(igs->committed[0].solution[4]==2);
    auto changed=frame(3,2,99,1);
    stream->feed(nav.get(),0,changed.data(),(int)changed.size(),t);
    CHECK(stream->blocked);CHECK(stream->reason=="SSR_PROVIDER_CHANGED_RESTART_REQUIRED");
    auto unsupported=std::make_unique<NtripSsr>();CHECK(unsupported->init());
    auto version3=io;setbitu(version3.data(),36,3,3);
    setbitu(version3.data(),((int)version3.size()-3)*8,24,rtk_crc24q(version3.data(),(int)version3.size()-3));
    unsupported->feed(nav.get(),0,version3.data(),(int)version3.size(),t);
    CHECK(unsupported->blocked && unsupported->reason=="IGS_SSR_VERSION_UNSUPPORTED");
    auto resync=std::make_unique<NtripSsr>();CHECK(resync->init());
    std::vector<unsigned char> noisy={0x71,0xD3,0xFC,0x00,0x11};
    noisy.insert(noisy.end(),orbit.begin(),orbit.end());noisy.insert(noisy.end(),code.begin(),code.end());
    resync->feed(nav.get(),0,noisy.data(),(int)noisy.size(),t);
    CHECK(resync->frames[0]==2 && NtripSsr::coherent(resync->committed[0],t));
    // The same gate-boundary lifecycle routine is called by Android JNI and PC.
    auto rtk=std::make_unique<rtk_t>();rtkinit(rtk.get(),&opt);
    obsd_t before[4]{},after[4]{};
    for(int i=0;i<4;i++){before[i].sat=i+1;before[i].code[0]=CODE_L1C;before[i].P[0]=24000000;before[i].L[0]=100000;}
    before[0].LLI[0]=LLI_SLIP;std::memcpy(after,before,sizeof(before));
    const auto original=before[0];
    NtripSsr::preserveRejectedArcs(rtk.get(),before,4,after,4);
    CHECK(!rtk->ssat[0].ppp_arc_pending[0]); // forwarded to normal PPP, no duplicate reset
    NtripSsr::preserveRejectedArcs(rtk.get(),before,4,after,3);
    CHECK(rtk->ssat[0].ppp_arc_pending[0]);
    CHECK(rtk->ssat[0].ppp_slip_evidence[0]&PPP_EVIDENCE_LLI);
    CHECK(std::memcmp(&original,before,sizeof(original))==0);
    rtkfree(rtk.get());rtkinit(rtk.get(),&opt);
    after[0].P[0]=after[0].L[0]=0; // one signal gated while satellite survives
    NtripSsr::preserveRejectedArcs(rtk.get(),before,4,after,4);
    CHECK(rtk->ssat[0].ppp_arc_pending[0]);
    rtkfree(rtk.get());rtkinit(rtk.get(),&opt);std::memcpy(after,before,sizeof(before));
    after[0].code[0]=CODE_L1W; // different actual signal is not a forwarded slip
    NtripSsr::preserveRejectedArcs(rtk.get(),before,4,after,4);
    CHECK(rtk->ssat[0].ppp_arc_pending[0]);
    rtkfree(rtk.get());rtkinit(rtk.get(),&opt);
    NtripSsr::preserveRejectedArcs(rtk.get(),before,4,nullptr,0);
    CHECK(rtk->ssat[0].ppp_arc_pending[0]); // all corrections lost
    rtkfree(rtk.get());rtkinit(rtk.get(),&opt);before[0].LLI[0]=0;
    NtripSsr::preserveRejectedArcs(rtk.get(),before,4,nullptr,0);
    CHECK(!rtk->ssat[0].ppp_arc_pending[0]); // no invented slip
    rtkfree(rtk.get());
    printf("NTRIP_NATIVE_CHECKS=%d passed\n",checks);return 0;
}
