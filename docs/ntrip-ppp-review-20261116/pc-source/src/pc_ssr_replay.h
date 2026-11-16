#pragma once
#include "rtklib.h"
#ifdef __cplusplus
extern "C" {
#endif
int pc_ssr_open(const char *directory, const char *diagnostic_csv, const char *datum,
                double latency_ms, nav_t *nav, prcopt_t *opt);
int pc_ssr_open_profile(const char *directory,const char *diagnostic_csv,const char *datum,
                double latency_ms,nav_t *nav,prcopt_t *opt,const char *profile);
int pc_ssr_active(void);
gtime_t pc_ssr_start(void);
int pc_ssr_prepare(gtime_t epoch,nav_t *nav,const prcopt_t *opt,obsd_t *obs,int n);
const char *pc_ssr_error(void);
void pc_ssr_close(void);
int pc_ssr_inspect(const char *directory,FILE *output);
int pc_ssr_inspect_profile(const char *directory,FILE *output,const char *profile);
void pc_ssr_preserve_rejected_arcs(rtk_t *rtk,const obsd_t *before,int n,
                                  const obsd_t *after,int accepted);
#ifdef __cplusplus
}
#endif
