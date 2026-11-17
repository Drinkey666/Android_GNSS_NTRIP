"""Compile the formal replay sources with read-only Step 9 hooks in three private copies."""

import difflib
import os
from pathlib import Path
import re
import shutil
import subprocess

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SOURCE = OUT / "private_src"
OBJECTS = OUT / "private_obj"

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one source anchor: {old[:100]!r}")
    return text.replace(old, new, 1)

include = ('#include "rtklib.h"', '#include "rtklib.h"\n#include "step9_audit.h"')

changes = {
    "pntpos.c": [
        include,
        ("/* pseudorange residuals -----------------------------------------------------*/\nstatic int rescode",
         '#include "step9_spp.inc"\n\n/* pseudorange residuals -----------------------------------------------------*/\nstatic int rescode'),
        ("        var[nv++] += varerr(opt, &obs[i], azel[1 + i * 2], sys);",
         """        {
            double noise=varerr(opt, &obs[i], azel[1 + i * 2], sys);
            var[nv] += noise;
            s9_row(nv,i,obs+i,-1,sys,azel+2*i,P,r,-CLIGHT*dts[2*i],dion,dtrp,
                   vare[i],vmeas,vion,vtrp,noise,var[nv],v[nv],H+nv*NX);
            nv++;
        }"""),
        ("        var[nv++] = 0.01;", """        var[nv] = 0.01;
        s9_row(nv,-1,NULL,i+3,0,NULL,0,0,0,0,0,0,0,0,0,0,var[nv],v[nv],H+nv*NX);
        nv++;"""),
        ("    // 开始最大 MAXITR", "    s9_try();\n    // 开始最大 MAXITR"),
        ("        nv = rescode(i, obs", "        s9_iteration=i;\n        nv = rescode(i, obs"),
        ("azel, vsat, resp, &ns);\n\n        // 自由度检查",
         "azel, vsat, resp, &ns);\n        s9_iteration=-1;\n\n        // 自由度检查"),
        ('            sprintf(msg, "lack of valid sats ns=%d", nv);',
         '            s9_result("lack_rows",i,0);\n            sprintf(msg, "lack of valid sats ns=%d", nv);'),
        ('            sprintf(msg, "lsq error info=%d", info);',
         '            s9_result("singular",i,0);\n            sprintf(msg, "lsq error info=%d", info);'),
        ("        for (j = 0; j < NX; j++) x[j] += dx[j];", """        {
            double before[NX];
            memcpy(before,x,sizeof(before));
            for (j = 0; j < NX; j++) x[j] += dx[j];
            s9_step(i,nv,before,dx,x);
        }"""),
        ("            free(v); free(H); free(var);\n            return stat;", """            s9_result(stat?"valsol_pass":"valsol_reject",i,1);
            if (stat && s9_log) {
                double post_azel[2*MAXOBS],post_resp[MAXOBS];
                int post_n,post_used[MAXOBS];
                s9_iteration=i;
                s9_postfit=1;
                /* Independent, read-only nonlinear residuals at the accepted x.
                 * Isolate buffers; do not feed this evaluation back to the solver. */
                rescode(1,obs,n,rs,dts,vare,svh,nav,x,opt,ssat,v,H,var,
                        post_azel,post_used,post_resp,&post_n);
                s9_postfit=0;
                s9_iteration=-1;
            }
            free(v); free(H); free(var);
            return stat;"""),
        ('    if (i >= MAXITR) sprintf(msg, "iteration divergent i=%d", i);',
         '    if (i >= MAXITR) s9_result("no_convergence",i,0);\n    if (i >= MAXITR) sprintf(msg, "iteration divergent i=%d", i);'),
        ("    int trial_used[MAXOBS],best_used[MAXOBS];", "    int s9_best=0;\n    int trial_used[MAXOBS],best_used[MAXOBS];"),
        ("        if(ok&&candidate<0)return 1;",
         "        if(ok)s9_metrics(candidate,dof,score,z,metres);\n        if(ok&&candidate<0)return 1;"),
        ("            trial=*sol;trial.stat=SOLQ_NONE;",
         '            trial=*sol;trial.stat=SOLQ_NONE;\n            s9_hypothesis("startup_fde",work[i].sat,s9_winner);'),
        ("            if(tdof<2||!isfinite(trial_score)||trial_score>=best_score)continue;",
         """            if(s9_log)fprintf(s9_log,"TRIAL_METRICS\\t%d\\t%d\\t%d\\t%.17g\\t%.17g\\t%.17g\\n",
                              s9_call,s9_attempt,tdof,trial_score,tz,tm);
            if(tdof<2||!isfinite(trial_score)||trial_score>=best_score)continue;
            s9_best=s9_attempt;"""),
        ("        work[best_i].P[0]=0.0;rejected[best_i]=1;*sol=best;ok=1;",
         """        work[best_i].P[0]=0.0;rejected[best_i]=1;*sol=best;ok=1;
        s9_selection("startup_fde",round,work[best_i].sat,s9_best);"""),
        ("    if(candidate>=0){strcpy(msg,", "    s9_metrics(candidate,dof,score,z,metres);\n    if(candidate>=0){strcpy(msg,"),
        ("    int i,j,k,nvsat,stat=0,*svh_e,*vsat_e,sat=0;",
         "    int i,j,k,nvsat,stat=0,*svh_e,*vsat_e,sat=0;\n    int s9_raim_parent=0;"),
        ("        if (!estpos(obs_e,n-1,rs_e,dts_e,vare_e,svh_e,nav,opt,ssat,&sol_e,azel_e,\n                    vsat_e,resp_e,msg_e)) {",
         """        s9_hypothesis("raim_fde",obs[i].sat,s9_raim_parent);
        {
            int solved=estpos(obs_e,n-1,rs_e,dts_e,vare_e,svh_e,nav,opt,ssat,
                              &sol_e,azel_e,vsat_e,resp_e,msg_e);
            s9_raim_parent=s9_attempt;
            if (!solved) {"""),
        ("            trace(3,\"raim_fde: exsat=%2d (%s)\\n\",obs[i].sat,msg);\n            continue;\n        }",
         """                trace(3,"raim_fde: exsat=%2d (%s)\\n",obs[i].sat,msg);
                continue;
            }
        }"""),
        ("        *sol=sol_e;\n        sat=obs[i].sat;",
         '        *sol=sol_e;\n        s9_selection("raim_fde",i,obs[i].sat,s9_attempt);\n        sat=obs[i].sat;'),
        ("    candidate=*sol;\n    sol=&candidate;",
         "    s9_begin(obs[0].time,startup,opt->sateph);\n    candidate=*sol;\n    sol=&candidate;"),
        ("    if(startup)stat=startup_fde(",
         '    s9_selection("initial",-1,0,s9_attempt);\n    if(startup)stat=startup_fde('),
        ("    if (stat) *output=*sol;\n    else {",
         "    if (stat) *output=*sol;\n    s9_end(stat,output);\n    if (!stat) {"),
    ],
    "rtkpos.c": [
        include,
        ("    /* rover position and time by single point positioning, skip if",
         """    s9_state(obs[0].time,"rtk_entry",rtk,rtk->x,rtk->ppp_clock_m,0,0);
    /* rover position and time by single point positioning, skip if"""),
        ("        ppp_innovation_note_spp(spp_ok && (!isolated || bootstrap));",
         """        s9_state(obs[0].time,"spp_return",rtk,spp_output->rr,CLIGHT*spp_output->dtr[0],
                 spp_ok,spp_ok && (!isolated || bootstrap));
        ppp_innovation_note_spp(spp_ok && (!isolated || bootstrap));"""),
        ('            trace(2,"$SPP_FALLBACK,', '''            s9_state(obs[0].time,"spp_fallback",rtk,rtk->x,CLIGHT*rtk->sol.dtr[0],0,0);
            trace(2,"$SPP_FALLBACK,'''),
        ("        pppos(rtk, obs, nu, nav);", """        pppos(rtk, obs, nu, nav);
        s9_state(obs[0].time,"ppp_return",rtk,rtk->x,rtk->ppp_clock_m,0,0);"""),
    ],
    "ppp.c": [
        include,
        ("    udpos_ppp(rtk);", """    s9_state(obs[0].time,"udpos_in",rtk,rtk->x,rtk->x[IC(0,&rtk->opt)],0,0);
    udpos_ppp(rtk);
    s9_state(obs[0].time,"udpos_out",rtk,rtk->x,rtk->x[IC(0,&rtk->opt)],0,0);"""),
        ("    udclk_ppp(rtk);", """    udclk_ppp(rtk);
    s9_state(obs[0].time,"udclk_out",rtk,rtk->x,rtk->x[IC(0,&rtk->opt)],0,0);"""),
        ("        if(opt->ppp_iekf) {\n            ppp_iekf_context_t ctx;",
         """        s9_state(obs[0].time,"ppp_trial_prior",rtk,xp,xp[IC(0,opt)],i,nv);
        if(opt->ppp_iekf) {
            ppp_iekf_context_t ctx;"""),
        ("            stat = SOLQ_PPP;\n", """            s9_state(obs[0].time,"ppp_commit",rtk,rtk->x,rtk->ppp_clock_m,i,nv);
            stat = SOLQ_PPP;
"""),
    ],
}

def build():
    SOURCE.mkdir()
    OBJECTS.mkdir()
    for directory in ("core", "src"):
        private = SOURCE / directory
        private.mkdir()
        for source in (ROOT / directory).iterdir():
            if source.is_file():
                shutil.copy2(source, private / source.name)
    patch = []
    for name, replacements in changes.items():
        path = SOURCE / "core" / name
        old_text = path.read_text(encoding="utf-8-sig")
        new_text = old_text
        for before, after in replacements:
            new_text = replace_once(new_text, before, after)
        path.write_text(new_text, encoding="utf-8")
        patch.extend(difflib.unified_diff(old_text.splitlines(True), new_text.splitlines(True),
                     fromfile=f"a/core/{name}", tofile=f"b/core/{name}"))
    for name in ("step9_spp.inc", "step9_audit.h"):
        shutil.copy2(OUT / name, SOURCE / "core" / name)
    (OUT / "step9_private.patch").write_text("".join(patch), encoding="utf-8")

    stock = (ROOT / "build/build.cmd").read_text(encoding="utf-8-sig").splitlines()
    link = next(line for line in stock if line.startswith("link ") and "ppp_ssr_replay.exe" in line)
    wanted = re.findall(r'"([^"]+\.obj)"', link)
    compile_lines = []
    for obj in wanted:
        compile_lines.append(next(line for line in stock if line.startswith("cl ") and f'/Fo"{obj}"' in line))
    replacements = [(ROOT / "core", SOURCE / "core"), (ROOT / "src", SOURCE / "src"),
                    (ROOT / "build", OBJECTS), (ROOT / "bin" / "ppp_ssr_replay.exe", OUT / "step9_probe.exe")]
    def private(line):
        for source, target in replacements:
            line = line.replace(str(source), str(target))
        return line
    commands = stock[:2]
    for line in compile_lines:
        commands.extend((private(line), "if errorlevel 1 exit /b 1"))
    commands.extend((private(link), "if errorlevel 1 exit /b 1"))
    cmd = OUT / "build_private.cmd"
    cmd.write_text("\n".join(commands) + "\n", encoding="utf-8")
    env = dict(os.environ, TEMP=str(OUT), TMP=str(OUT))
    with (OUT / "build_private.log").open("wb") as log:
        subprocess.run(["cmd", "/c", str(cmd)], cwd=OUT, env=env, stdout=log,
                       stderr=subprocess.STDOUT, check=True)
    print(f"Built Step 9 with {len(wanted)} private objects")

if __name__ == "__main__":
    build()
