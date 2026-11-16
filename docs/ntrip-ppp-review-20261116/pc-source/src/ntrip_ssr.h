#pragma once
#include <string>
#include <vector>
extern "C" {
#include "rtklib.h"
}

/* Orbit/clock (0), broadcast (1), optional separate bias (2). Serial owner only. */
class NtripSsr {
public:
    rtcm_t *decoder[3]{};
    std::vector<unsigned char> frame_buffer[3];
    ssr_t committed[MAXSAT]{};
    ssr_t transport_committed[3][MAXSAT]{};
    unsigned long frames[3]{}, crc_errors[3]{}, messages[3]{};
    unsigned long decode_errors[3]{};
    bool blocked=false;
    int provider=-1, solution=-1;
    int bias_provider=-1,bias_solution=-1;
    int accepted_satellites=0, accepted_codes=0;
    std::string reason="WAITING_RTCM";
    ~NtripSsr();
    bool init();
    static constexpr const char *WHU_CONTINUITY_PROFILE="WHU_OSB_CONTINUITY_V1";
    static constexpr const char *WHU_FIRST_COMPLETE_PROFILE="WHU_OSB_FIRST_COMPLETE_V2";
    bool useWhuOsb(const std::string &orbit_mount,const std::string &bias_mount,bool com,
                   bool start_with_first_bias=false);
    bool usable(int sat,gtime_t epoch,std::string *why=nullptr) const;
    bool phaseUsable(int sat,gtime_t epoch,std::string *why=nullptr) const;
    bool whuProfile() const { return whu_osb; }
    const char *profileName() const;
    void resetTransport(int channel); // discard fragments/incomplete batches, keep completed data
    void feed(nav_t *nav,int channel,const unsigned char *data,int count,gtime_t anchor);
    int prepare(nav_t *nav,const prcopt_t *opt,gtime_t epoch,obsd_t *obs,int n);
    // Keep confirmed slips even when correction gating prevents a PPP update.
    static void preserveRejectedArcs(rtk_t *rtk,const obsd_t *before,int n,
                                     const obsd_t *after,int accepted);
    std::string status() const;
    static bool coherent(const ssr_t &s,gtime_t time,std::string *why=nullptr);
    static void setReference(nav_t *nav); // documented standard SSR APC frequency pairs
private:
    // Operational continuity watchdogs, NOT a claimed WHU satellite-bias validity interval.
    static constexpr double WHU_ESTIMATION_SECONDS=300.0;
    static constexpr double WHU_SENDING_SECONDS=5.0;
    bool whu_osb=false;
    bool whu_start_with_first_bias=false;
    int whu_orbit_iod=-1,whu_bias_iod=-1;
    struct BiasContinuity {gtime_t epoch{},received{},advanced{};bool consecutive=false;};
    BiasContinuity bias_continuity[MAXSAT]{};
    BiasContinuity phase_continuity[MAXSAT]{};
    int phase_provider=-1,phase_solution=-1,phase_iod=-1;
    bool phase_blocked=false;
    struct PhaseBatch {bool open=false;int key=0,epoch=0,iod=0,provider=0,solution=0;};
    PhaseBatch phase_batch[3]{};
    void rollbackPhase(int channel);
    void commitPhase(int channel,gtime_t receipt);
    bool observeWhuBias(int sat,const ssr_t &s,gtime_t receipt);
    void mergeEphemeris(nav_t *nav,const rtcm_t *r);
};
